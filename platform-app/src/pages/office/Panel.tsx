import { useState } from 'react';
import type { AgentPublic, AgentState, Capability, InboxItem, Msg, Ticket } from './types';
import { STATE_COLOR, STATE_LABEL, colorFor, timeAgo } from './types';

export type Tab = 'needs' | 'team' | 'board' | 'feed';

const KIND_TAG: Record<InboxItem['kind'], { label: string; cls: string }> = {
  social_draft: { label: 'להחליט · פוסט', cls: 'bg-red-800 text-white' },
  proposal: { label: 'להחליט · Shopify', cls: 'bg-red-800 text-white' },
  blocker: { label: 'חסם', cls: 'bg-amber-700 text-white' },
  missing_tool: { label: 'חסר כלי', cls: 'bg-amber-600 text-white' },
  connection: { label: 'חיבור', cls: 'bg-slate-600 text-white' },
};

function Avatar({ name, role }: { name: string; role?: string }) {
  return (
    <span className="inline-grid h-5 w-5 place-items-center rounded-full text-[10px] font-bold text-white"
      style={{ background: role ? colorFor(role) : '#64748b' }}>
      {name.slice(0, 1).toUpperCase()}
    </span>
  );
}

function lastResultText(r?: Record<string, unknown>): string {
  if (!r || !Object.keys(r).length) return '';
  const pick = r.summary ?? r.text ?? r.result ?? r.status;
  return typeof pick === 'string' ? pick : JSON.stringify(r).slice(0, 220);
}

