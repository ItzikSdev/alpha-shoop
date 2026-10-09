import { useEffect, useMemo, useRef } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { Html, OrbitControls } from '@react-three/drei';
import type { Group } from 'three';
import { Vector3 } from 'three';
import type { AgentPublic, AgentState, Visitor } from './types';
import { SOURCE_COLOR, SOURCE_LABEL, STAGE_LABEL, STATE_COLOR, STATE_LABEL, colorFor, flagOf } from './types';

// ── Floor plan (world units). Offices on the left, gym + meeting room on the right ──
//  x: -9 … 3.2 offices | 3.2 … 9 gym (z < 0.15) / meeting room (z > 0.15)
const INNER_X = 3.2;
const SPLIT_Z = 0.15;
const AISLE_X = 2.5;          // clear aisle along the inner wall
const DOOR_Z = { gym: -2.2, meeting: 2.6 } as const;
const DESK_COLS = [-7.6, -4.6, -1.6, 1.0];
const DESK_ROWS = [-4.0, -1.0, 2.0];   // desk centre z; seat is +1.0 in front

type Area = 'office' | 'exec' | 'gym' | 'meeting';
type V2 = [number, number];

export function seatFor(i: number): V2 {
  const col = i % DESK_COLS.length;
  const row = Math.min(Math.floor(i / DESK_COLS.length), DESK_ROWS.length - 1);
  return [DESK_COLS[col], DESK_ROWS[row] + 1.0];
}

// Private offices for senior roles (CEO / oversight) along the front of the floor.
const OFFICE_W = 3.7;
const OFFICE_CX = [-7.15, -3.45, 0.25];
const OFFICE_BACK_Z = 2.5;      // glass partition with the door
const OFFICE_DESK_Z = 3.8;
const OFFICE_SEAT_Z = 4.85;
const CORRIDOR_Z = 1.8;         // free lane between the cubicle rows and the offices
export const isSenior = (a: AgentPublic) => a.team === 'leadership' || a.team === 'oversight';

export interface Layout { seat: Map<string, V2>; office: Map<string, number> }
export function layoutOf(agents: AgentPublic[]): Layout {
  const seat = new Map<string, V2>();
  const office = new Map<string, number>();
  let o = 0;
  let k = 0;
  for (const a of agents) {
    if (isSenior(a) && o < OFFICE_CX.length) {
      office.set(a.agent_id, o);
      seat.set(a.agent_id, [OFFICE_CX[o], OFFICE_SEAT_Z]);
      o += 1;
    } else {
      seat.set(a.agent_id, seatFor(k));
      k += 1;
    }
  }
  return { seat, office };
}
/** Where a visitor stands next to someone's desk to talk to them. */
function visitSpot(seat: V2, inOffice: boolean): V2 {
  return inOffice ? [seat[0] + 1.0, seat[1]] : [seat[0] + 1.05, seat[1] + 0.15];
}
const nearestOfficeX = (x: number) => OFFICE_CX.reduce((b, c) => (Math.abs(c - x) < Math.abs(b - x) ? c : b), OFFICE_CX[0]);
const GYM_SLOTS: V2[] = [[4.6, -4.4], [6.2, -4.4], [7.8, -4.4], [4.6, -1.0], [6.2, -1.0], [7.8, -1.0],
  [5.4, -3.0], [7.0, -3.0], [8.2, -2.2]];
const MEET_SLOTS: V2[] = [[5.0, 2.0], [6.3, 1.5], [7.6, 2.0], [5.0, 3.9], [6.3, 4.4], [7.6, 3.9],
  [4.2, 2.95], [8.3, 2.95], [6.3, 5.0]];

function areaOf([x, z]: V2): Area {
  if (x <= INNER_X) return z >= 4.0 ? 'exec' : 'office';
  return z < SPLIT_Z ? 'gym' : 'meeting';
}

/** Waypoints that go around desks and through the doors instead of through walls. */
function pathBetween(from: V2, to: V2): V2[] {
  const a = areaOf(from);
  const b = areaOf(to);
  const out: V2[] = [];
  const inside = (x: Area) => x === 'office' || x === 'exec';
  const leave = (p: V2, area: Area) => {
    if (area === 'exec') { const cx = nearestOfficeX(p[0]); out.push([cx, OFFICE_BACK_Z + 0.9], [cx, CORRIDOR_Z], [AISLE_X, CORRIDOR_Z]); }
    else out.push([p[0], p[1] + 0.7], [AISLE_X, p[1] + 0.7]);
  };
  const enter = (p: V2, area: Area) => {
    if (area === 'exec') { const cx = nearestOfficeX(p[0]); out.push([AISLE_X, CORRIDOR_Z], [cx, CORRIDOR_Z], [cx, OFFICE_BACK_Z + 0.9]); }
    else out.push([AISLE_X, p[1] + 0.7], [p[0], p[1] + 0.7]);
  };
  if (inside(a) && inside(b)) {
    const sameOffice = a === 'exec' && b === 'exec' && nearestOfficeX(from[0]) === nearestOfficeX(to[0]);
    if (!sameOffice && Math.abs(from[0] - to[0]) + Math.abs(from[1] - to[1]) > 0.1) { leave(from, a); enter(to, b); }
  } else if (inside(a)) {
    leave(from, a);
    out.push([AISLE_X, DOOR_Z[b as 'gym' | 'meeting']], [4.0, DOOR_Z[b as 'gym' | 'meeting']]);
  } else if (inside(b)) {
    out.push([4.0, DOOR_Z[a as 'gym' | 'meeting']], [AISLE_X, DOOR_Z[a as 'gym' | 'meeting']]);
    enter(to, b);
  } else if (a !== b) {
    out.push([4.0, DOOR_Z[a as 'gym' | 'meeting']], [AISLE_X, DOOR_Z[a as 'gym' | 'meeting']], [AISLE_X, DOOR_Z[b as 'gym' | 'meeting']], [4.0, DOOR_Z[b as 'gym' | 'meeting']]);
  }
  out.push(to);
  return out;
}

