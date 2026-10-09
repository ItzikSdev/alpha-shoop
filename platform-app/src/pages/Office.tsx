import { useCallback, useEffect, useMemo, useState } from 'react';
import { apiGet, apiPost } from '../api/client';
import { OfficeScene } from './office/Scene';
import { Panel, type Tab } from './office/Panel';
import type { AgentPublic, AgentState, Capability, InboxItem, Meeting, Msg, Ticket, Visitor } from './office/types';

const SPEAKING_WINDOW_MS = 90_000;
const MEETING_WINDOW_MS = 15 * 60_000;

// Tel Aviv — real-time weather from Open-Meteo (free, no key), like the reference office.
const WEATHER_URL =
  'https://api.open-meteo.com/v1/forecast?latitude=32.08&longitude=34.78&current=temperature_2m,weather_code,is_day';
function weatherEmoji(code: number, day: boolean): string {
  if (code === 0) return day ? '☀️' : '🌙';
  if (code <= 3) return day ? '⛅' : '☁️';
  if (code <= 48) return '🌫️';
  if (code <= 67 || (code >= 80 && code <= 82)) return '🌧️';
  if (code <= 77) return '🌨️';
  return '⛈️';
}

function useClock() {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => { const t = setInterval(() => setNow(new Date()), 15_000); return () => clearInterval(t); }, []);
  return now;
}