export function Panel(props: {
  tab: Tab; setTab: (t: Tab) => void;
  agents: AgentPublic[]; stateOf: (a: AgentPublic) => AgentState;
  caps: Capability[]; inbox: InboxItem[]; tickets: Ticket[]; msgs: Msg[];
  selectedId: string | null; setSelectedId: (id: string | null) => void;
  onDecide: (item: InboxItem, decision: 'approve' | 'hold' | 'reject', feedback?: string) => Promise<string>;
  onInstructItem: (item: InboxItem, text: string) => Promise<string>;
  onInstructAgent: (agent: AgentPublic, text: string) => Promise<string>;
}) {
  const { tab, setTab, agents, stateOf, caps, inbox, tickets, msgs, selectedId, setSelectedId } = props;
  const [openItem, setOpenItem] = useState<string | null>(null);
  const [instr, setInstr] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const roleOf = (name: string) => agents.find((a) => a.name === name)?.role;
  const decideItems = inbox.filter((i) => i.decide);
  const infoItems = inbox.filter((i) => !i.decide);
  const item = inbox.find((i) => i.id === openItem) ?? null;
  const selected = agents.find((a) => a.agent_id === selectedId) ?? null;
  const openTickets = tickets.filter((t) => t.status !== 'done');

  async function run(p: Promise<string>) {
    setBusy(true); setNotice('');
    try { setNotice(await p); } catch (e) { setNotice(`⚠️ ${String(e)}`); } finally { setBusy(false); }
  }

  const tabs: { id: Tab; label: string; badge?: number }[] = [
    { id: 'needs', label: 'צריך אותך', badge: decideItems.length + infoItems.length },
    { id: 'team', label: 'צוות' },
    { id: 'board', label: 'לוח', badge: openTickets.length },
    { id: 'feed', label: 'פיד' },
  ];

  const DecisionButtons = ({ it }: { it: InboxItem }) => (
    <div className="mt-2 flex flex-wrap gap-1.5">
      <button disabled={busy} onClick={() => run(props.onDecide(it, 'approve'))}
        className="rounded-md bg-green-700 px-3 py-1 text-xs font-semibold text-white disabled:opacity-40">אשר</button>
      <button disabled={busy} onClick={() => run(props.onDecide(it, 'hold'))}
        className="rounded-md bg-amber-200 px-3 py-1 text-xs font-semibold text-amber-900 disabled:opacity-40">השהה</button>
      <button disabled={busy} onClick={() => run(props.onDecide(it, 'reject', instr))}
        className="rounded-md bg-gray-200 px-3 py-1 text-xs font-semibold text-gray-800 disabled:opacity-40">החזר ל-{it.agent}</button>
      <button disabled={busy} onClick={() => setOpenItem(it.id)}
        className="rounded-md border border-red-300 px-3 py-1 text-xs font-semibold text-red-200">הנחיה</button>
    </div>
  );

  return (
    <aside dir="rtl" className="flex w-full flex-col overflow-hidden border-t border-gray-800 bg-gray-900 md:w-[400px] md:border-l md:border-t-0">
      <div className="flex items-center gap-1 border-b border-gray-800 p-2">
        {tabs.map((t) => (
          <button key={t.id} onClick={() => { setTab(t.id); setOpenItem(null); }}
            className={`flex items-center gap-1 rounded-md px-3 py-1.5 text-sm ${tab === t.id ? 'bg-gray-700 text-white' : 'text-gray-300 hover:bg-gray-800'}`}>
            {t.label}
            {!!t.badge && <span className="rounded-full bg-red-800 px-1.5 text-[10px] text-white">{t.badge}</span>}
          </button>
        ))}
      </div>

      <div className="flex-1 space-y-2 overflow-y-auto p-3">
        {/* ── Needs you ── */}
        {tab === 'needs' && !item && (
          <>
            <div className="text-xs font-bold tracking-wide text-gray-300">להחליט ({decideItems.length})</div>
            {decideItems.length === 0 && <div className="text-xs text-gray-300">אין כרגע החלטות שמחכות לך.</div>}
            {decideItems.map((it) => (
              <div key={it.id} className="rounded-lg border-r-4 border-red-700 bg-gray-800/70 p-3">
                <div className="flex items-center gap-2">
                  <span className={`rounded px-1.5 py-0.5 text-[10px] font-bold ${KIND_TAG[it.kind].cls}`}>{KIND_TAG[it.kind].label}</span>
                  <span className="mr-auto text-[11px] text-gray-300">{timeAgo(it.created_at)}</span>
                </div>
                <button onClick={() => setOpenItem(it.id)} className="mt-1 block text-right text-sm font-semibold text-gray-100 hover:underline" dir="auto">{it.title}</button>
                <div className="mt-1 flex items-center gap-1.5 text-xs text-gray-300">
                  <Avatar name={it.agent} role={roleOf(it.agent)} /> {it.agent} · {it.context}
                </div>
                <DecisionButtons it={it} />
              </div>
            ))}
            <div className="pt-2 text-xs font-bold tracking-wide text-gray-300">חסמים וחיבורים ({infoItems.length})</div>
            {infoItems.map((it) => (
              <button key={it.id} onClick={() => setOpenItem(it.id)} className="block w-full rounded-lg bg-gray-800/40 p-2.5 text-right">
                <div className="flex items-center gap-2">
                  <span className={`rounded px-1.5 py-0.5 text-[10px] font-bold ${KIND_TAG[it.kind].cls}`}>{KIND_TAG[it.kind].label}</span>
                  <span className="text-xs text-gray-300"><Avatar name={it.agent} role={roleOf(it.agent)} /> {it.agent}</span>
                </div>
                <div className="mt-1 text-xs text-gray-200" dir="auto">{it.title}</div>
                <div className="text-[11px] text-gray-300" dir="auto">{it.summary}</div>
              </button>
            ))}
          </>
        )}
        {tab === 'needs' && item && (
          <div className="space-y-2 text-sm">
            <button onClick={() => setOpenItem(null)} className="text-xs font-bold tracking-wide text-red-300">→ כל העבודה</button>
            <div className="font-mono text-[13px] font-bold uppercase text-gray-100" dir="auto">{item.title}</div>
            <dl className="grid grid-cols-[70px_1fr] gap-y-1 text-xs">
              <dt className="text-gray-300">סטטוס</dt><dd className="text-gray-200">{item.decide ? 'ממתין להחלטה שלך' : item.status}</dd>
              <dt className="text-gray-300">הקשר</dt><dd className="text-gray-200">{item.context}</dd>
              <dt className="text-gray-300">מאת</dt><dd className="text-gray-200">{item.agent}</dd>
              <dt className="text-gray-300">תאריך</dt><dd className="text-gray-200">{item.created_at ? new Date(item.created_at).toLocaleString('he-IL') : '—'}</dd>
            </dl>
            {item.summary && <div><div className="text-xs font-bold text-gray-300">סיכום</div><div className="text-gray-200" dir="auto">{item.summary}</div></div>}
            {item.body && <div className="whitespace-pre-wrap rounded bg-gray-950 p-2 text-gray-200" dir="auto">{item.body}</div>}
            {item.media_url && (/\.(mp4|mov|webm)(\?|$)/i.test(item.media_url)
              ? <video src={item.media_url} controls className="max-h-56 w-full rounded" />
              : <img src={item.media_url} alt="" className="max-h-56 w-full rounded object-contain" />)}
            {item.link && <a href={item.link} target="_blank" rel="noreferrer" className="text-xs text-sky-400 underline">{item.link}</a>}
            {item.error && <div className="rounded bg-red-950/60 p-2 text-xs text-red-200">ניסיון פרסום נכשל: {item.error}</div>}
            {item.decide && <><div className="text-xs font-bold text-gray-300">ההחלטה שלך</div><DecisionButtons it={item} /></>}
            <div className="pt-2 text-xs font-bold text-gray-300">הנחיה ל-{item.agent}</div>
            <textarea dir="auto" rows={3} value={instr} onChange={(e) => setInstr(e.target.value)}
              placeholder="מה לשנות / מה לעשות?" className="w-full rounded-md border border-gray-700 bg-gray-950 p-2 text-sm text-gray-100 outline-none focus:border-sky-500" />
            <button disabled={busy || !instr.trim()} onClick={() => run(props.onInstructItem(item, instr).then((r) => { setInstr(''); return r; }))}
              className="rounded-md bg-red-800 px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-40">שלח הנחיה</button>
          </div>
        )}

        {/* ── Team ── */}
        {tab === 'team' && agents.map((a) => {
          const s = stateOf(a);
          const cap = caps.find((c) => c.agent === a.name);
          const open = selectedId === a.agent_id;
          return (
            <div key={a.agent_id} className={`rounded-lg border p-3 ${open ? 'border-white/50 bg-gray-800' : 'border-gray-800 bg-gray-900'}`}>
              <button onClick={() => setSelectedId(open ? null : a.agent_id)} className="block w-full text-right">
                <div className="flex items-center gap-2">
                  <span className="h-2.5 w-2.5 rounded-full" style={{ background: STATE_COLOR[s] }} />
                  <span className="font-semibold text-gray-100">{a.name}</span>
                  <span className="mr-auto text-xs" style={{ color: STATE_COLOR[s] }}>{STATE_LABEL[s]}</span>
                </div>
                <div className="font-mono text-[11px] text-gray-300">{a.role}</div>
              </button>
              {open && (
                <div className="mt-2 space-y-2 border-t border-gray-700 pt-2 text-xs">
                  <div><div className="font-bold tracking-wide text-gray-300">עובד על</div>
                    <div className="text-gray-200" dir="auto">{a.task || `אין כרגע משימה של ${a.name} בתור או בלוח.`}</div></div>
                  {lastResultText(a.last_result) && <div><div className="font-bold tracking-wide text-gray-300">תוצאה אחרונה</div>
                    <div className="text-gray-300" dir="auto">{lastResultText(a.last_result)}</div></div>}
                  {cap && <div><div className="font-bold tracking-wide text-gray-300">חיבורים</div>
                    {cap.connected.length > 0 && <div className="text-green-300/80">✓ {cap.connected.join(', ')}</div>}
                    {cap.not_connected.map((n) => <div key={n.tool} className="text-red-300">✗ {n.tool} — {n.missing_env.join(', ') || n.error}</div>)}
                    {cap.missing_tools.map((m) => <div key={m.need} className="text-amber-300">🧰 אין כלי ל: {m.need}<div className="text-gray-300">{m.fix}</div></div>)}
                  </div>}
                </div>
              )}
            </div>
          );
        })}

        {/* ── Board ── */}
        {tab === 'board' && (
          <>
            {(['doing', 'todo', 'blocked', 'done'] as const).map((st) => {
              const list = tickets.filter((t) => t.status === st).slice(0, st === 'done' ? 5 : 30);
              if (!list.length) return null;
              const label = { doing: 'בעבודה', todo: 'לביצוע', blocked: 'חסום', done: 'הושלם לאחרונה' }[st];
              return (
                <div key={st}>
                  <div className="mb-1 text-xs font-bold tracking-wide text-gray-300">{label} ({list.length})</div>
                  {list.map((t) => (
                    <div key={t.id} className="mb-1.5 rounded-lg bg-gray-800/60 p-2">
                      <div className="flex items-center gap-2 text-[10px]">
                        <span className="rounded bg-gray-700 px-1.5 py-0.5 font-bold text-gray-200">משימה</span>
                        <span className={t.priority === 'critical' || t.priority === 'high' ? 'text-red-300' : 'text-gray-300'}>{t.priority}</span>
                        <span className="mr-auto text-gray-300">{t.due_at ? `יעד ${new Date(t.due_at).toLocaleDateString('he-IL')}` : ''}</span>
                      </div>
                      <div className="mt-1 text-xs text-gray-100" dir="auto">{t.title}</div>
                      {t.assignee && <div className="mt-1 text-[11px] text-gray-300"><Avatar name={t.assignee} role={roleOf(t.assignee)} /> {t.assignee}</div>}
                    </div>
                  ))}
                </div>
              );
            })}
            {tickets.length === 0 && <div className="text-xs text-gray-300">הלוח ריק.</div>}
          </>
        )}

        {/* ── Feed ── */}
        {tab === 'feed' && [...msgs].reverse().slice(0, 60).map((m, i) => (
          <div key={i} className="rounded-lg bg-gray-800/60 p-2">
            <div className="text-[11px] text-gray-300"><span className="font-semibold text-gray-300">{m.name}</span> · {timeAgo(m.ts)}</div>
            <div dir="auto" className="text-sm text-gray-200">{m.text}</div>
          </div>
        ))}
      </div>

      <div className="border-t border-gray-800 p-3">
        <div className="mb-1 flex items-center gap-2 text-xs font-bold tracking-wide text-red-300">
          תן הוראה
          <select value={selectedId ?? ''} onChange={(e) => setSelectedId(e.target.value || null)}
            className="mr-auto rounded bg-gray-950 px-1 py-0.5 text-xs text-gray-200">
            <option value="">— בחר סוכן —</option>
            {agents.map((a) => <option key={a.agent_id} value={a.agent_id}>{a.name}</option>)}
          </select>
        </div>
        {tab !== 'needs' || !item ? (
          <>
            <textarea dir="auto" rows={2} value={instr} onChange={(e) => setInstr(e.target.value)} placeholder="מה לעשות?"
              className="w-full rounded-md border border-gray-700 bg-gray-950 p-2 text-sm text-gray-100 outline-none focus:border-sky-500" />
            <div className="mt-2 flex items-center gap-2">
              <button disabled={busy || !instr.trim() || !selected}
                onClick={() => selected && run(props.onInstructAgent(selected, instr).then((r) => { setInstr(''); return r; }))}
                className="rounded-md bg-red-800 px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-40">
                {selected ? `שלח ל-${selected.name}` : 'בחר סוכן'}
              </button>
              <span className="text-xs text-gray-300">{notice}</span>
            </div>
          </>
        ) : <span className="text-xs text-gray-300">{notice}</span>}
      </div>
    </aside>
  );
}