// ── Static set pieces ─────────────────────────────────────────────────────────

function Box({ p, s, c, e }: { p: [number, number, number]; s: [number, number, number]; c: string; e?: number }) {
  return (
    <mesh position={p} castShadow receiveShadow>
      <boxGeometry args={s} />
      <meshStandardMaterial color={c} emissive={e ? c : '#000'} emissiveIntensity={e ?? 0} />
    </mesh>
  );
}

function Cubicle({ x, z, color }: { x: number; z: number; color: string }) {
  return (
    <group position={[x, 0, z]}>
      <Box p={[0, 0.72, 0]} s={[1.9, 0.08, 0.9]} c="#d9c3a0" />
      <Box p={[0, 0.36, -0.3]} s={[1.7, 0.7, 0.06]} c="#8b6f47" />
      <Box p={[0, 1.05, -0.2]} s={[0.8, 0.5, 0.05]} c="#111827" e={0.25} />
      <mesh position={[0, 1.05, -0.17]}>
        <planeGeometry args={[0.72, 0.42]} />
        <meshBasicMaterial color={color} transparent opacity={0.35} />
      </mesh>
      <Box p={[0, 0.55, -0.55]} s={[2.3, 1.1, 0.08]} c="#efe6d6" />
      <Box p={[-1.15, 0.55, 0.05]} s={[0.08, 1.1, 1.3]} c="#efe6d6" />
      <Box p={[0, 0.42, 1.05]} s={[0.5, 0.08, 0.5]} c="#374151" />
      <Box p={[0, 0.7, 1.28]} s={[0.5, 0.5, 0.08]} c="#374151" />
    </group>
  );
}

function ExecOffice({ cx, agent }: { cx: number; agent: AgentPublic }) {
  const wall = '#e7dcc8';
  const col = colorFor(agent.role);
  const half = OFFICE_W / 2;
  const glass = (x: number, w: number) => (
    <group position={[x, 0, OFFICE_BACK_Z]}>
      <Box p={[0, 0.06, 0]} s={[w, 0.12, 0.1]} c={wall} />
      <mesh position={[0, 0.58, 0]}>
        <boxGeometry args={[w, 0.9, 0.04]} />
        <meshStandardMaterial color="#9ec9e8" transparent opacity={0.35} />
      </mesh>
    </group>
  );
  const doorHalf = 0.55;
  return (
    <group>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[cx, 0.015, 4.0]} receiveShadow>
        <planeGeometry args={[OFFICE_W - 0.15, 2.85]} />
        <meshStandardMaterial color="#b7a98f" />
      </mesh>
      {glass(cx - half / 2 - doorHalf / 2, half - doorHalf)}
      {glass(cx + half / 2 + doorHalf / 2, half - doorHalf)}
      {cx > -7 && <Box p={[cx - half + 0.05, 0.5, 4.0]} s={[0.08, 1.0, 3.0]} c={wall} />}
      <Box p={[cx + half - 0.05, 0.5, 4.0]} s={[0.08, 1.0, 3.0]} c={wall} />
      {/* executive desk + two monitors + chair */}
      <Box p={[cx, 0.72, OFFICE_DESK_Z]} s={[2.3, 0.09, 0.95]} c="#5b4128" />
      <Box p={[cx - 0.9, 0.36, OFFICE_DESK_Z]} s={[0.4, 0.7, 0.85]} c="#4a3420" />
      <Box p={[cx + 0.9, 0.36, OFFICE_DESK_Z]} s={[0.4, 0.7, 0.85]} c="#4a3420" />
      {[-0.5, 0.5].map((dx) => (
        <group key={dx}>
          <Box p={[cx + dx, 1.08, OFFICE_DESK_Z - 0.25]} s={[0.78, 0.46, 0.05]} c="#111827" e={0.25} />
          <mesh position={[cx + dx, 1.08, OFFICE_DESK_Z - 0.22]}>
            <planeGeometry args={[0.7, 0.38]} />
            <meshBasicMaterial color={col} transparent opacity={0.35} />
          </mesh>
        </group>
      ))}
      <Box p={[cx, 0.42, OFFICE_SEAT_Z + 0.05]} s={[0.55, 0.08, 0.55]} c="#1f2937" />
      <Box p={[cx, 0.75, OFFICE_SEAT_Z + 0.3]} s={[0.55, 0.65, 0.08]} c="#1f2937" />
      {/* guest chairs, shelf, plant */}
      {[-0.65, 0.65].map((dx) => (
        <group key={dx}>
          <Box p={[cx + dx, 0.3, 3.0]} s={[0.45, 0.08, 0.45]} c="#64748b" />
          <Box p={[cx + dx, 0.55, 2.78]} s={[0.45, 0.45, 0.07]} c="#64748b" />
        </group>
      ))}
      <Box p={[cx - half + 0.3, 0.55, 4.5]} s={[0.35, 1.1, 1.5]} c="#6b4f35" />
      <Box p={[cx - half + 0.3, 0.9, 4.5]} s={[0.3, 0.1, 1.3]} c="#c9b28a" />
      <Tree x={cx + half - 0.45} z={5.05} s={0.5} />
      <RoomLabel p={[cx, 1.75, OFFICE_BACK_Z]} title={agent.name.toUpperCase()}
        sub={agent.role === agent.name ? 'יועץ בכיר' : agent.role} />
    </group>
  );
}