export function Office() {
  const [agents, setAgents] = useState<AgentPublic[]>([]);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [caps, setCaps] = useState<Capability[]>([]);
  const [inbox, setInbox] = useState<InboxItem[]>([]);
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [visitors, setVisitors] = useState<Visitor[]>([]);
  const [online, setOnline] = useState(true);
  const [weather, setWeather] = useState<{ t: number; code: number; day: boolean } | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>('needs');
  const now = useClock();

  const load = useCallback(async () => {
    const [org, m, c, ib, tk, mt] = await Promise.allSettled([
      apiGet<{ roster: AgentPublic[] }>('/org'),
      apiGet<{ messages: Msg[] }>('/org/messages?limit=80'),
      apiGet<Capability[]>('/org/capabilities'),
      apiGet<{ items: InboxItem[] }>('/org/inbox'),
      apiGet<{ tickets: Ticket[] }>('/org/tickets'),
      apiGet<Meeting[]>('/org/meetings?limit=5'),
    ]);
    if (org.status === 'fulfilled') setAgents(org.value.roster);
    if (m.status === 'fulfilled') setMsgs(m.value.messages);
    if (c.status === 'fulfilled') setCaps(c.value);
    if (ib.status === 'fulfilled') setInbox(ib.value.items);
    if (tk.status === 'fulfilled') setTickets(tk.value.tickets);
    if (mt.status === 'fulfilled') setMeetings(mt.value);
    setOnline(org.status === 'fulfilled');
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 8_000);
    return () => clearInterval(t);
  }, [load]);

  // Real shoppers right now (anonymous: source + country + stage). Fast poll — it's the live part.
  useEffect(() => {
    let alive = true;
    if (new URLSearchParams(window.location.search).has('demoVisitors')) {   // ?demoVisitors → preview with fake shoppers
      const n = Date.now() / 1000;
      setVisitors([
        { id: 'd1', stage: 'browsing', source: 'facebook', country: 'US', first_seen: n - 10, last_seen: n },
        { id: 'd2', stage: 'browsing', source: 'instagram', country: 'IL', first_seen: n - 25, last_seen: n },
        { id: 'd3', stage: 'browsing', source: 'google', country: 'DE', first_seen: n - 40, last_seen: n },
        { id: 'd4', stage: 'product', source: 'tiktok', country: 'GB', first_seen: n - 400, last_seen: n },
        { id: 'd5', stage: 'checkout', source: 'direct', country: 'US', first_seen: n - 600, last_seen: n },
        { id: 'd6', stage: 'purchased', source: 'facebook', country: 'CA', first_seen: n - 700, last_seen: n, total: 38.5 },
      ]);
      return () => { alive = false; };
    }
    const get = () => apiGet<{ visitors: Visitor[] }>('/visitors/live')
      .then((r) => { if (alive) setVisitors(r.visitors ?? []); }).catch(() => undefined);
    get();
    const t = setInterval(get, 4_000);
    return () => { alive = false; clearInterval(t); };
  }, []);

  useEffect(() => {
    let alive = true;
    const get = () => fetch(WEATHER_URL).then((r) => r.json()).then((j) => {
      if (alive && j?.current) setWeather({ t: j.current.temperature_2m, code: j.current.weather_code, day: !!j.current.is_day });
    }).catch(() => undefined);
    get();
    const t = setInterval(get, 15 * 60_000);
    return () => { alive = false; clearInterval(t); };
  }, []);

  const lastMsgByName = useMemo(() => {
    const map = new Map<string, Msg>();
    for (const x of msgs) map.set(x.name, x);
    return map;
  }, [msgs]);
  const inMeeting = useMemo(() => {
    const ids = new Set<string>();
    for (const m of meetings) {
      // The backend also logs one-person "standups" every time a single agent acts; a meeting is
      // only a meeting when at least two people from the roster are in it.
      const here = m.attendees.filter((id) => agents.some((a) => a.agent_id === id));
      if (here.length >= 2 && Date.now() - new Date(m.held_at).getTime() < MEETING_WINDOW_MS) here.forEach((a) => ids.add(a));
    }
    return ids;
  }, [meetings, agents]);

  const needsYouOf = (a: AgentPublic) =>
    inbox.some((i) => i.decide && i.agent === a.name) || caps.find((c) => c.agent === a.name)?.ok === false;

  const stateOf = (a: AgentPublic): AgentState => {
    if (inMeeting.has(a.agent_id)) return 'meeting';
    const last = lastMsgByName.get(a.name);
    if (last && now.getTime() - new Date(last.ts).getTime() < SPEAKING_WINDOW_MS) return 'speaking';
    if (needsYouOf(a)) return 'waiting';
    return a.task ? 'working' : 'gym';
  };
  // Who is the latest message addressed to? No "to" field in the feed, so use the first other
  // agent's name mentioned in the text (word match, case-insensitive).
  const talkToOf = (a: AgentPublic): string | undefined => {
    const text = lastMsgByName.get(a.name)?.text;
    if (!text) return undefined;
    let best: { id: string; at: number } | undefined;
    for (const o of agents) {
      if (o.agent_id === a.agent_id) continue;
      const m = new RegExp(`(^|[^\\p{L}])${o.name}([^\\p{L}]|$)`, 'iu').exec(text);
      if (m && (!best || m.index < best.at)) best = { id: o.agent_id, at: m.index };
    }
    return best?.id;
  };
  const bubbleOf = (a: AgentPublic) => (stateOf(a) === 'speaking' ? lastMsgByName.get(a.name)?.text : undefined);

  const counts = agents.reduce((acc, a) => { acc[stateOf(a)] += 1; return acc; },
    { speaking: 0, working: 0, waiting: 0, meeting: 0, gym: 0 } as Record<AgentState, number>);
  const openTasks = tickets.filter((t) => t.status !== 'done').length;
  const decideCount = inbox.filter((i) => i.decide).length;

  const hour = Number(new Intl.DateTimeFormat('en-GB', { hour: '2-digit', hour12: false, timeZone: 'Asia/Jerusalem' }).format(now));
  const night = weather ? !weather.day : hour < 6 || hour >= 19;
  const clock = new Intl.DateTimeFormat('he-IL', { hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Jerusalem' }).format(now);

  async function onDecide(item: InboxItem, decision: 'approve' | 'hold' | 'reject', feedback = '') {
    const r = await apiPost<Record<string, unknown>>(`/org/inbox/${encodeURIComponent(item.id)}/decide`, { decision, feedback });
    await load();
    const pub = r.publish as { ok?: boolean; error?: string } | undefined;
    if (pub && !pub.ok) return `⚠️ אושר, אבל הפרסום נכשל: ${pub.error}`;
    return { approve: '✅ אושר', hold: '⏸️ הושהה', reject: `↩️ הוחזר ל-${item.agent}` }[decision];
  }
  async function onInstructItem(item: InboxItem, text: string) {
    const r = await apiPost<{ sent_to?: string; error?: string }>(`/org/inbox/${encodeURIComponent(item.id)}/instruct`, { text, agent: item.agent });
    await load();
    return r.error ? `⚠️ ${r.error}` : `✅ נשלח ל-${r.sent_to}`;
  }
  async function onInstructAgent(agent: AgentPublic, text: string) {
    const r = await apiPost<{ assigned_to?: string; error?: string }>('/org/assign', { role: agent.role, task: text, by: 'Itzik' });
    await load();
    return r.error ? `⚠️ ${r.error}` : `✅ נשלח ל-${r.assigned_to}`;
  }

  const chip = 'rounded-full bg-white/90 px-3 py-1 text-xs font-semibold text-slate-800 shadow';
  return (
    <div className="flex h-screen flex-col md:flex-row">
      <div className="relative min-h-[55vh] flex-1">
        <OfficeScene agents={agents} stateOf={stateOf} bubbleOf={bubbleOf} needsYouOf={needsYouOf} talkToOf={talkToOf}
          selectedId={selectedId} onSelect={(id) => { setSelectedId(id); if (id) setTab('team'); }} night={night} visitors={visitors} />

        <div className="pointer-events-none absolute left-3 top-3 flex flex-wrap items-center gap-2" dir="rtl">
          <span className="rounded-lg bg-white/90 px-3 py-1.5 font-mono text-sm font-extrabold tracking-wider text-slate-900 shadow">
            ALPHA HQ <span className={online ? 'text-green-600' : 'text-red-600'}>●</span>
          </span>
          <span className={chip}>{agents.length} בצוות</span>
          <span className={chip}>{clock}</span>
          <span className={chip}>🛍️ {visitors.filter((v) => v.stage !== 'purchased').length} מבקרים בחנות</span>
          {weather && <span className={chip}>{weatherEmoji(weather.code, weather.day)} {Math.round(weather.t)}° תל אביב</span>}
        </div>

        <div className="pointer-events-none absolute bottom-3 left-3 flex gap-4 rounded-xl bg-white/90 px-4 py-2 shadow" dir="rtl">
          {[
            [counts.working + counts.speaking, 'עובדים'],
            [counts.gym, 'בחדר הכושר'],
            [counts.meeting, 'בישיבה'],
            [openTasks, 'משימות פתוחות'],
            [decideCount, 'ממתינים לך'],
          ].map(([n, l]) => (
            <div key={String(l)} className="text-center">
              <div className="font-mono text-lg font-bold text-slate-900">{n}</div>
              <div className="font-mono text-[11px] font-medium tracking-wide text-slate-900">{l}</div>
            </div>
          ))}
        </div>
        {!online && (
          <div className="absolute bottom-20 left-3 rounded bg-red-900/90 px-3 py-2 text-xs text-red-100">
            ה-API לא זמין — מציג נתונים אחרונים
          </div>
        )}
      </div>
      <Panel tab={tab} setTab={setTab} agents={agents} stateOf={stateOf} caps={caps} inbox={inbox}
        tickets={tickets} msgs={msgs} selectedId={selectedId} setSelectedId={setSelectedId}
        onDecide={onDecide} onInstructItem={onInstructItem} onInstructAgent={onInstructAgent} />
    </div>
  );
}
