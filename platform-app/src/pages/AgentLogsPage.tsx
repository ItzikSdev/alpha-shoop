import { useEffect, useRef, useState } from 'react';
import { apiGet } from '../api/client';

interface Msg { ts: string; name: string; role: string; text: string }
interface Resp { messages: Msg[]; count: number }

const COLOR: Record<string, string> = {
  CEO: 'text-amber-300', 'Product Hunter': 'text-sky-300', 'UX & Content': 'text-pink-300',
  'Shopify Developer': 'text-emerald-300', 'Growth Marketer': 'text-violet-300',
  // legacy roles (departed agents)
  CTO: 'text-sky-300', Developer: 'text-emerald-300',
};
const time = (ts: string) => { try { return new Date(ts).toLocaleString(); } catch { return ts; } };

export function AgentLogsPage() {
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [error, setError] = useState('');
  const [live, setLive] = useState(true);
  const bottom = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let alive = true;
    const load = () =>
      apiGet<Resp>('/org/messages?limit=300')
        .then((d) => { if (alive) { setMsgs(d.messages); setError(''); } })
        .catch((e) => alive && setError(String(e)));
    load();
    if (!live) return () => { alive = false; };
    const id = setInterval(load, 4000);
    return () => { alive = false; clearInterval(id); };
  }, [live]);

  useEffect(() => { bottom.current?.scrollIntoView({ behavior: 'smooth' }); }, [msgs.length]);

  return (
    <div className="mx-auto max-w-4xl p-6">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">💬 Agent Logs</h1>
          <p className="text-sm text-gray-500">The team talking to each other — outside the chat. {msgs.length} messages.</p>
        </div>
        <label className="flex items-center gap-2 text-sm text-gray-400">
          <input type="checkbox" checked={live} onChange={(e) => setLive(e.target.checked)} />
          Live
        </label>
      </div>

      {error && <div className="mb-3 rounded border border-rose-800/50 bg-rose-900/15 p-2 text-sm text-rose-300">{error}</div>}

      <div className="space-y-2 rounded-xl border border-gray-800 bg-gray-900/40 p-4">
        {msgs.length === 0 && (
          <p className="py-8 text-center text-sm text-gray-500">No messages yet. They'll appear here as the agents work and talk.</p>
        )}
        {msgs.map((m, i) => (
          <div key={i} className="flex gap-3">
            <div className="w-28 shrink-0 text-right">
              <div className={`text-sm font-semibold ${COLOR[m.role] || 'text-gray-300'}`}>{m.name}</div>
              <div className="text-[10px] text-gray-600">{m.role}</div>
            </div>
            <div className="flex-1 border-l border-gray-800 pl-3">
              <div className="text-[10px] text-gray-600">{time(m.ts)}</div>
              <div className="whitespace-pre-wrap text-sm text-gray-200">{m.text}</div>
            </div>
          </div>
        ))}
        <div ref={bottom} />
      </div>
    </div>
  );
}