function Tree({ x, z, s = 1 }: { x: number; z: number; s?: number }) {
  return (
    <group position={[x, 0, z]} scale={s}>
      <Box p={[0, 0.35, 0]} s={[0.18, 0.7, 0.18]} c="#7c5a3a" />
      <mesh position={[0, 1.0, 0]} castShadow>
        <boxGeometry args={[0.8, 0.8, 0.8]} />
        <meshStandardMaterial color="#3f7d3a" />
      </mesh>
    </group>
  );
}

function Car({ x, z, color }: { x: number; z: number; color: string }) {
  return (
    <group position={[x, 0, z]}>
      <Box p={[0, 0.3, 0]} s={[1.0, 0.35, 1.9]} c={color} />
      <Box p={[0, 0.6, -0.1]} s={[0.85, 0.3, 1.0]} c="#cbd5e1" />
      {([[-0.5, 0.65], [0.5, 0.65], [-0.5, -0.65], [0.5, -0.65]] as V2[]).map(([wx, wz], k) => (
        <Box key={k} p={[wx, 0.14, wz]} s={[0.12, 0.28, 0.32]} c="#111827" />
      ))}
    </group>
  );
}

function RoomLabel({ p, title, sub }: { p: [number, number, number]; title: string; sub: string }) {
  return (
    <Html position={p} center zIndexRange={[5, 0]}>
      <div dir="rtl" style={{
        pointerEvents: 'none', background: 'rgba(255,255,255,0.92)', color: '#0f172a', borderRadius: 8,
        padding: '3px 10px', fontSize: 12, whiteSpace: 'nowrap', boxShadow: '0 1px 4px rgba(0,0,0,.25)',
        textAlign: 'center',
      }}>
        <div style={{ fontWeight: 700, letterSpacing: 0.5 }}>{title}</div>
        <div style={{ fontSize: 11.5, fontWeight: 500, color: '#020617' }}>{sub}</div>
      </div>
    </Html>
  );
}

function Building({ agents, layout }: { agents: AgentPublic[]; layout: Layout }) {
  const wall = '#e7dcc8';
  const H = 1.0;
  return (
    <group>
      {/* slab + floors */}
      <Box p={[0, -0.12, 0]} s={[18.4, 0.24, 11.4]} c="#6b4f35" />
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[-2.9, 0.01, 0]} receiveShadow>
        <planeGeometry args={[12.2, 11]} />
        <meshStandardMaterial color="#d8c7a6" />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[6.1, 0.012, -2.7]} receiveShadow>
        <planeGeometry args={[5.8, 5.6]} />
        <meshStandardMaterial color="#c9d6cf" />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[6.1, 0.012, 2.8]} receiveShadow>
        <planeGeometry args={[5.8, 5.3]} />
        <meshStandardMaterial color="#d6cfe0" />
      </mesh>
      {/* outer walls (front open like a cut-away, with a door) */}
      <Box p={[0, H / 2, -5.5]} s={[18.2, H, 0.15]} c={wall} />
      <Box p={[-9.05, H / 2, 0]} s={[0.15, H, 11]} c={wall} />
      <Box p={[9.05, H / 2, 0]} s={[0.15, H, 11]} c={wall} />
      <Box p={[-5.0, 0.2, 5.5]} s={[8.2, 0.4, 0.15]} c={wall} />
      <Box p={[5.0, 0.2, 5.5]} s={[8.2, 0.4, 0.15]} c={wall} />
      {/* inner wall with two doors (gym, meeting) */}
      <Box p={[INNER_X, H / 2, -4.25]} s={[0.12, H, 2.5]} c={wall} />
      <Box p={[INNER_X, H / 2, 0.2]} s={[0.12, H, 3.4]} c={wall} />
      <Box p={[INNER_X, H / 2, 4.4]} s={[0.12, H, 2.2]} c={wall} />
      <Box p={[6.1, H / 2, SPLIT_Z]} s={[5.8, H, 0.12]} c={wall} />
      {/* cubicles — one per agent */}
      {agents.filter((a) => !layout.office.has(a.agent_id)).map((a) => {
        const [sx, sz] = layout.seat.get(a.agent_id)!;
        return <Cubicle key={a.agent_id} x={sx} z={sz - 1.0} color={colorFor(a.role)} />;
      })}
      {/* private offices for senior roles */}
      {agents.filter((a) => layout.office.has(a.agent_id)).map((a) => (
        <ExecOffice key={a.agent_id} cx={OFFICE_CX[layout.office.get(a.agent_id)!]} agent={a} />
      ))}
      {/* gym */}
      {GYM_SLOTS.slice(0, 3).map(([x, z], k) => (
        <group key={k} position={[x, 0, z - 0.2]}>
          <Box p={[0, 0.12, 0]} s={[0.7, 0.18, 1.4]} c="#1f2937" />
          <Box p={[0, 0.6, -0.65]} s={[0.7, 0.8, 0.08]} c="#475569" />
        </group>
      ))}
      <Box p={[6.2, 0.25, -2.6]} s={[1.6, 0.12, 0.45]} c="#9a3412" />
      <Box p={[4.6, 0.5, -2.7]} s={[0.25, 0.9, 0.25]} c="#dc2626" />
      <RoomLabel p={[8.2, 2.6, -4.9]} title="חדר כושר" sub="מי שלא במשמרת" />
      {/* meeting room */}
      <Box p={[6.3, 0.62, 2.95]} s={[2.4, 0.08, 1.4]} c="#7c5a3a" />
      <Box p={[6.3, 0.3, 2.95]} s={[0.2, 0.6, 0.2]} c="#5b4128" />
      <Box p={[8.85, 1.0, 2.95]} s={[0.06, 0.9, 1.6]} c="#0f172a" e={0.2} />
      <RoomLabel p={[8.2, 2.6, 4.9]} title="חדר ישיבות" sub="כשיש פגישה — האחראים כאן" />
      {/* entrance + outside */}
      {[6.3, 7.1, 7.9, 8.7].map((z) => (
        <mesh key={z} rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.02, z]}>
          <circleGeometry args={[0.32, 16]} />
          <meshStandardMaterial color="#d1d5db" />
        </mesh>
      ))}
      <Box p={[-1.6, 0.3, 6.4]} s={[1.6, 0.6, 0.6]} c="#3f7d3a" />
      <Box p={[1.6, 0.3, 6.4]} s={[1.6, 0.6, 0.6]} c="#3f7d3a" />
      {([[-11, -4], [-11.5, 1], [11, -3.5], [11.2, 3], [-5, 8.5], [5, 8.8], [9, 8], [-10, 7.5]] as V2[]).map(([x, z], k) => (
        <Tree key={k} x={x} z={z} s={0.9 + (k % 3) * 0.15} />
      ))}
      {/* parking */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[-13.2, 0.01, 1]}>
        <planeGeometry args={[3.6, 7]} />
        <meshStandardMaterial color="#6b7280" />
      </mesh>
      <Car x={-13.2} z={-1} color="#ef4444" />
      <Car x={-13.2} z={2.6} color="#3b82f6" />
      <RoomLabel p={[-13.2, 1.4, 4.8]} title="חניה" sub="הולכים הביתה כשאין עבודה" />
    </group>
  );
}


// ── The store (right of the office) + live visitors ───────────────────────────
const STORE_CX = 15.5;
const STORE_W = 7.4;
const STORE_Z0 = -3.4;          // back wall
const STORE_Z1 = 3.0;           // front (door side)
const STORE_DOOR: V2 = [STORE_CX, STORE_Z1 + 0.2];
const QUEUE_START: V2 = [STORE_CX, STORE_Z1 + 1.3];   // first in line stands here, line runs toward +z
const STREET_SPAWN: V2 = [STORE_CX + 7, 8.5];
const SHELF_SPOTS: V2[] = [[STORE_CX - 2.4, -1.6], [STORE_CX - 2.4, 0.2], [STORE_CX + 0.2, -2.0], [STORE_CX + 2.4, -1.4],
  [STORE_CX + 2.4, 0.4], [STORE_CX - 0.6, 1.2], [STORE_CX + 0.9, 1.6]];
const COUNTER_SPOTS: V2[] = [[STORE_CX + 1.2, -0.6], [STORE_CX + 2.3, -0.6], [STORE_CX + 3.0, 0.5]];
const QUEUE_WINDOW_S = 75;      // a fresh arrival waits in line this long, then walks in

function StoreBuilding({ liveCount }: { liveCount: number }) {
  const wall = '#f3e8d6';
  const H = 2.1;
  const z0 = STORE_Z0, z1 = STORE_Z1, w = STORE_W, cx = STORE_CX;
  const doorW = 1.3;
  const sideW = (w - doorW) / 2;
  const shelf = (x: number, z: number, rot = 0) => (
    <group position={[x, 0, z]} rotation={[0, rot, 0]}>
      <Box p={[0, 0.55, 0]} s={[1.6, 1.1, 0.4]} c="#a07a52" />
      {[0.25, 0.65, 1.0].map((y, k) => (
        <group key={y}>
          <Box p={[-0.45, y + 0.12, 0.05]} s={[0.35, 0.22, 0.25]} c={['#f9a8d4', '#93c5fd', '#fde68a'][k]} />
          <Box p={[0.0, y + 0.1, 0.05]} s={[0.3, 0.18, 0.25]} c={['#86efac', '#fca5a5', '#c4b5fd'][k]} />
          <Box p={[0.45, y + 0.12, 0.05]} s={[0.35, 0.22, 0.25]} c={['#fdba74', '#a5f3fc', '#f9a8d4'][k]} />
        </group>
      ))}
    </group>
  );
  return (
    <group>
      <Box p={[cx, -0.06, (z0 + z1) / 2]} s={[w + 0.8, 0.12, z1 - z0 + 0.8]} c="#8a6a49" />
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[cx, 0.01, (z0 + z1) / 2]} receiveShadow>
        <planeGeometry args={[w, z1 - z0]} />
        <meshStandardMaterial color="#fbeedd" />
      </mesh>
      {/* walls: back, left, right, front with a door gap and glass windows */}
      <Box p={[cx, H / 2, z0]} s={[w, H, 0.15]} c={wall} />
      <Box p={[cx - w / 2, H / 2, (z0 + z1) / 2]} s={[0.15, H, z1 - z0]} c={wall} />
      <Box p={[cx + w / 2, H / 2, (z0 + z1) / 2]} s={[0.15, H, z1 - z0]} c={wall} />
      {[-1, 1].map((sd) => (
        <group key={sd} position={[cx + sd * (doorW / 2 + sideW / 2), 0, z1]}>
          <Box p={[0, 0.3, 0]} s={[sideW, 0.6, 0.15]} c={wall} />
          <mesh position={[0, 1.35, 0]}>
            <boxGeometry args={[sideW, 1.5, 0.05]} />
            <meshStandardMaterial color="#bfe3f5" transparent opacity={0.35} />
          </mesh>
          <Box p={[0, 2.05, 0]} s={[sideW, 0.1, 0.15]} c={wall} />
        </group>
      ))}
      <Box p={[cx, 2.05, z1]} s={[doorW, 0.1, 0.15]} c={wall} />
      {/* awning + sign */}
      <Box p={[cx, 2.35, z1 + 0.35]} s={[w + 0.2, 0.18, 0.9]} c="#e11d48" />
      <Box p={[cx, 2.9, z1 - 0.05]} s={[w - 1.2, 0.7, 0.12]} c="#fff7ed" />
      <Html position={[cx, 2.9, z1 + 0.05]} center zIndexRange={[5, 0]}>
        <div style={{ pointerEvents: 'none', textAlign: 'center', whiteSpace: 'nowrap' }}>
          <div style={{ fontSize: 15, fontWeight: 900, letterSpacing: 1.5, color: '#be123c' }}>ALPHA for BABY</div>
          <div style={{ fontSize: 10.5, fontWeight: 600, color: '#0f172a' }}>alphaforbaby.com · החנות</div>
        </div>
      </Html>
      {/* shelves along the walls, counter with a register */}
      {shelf(cx - 2.6, z0 + 0.5)}
      {shelf(cx - 0.6, z0 + 0.5)}
      {shelf(cx + 1.4, z0 + 0.5)}
      {shelf(cx - w / 2 + 0.5, -0.8, Math.PI / 2)}
      {shelf(cx - w / 2 + 0.5, 1.0, Math.PI / 2)}
      <Box p={[cx + 2.3, 0.5, -1.4]} s={[2.4, 1.0, 0.7]} c="#7c5a3a" />
      <Box p={[cx + 2.6, 1.18, -1.4]} s={[0.5, 0.36, 0.4]} c="#111827" e={0.2} />
      <Box p={[cx - 1.1, 0.3, 0.9]} s={[1.0, 0.6, 1.0]} c="#fda4af" />
      <RoomLabel p={[cx, 3.7, z0]} title="החנות — Alpha for Baby"
        sub={liveCount > 0 ? `${liveCount} מבקרים עכשיו` : 'אין מבקרים כרגע'} />
      <Tree x={cx - w / 2 - 0.9} z={z1 + 0.6} s={0.8} />
      <Tree x={cx + w / 2 + 0.9} z={z1 + 0.6} s={0.8} />
    </group>
  );
}

function VisitorFigure({ v, now, target, index }: { v: Visitor; now: number; target: V2; index: number }) {
  const ref = useRef<Group>(null);
  const body = useRef<Group>(null);
  const path = useRef<V2[]>([]);
  const last = useRef<V2 | null>(null);
  const celebrating = v.stage === 'purchased';
  const phase = useMemo(() => Math.random() * Math.PI * 2, []);
  const tmp = useMemo(() => new Vector3(), []);
  const src = v.source || 'direct';
  const col = SOURCE_COLOR[src] ?? '#94a3b8';
  const inside = target[1] < STORE_Z1 - 0.2;
  useEffect(() => {
    const g = ref.current;
    if (!g) return;
    if (!last.current) {                       // newcomer walks in from the street
      g.position.set(STREET_SPAWN[0], 0, STREET_SPAWN[1]);
      path.current = [[target[0], STREET_SPAWN[1] - 0.4], ...(inside ? [STORE_DOOR] : []), target];
      if (inside) path.current = [[STORE_DOOR[0], STORE_Z1 + 1.6], STORE_DOOR, target];
    } else if (last.current[0] !== target[0] || last.current[1] !== target[1]) {
      const wasInside = last.current[1] < STORE_Z1 - 0.2;
      path.current = inside && !wasInside ? [[STORE_DOOR[0], STORE_Z1 + 1.0], STORE_DOOR, target]
        : !inside && wasInside ? [STORE_DOOR, target] : [target];
    }
    last.current = target;
  }, [target, inside]);
  useFrame(({ clock }, dt) => {
    const g = ref.current;
    if (!g || !body.current) return;
    const t = clock.getElapsedTime() + phase;
    let walking = false;
    const next = path.current[0];
    if (next) {
      tmp.set(next[0] - g.position.x, 0, next[1] - g.position.z);
      const dist = tmp.length();
      const step = Math.min(dist, 2.0 * Math.min(dt, 0.05));
      if (dist < 0.05) path.current.shift();
      else {
        tmp.normalize();
        g.position.x += tmp.x * step;
        g.position.z += tmp.z * step;
        g.rotation.y = Math.atan2(tmp.x, tmp.z);
        walking = true;
      }
    } else {
      g.rotation.y = inside ? (v.stage === 'checkout' || celebrating ? Math.PI : Math.PI) : Math.PI;
    }
    body.current.position.y = celebrating && !walking ? Math.abs(Math.sin(t * 7)) * 0.35
      : Math.abs(Math.sin(t * (walking ? 9 : 1.1))) * (walking ? 0.07 : 0.012);
    body.current.rotation.y = celebrating && !walking ? t * 4 : 0;
  });
  const ageMin = Math.max(0, Math.round((now - v.first_seen) / 60));
  return (
    <group ref={ref}>
      <group ref={body}>
        <mesh position={[0, 0.5, 0]} castShadow>
          <capsuleGeometry args={[0.2, 0.42, 6, 12]} />
          <meshStandardMaterial color={col} />
        </mesh>
        <mesh position={[0, 1.04, 0]} castShadow>
          <sphereGeometry args={[0.2, 16, 16]} />
          <meshStandardMaterial color="#f1d3b0" />
        </mesh>
        {celebrating && (
          <mesh position={[0, 1.4, 0]}><coneGeometry args={[0.14, 0.3, 10]} /><meshStandardMaterial color="#fbbf24" /></mesh>
        )}
      </group>
      <mesh position={[0, 0.02, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[0.3, 0.4, 32]} />
        <meshBasicMaterial color={celebrating ? '#fbbf24' : col} />
      </mesh>
      <Html position={[0, 1.7 + (index % 2) * 0.0, 0]} center zIndexRange={[9, 0]}>
        <div dir="rtl" style={{ pointerEvents: 'none', whiteSpace: 'nowrap', textAlign: 'center',
          background: celebrating ? '#fef3c7' : 'rgba(255,255,255,0.95)', color: '#0f172a', borderRadius: 8,
          padding: '1px 7px', boxShadow: '0 1px 4px rgba(0,0,0,.3)', outline: `2px solid ${col}` }}>
          <div style={{ fontSize: 11, fontWeight: 800 }}>
            לקוח · מגיע מ-<span style={{ color: col }}>{SOURCE_LABEL[src] ?? src}</span>{v.country ? ` ${flagOf(v.country)} ${v.country}` : ''}
          </div>
          <div style={{ fontSize: 10.5, fontWeight: 500 }}>
            {STAGE_LABEL[v.stage]}{celebrating && v.total ? ` · $${v.total}` : ''}{!celebrating && ageMin > 0 ? ` · ${ageMin} ד׳` : ''}
          </div>
        </div>
      </Html>
    </group>
  );
}

/** Slots: newcomers line up outside the door, everyone else browses inside; buyers go to the counter. */
function visitorTargets(visitors: Visitor[], nowS: number): Map<string, V2> {
  const out = new Map<string, V2>();
  const sorted = [...visitors].sort((a, b) => a.first_seen - b.first_seen);
  let q = 0, shelf = 0, counter = 0;
  for (const v of sorted) {
    if (v.stage === 'purchased') { out.set(v.id, COUNTER_SPOTS[counter++ % COUNTER_SPOTS.length]); continue; }
    if (v.stage === 'checkout' || v.stage === 'cart') { out.set(v.id, COUNTER_SPOTS[counter++ % COUNTER_SPOTS.length]); continue; }
    const waiting = v.stage === 'browsing' && nowS - v.first_seen < QUEUE_WINDOW_S;
    if (waiting) { out.set(v.id, [QUEUE_START[0] + (q % 2 ? 0.55 : -0.05), QUEUE_START[1] + Math.floor(q / 2) * 0.75]); q += 1; }
    else out.set(v.id, SHELF_SPOTS[shelf++ % SHELF_SPOTS.length]);
  }
  return out;
}

// ── Agents ────────────────────────────────────────────────────────────────────

function AgentFigure({
  agent, state, target, face, bubble, selected, needsYou, onSelect,
}: {
  agent: AgentPublic; state: AgentState; target: V2; face?: V2; bubble?: string;
  selected: boolean; needsYou: boolean; onSelect: () => void;
}) {
  const ref = useRef<Group>(null);
  const body = useRef<Group>(null);
  const path = useRef<V2[]>([]);
  const lastTarget = useRef<V2 | null>(null);
  const phase = useMemo(() => Math.random() * Math.PI * 2, []);
  const tmp = useMemo(() => new Vector3(), []);

  useEffect(() => {
    const g = ref.current;
    if (!g) return;
    if (!lastTarget.current) {           // first render: appear in place, no walk
      g.position.set(target[0], 0, target[1]);
    } else if (lastTarget.current[0] !== target[0] || lastTarget.current[1] !== target[1]) {
      path.current = pathBetween([g.position.x, g.position.z], target);
    }
    lastTarget.current = target;
  }, [target]);

  useFrame(({ clock }, dt) => {
    const g = ref.current;
    if (!g || !body.current) return;
    const t = clock.getElapsedTime() + phase;
    let walking = false;
    const next = path.current[0];
    if (next) {
      tmp.set(next[0] - g.position.x, 0, next[1] - g.position.z);
      const dist = tmp.length();
      const step = Math.min(dist, 2.4 * Math.min(dt, 0.05));
      if (dist < 0.05) path.current.shift();
      else {
        tmp.normalize();
        g.position.x += tmp.x * step;
        g.position.z += tmp.z * step;
        g.rotation.y = Math.atan2(tmp.x, tmp.z);
        walking = true;
      }
    } else {
      g.rotation.y = state === 'meeting' ? Math.atan2(6.3 - g.position.x, 2.95 - g.position.z)
        : face ? Math.atan2(face[0] - g.position.x, face[1] - g.position.z) : Math.PI;
    }
    const amp = walking ? 0.08 : state === 'gym' ? 0.12 : state === 'speaking' ? 0.07 : 0.015;
    const speed = walking ? 10 : state === 'gym' ? 9 : state === 'speaking' ? 6 : 1.2;
    body.current.position.y = Math.abs(Math.sin(t * speed)) * amp - (state === 'meeting' && !walking ? 0.12 : 0);
  });

  const col = colorFor(agent.role);
  return (
    <group ref={ref}>
      <group
        ref={body}
        onClick={(e) => { e.stopPropagation(); onSelect(); }}
        onPointerOver={() => { document.body.style.cursor = 'pointer'; }}
        onPointerOut={() => { document.body.style.cursor = 'auto'; }}
      >
        <mesh position={[0, 0.5, 0]} castShadow>
          <capsuleGeometry args={[0.22, 0.45, 6, 12]} />
          <meshStandardMaterial color={col} />
        </mesh>
        <mesh position={[0, 1.08, 0]} castShadow>
          <sphereGeometry args={[0.21, 16, 16]} />
          <meshStandardMaterial color="#f3d9b8" />
        </mesh>
      </group>
      <mesh position={[0, 0.02, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[0.32, 0.42, 32]} />
        <meshBasicMaterial color={STATE_COLOR[state]} />
      </mesh>
      {selected && (
        <mesh position={[0, 0.03, 0]} rotation={[-Math.PI / 2, 0, 0]}>
          <ringGeometry args={[0.5, 0.56, 32]} />
          <meshBasicMaterial color="#ffffff" />
        </mesh>
      )}
      <Html position={[0, 1.65, 0]} center zIndexRange={selected ? [20, 11] : [10, 0]}>
        <div dir="auto" style={{
          pointerEvents: 'none', display: 'flex', flexDirection: 'column-reverse', alignItems: 'center',
          whiteSpace: 'nowrap',
        }}>
          <div style={{
            background: 'rgba(255,255,255,0.94)', color: '#0f172a', borderRadius: 8, padding: '1px 7px',
            boxShadow: '0 1px 4px rgba(0,0,0,.3)', textAlign: 'center',
            outline: selected ? '2px solid #0ea5e9' : 'none',
          }}>
            <div style={{ fontSize: 11, fontWeight: 800, letterSpacing: 0.6, display: 'flex', gap: 5, alignItems: 'center', justifyContent: 'center' }}>
              <span style={{ width: 7, height: 7, borderRadius: 9, background: STATE_COLOR[state], display: 'inline-block' }} />
              {needsYou && <span style={{ color: '#d97706' }}>⚠</span>}
              {agent.name.toUpperCase()}
            </div>
            <div style={{
              fontSize: 11, fontWeight: 500, color: '#020617', maxWidth: 140,
              overflow: 'hidden', textOverflow: 'ellipsis',
            }}>
              {selected ? `${agent.role} · ${STATE_LABEL[state]}` : STATE_LABEL[state]}
            </div>
          </div>
          {bubble && (
            <div style={{
              marginBottom: 4, width: 180, whiteSpace: 'normal', background: '#ffffff', color: '#000000', fontWeight: 500,
              padding: '4px 8px', borderRadius: 10, fontSize: 11.5, lineHeight: 1.3,
              boxShadow: '0 1px 4px rgba(0,0,0,.3)',
            }}>
              {bubble.length > 90 ? bubble.slice(0, 90) + '…' : bubble}
            </div>
          )}
        </div>
      </Html>
    </group>
  );
}

export function OfficeScene({
  agents, stateOf, bubbleOf, needsYouOf, talkToOf, selectedId, onSelect, night, visitors = [],
}: {
  visitors?: Visitor[];
  agents: AgentPublic[];
  talkToOf: (a: AgentPublic) => string | undefined;
  stateOf: (a: AgentPublic) => AgentState;
  bubbleOf: (a: AgentPublic) => string | undefined;
  needsYouOf: (a: AgentPublic) => boolean;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  night: boolean;
}) {
  const layout = useMemo(() => layoutOf(agents), [agents]);
  const nowS = Date.now() / 1000;
  const vTargets = visitorTargets(visitors, nowS);
  // Stable slot assignment per room so two agents never stand on the same spot.
  let gymI = 0;
  let meetI = 0;
  const states = agents.map(stateOf);
  const idx = new Map(agents.map((a, i) => [a.agent_id, i]));
  // Who walks over to whom: only a seated speaker visits, and only a seated person gets visited,
  // so two people mentioning each other never swap places mid-corridor.
  const visiting = new Map<string, string>();      // visitor id → partner id
  const visited = new Set<string>();
  agents.forEach((a, i) => {
    const pid = talkToOf(a);
    const pi = pid ? idx.get(pid) : undefined;
    if (pid === undefined || pi === undefined || pid === a.agent_id) return;
    if (states[i] !== 'speaking' || states[pi] === 'gym' || states[pi] === 'meeting') return;
    if (visited.has(a.agent_id) || visiting.has(pid)) return;
    visiting.set(a.agent_id, pid);
    visited.add(pid);
  });
  const visitorsAt = new Map<string, number>();
  const targets = agents.map((a, i): V2 => {
    const s = states[i];
    if (s === 'gym') return GYM_SLOTS[gymI++ % GYM_SLOTS.length];
    if (s === 'meeting') return MEET_SLOTS[meetI++ % MEET_SLOTS.length];
    const pid = visiting.get(a.agent_id);
    if (pid) {
      const spot = visitSpot(layout.seat.get(pid)!, layout.office.has(pid));
      const n = visitorsAt.get(pid) ?? 0;
      visitorsAt.set(pid, n + 1);
      return [spot[0], spot[1] + n * 0.5];
    }
    return layout.seat.get(a.agent_id)!;
  });
  const faceOf = (a: AgentPublic, i: number): V2 | undefined => {
    const pid = visiting.get(a.agent_id);
    if (pid) return layout.seat.get(pid);
    if (visited.has(a.agent_id)) {
      const visitor = [...visiting.entries()].find(([, p]) => p === a.agent_id)?.[0];
      const vi = visitor ? idx.get(visitor) : undefined;
      if (vi !== undefined) return targets[vi];
    }
    return undefined;
  };
  return (
    <Canvas shadows orthographic camera={{ position: [17, 14, 14.5], zoom: 24, near: 0.1, far: 200 }}
      onPointerMissed={() => onSelect(null)}>
      <color attach="background" args={[night ? '#0b1220' : '#a7c46a']} />
      <ambientLight intensity={night ? 0.35 : 0.8} />
      <directionalLight position={[8, 16, 6]} intensity={night ? 0.35 : 1.1} castShadow
        shadow-mapSize={[1024, 1024]} />
      {night && <pointLight position={[-3, 3, 0]} intensity={8} distance={14} color="#fde68a" />}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.25, 0]} receiveShadow>
        <planeGeometry args={[60, 60]} />
        <meshStandardMaterial color={night ? '#2f3d1f' : '#9bbb59'} />
      </mesh>
      <Building agents={agents} layout={layout} />
      <StoreBuilding liveCount={visitors.filter((v) => v.stage !== 'purchased').length} />
      {visitors.map((v, i) => (
        <VisitorFigure key={v.id} v={v} now={nowS} target={vTargets.get(v.id)!} index={i} />
      ))}
      {agents.map((a, i) => (
        <AgentFigure
          key={a.agent_id}
          agent={a}
          state={stateOf(a)}
          target={targets[i]}
          face={faceOf(a, i)}
          bubble={bubbleOf(a)}
          selected={selectedId === a.agent_id}
          needsYou={needsYouOf(a)}
          onSelect={() => onSelect(a.agent_id)}
        />
      ))}
      <OrbitControls enablePan minZoom={12} maxZoom={90} target={[3, 0, 0.5]}
        minPolarAngle={Math.PI / 7} maxPolarAngle={Math.PI / 2.4} />
    </Canvas>
  );
}
