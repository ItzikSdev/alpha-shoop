import { useEffect, useState, useCallback } from 'react';
import { apiGet, apiPost, apiPatch } from '../api/client';

interface Ticket {
  id: string; title: string; description: string; created_by: string;
  assignee: string; status: string; priority: string; source: string;
  due_at: string; overdue?: boolean; store_name?: string; store_url?: string;
}

const COLUMNS = ['todo', 'doing', 'blocked', 'done'];
const COL_LABEL: Record<string, string> = { todo: 'Todo', doing: 'Doing', blocked: 'Blocked', done: 'Done' };
const NEXT: Record<string, string> = { todo: 'doing', doing: 'done', blocked: 'doing', done: 'todo' };
const AGENT_EMOJI: Record<string, string> = { Ava: '👑', Hunter: '🎯', Remy: '🎨', Devon: '🛠️', Max: '📣' };
const PRIO_CLS: Record<string, string> = {
  critical: 'bg-red-900/40 text-red-400 border-red-800',
  high: 'bg-orange-900/40 text-orange-400 border-orange-800',
  medium: 'bg-blue-900/40 text-blue-400 border-blue-800',
  low: 'bg-gray-800 text-gray-500 border-gray-700',
};

function fmtDue(iso: string): string {
  if (!iso) return '';
  return new Date(iso).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

export function TicketsPage() {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);

  const load = useCallback(() => {
    apiGet<{ tickets: Ticket[] }>('/org/tickets')
      .then((r) => setTickets(r.tickets || []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); const t = setInterval(load, 8000); return () => clearInterval(t); }, [load]);

  const move = async (id: string, status: string) => { await apiPatch(`/org/tickets/${id}`, { status: NEXT[status] }); load(); };
  const scan = async () => { setScanning(true); await apiPost('/org/tickets/scan', {}).catch(() => {}); setScanning(false); load(); };

  const open = tickets.filter((t) => t.status !== 'done').length;
  const overdue = tickets.filter((t) => t.overdue).length;

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">🎫 Tickets</h1>
          <p className="text-gray-400 text-sm mt-1">
            Agents open tickets from problems; Ava assigns owner, priority &amp; deadline.
            &nbsp;·&nbsp; {open} open &nbsp;·&nbsp;
            <span className={overdue ? 'text-red-400' : 'text-gray-500'}> {overdue} overdue</span>
          </p>
        </div>
        <button onClick={scan} disabled={scanning}
          className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-medium transition-colors">
          {scanning ? 'Scanning…' : '🔍 Run quality scan'}
        </button>
      </div>

      {loading ? (
        <div className="text-center py-12 text-gray-500">Loading tickets…</div>
      ) : (
        <div className="grid grid-cols-4 gap-4 items-start">
          {COLUMNS.map((col) => {
            const items = tickets.filter((t) => t.status === col);
            return (
              <div key={col} className="rounded-xl bg-gray-950/40 border border-gray-800 p-3 min-h-[120px]">
                <div className="text-xs font-semibold uppercase tracking-wide text-gray-400 mb-3 px-1">
                  {COL_LABEL[col]} <span className="text-gray-600">({items.length})</span>
                </div>
                <div className="space-y-3">
                  {items.map((t) => (
                    <div key={t.id} className="p-4 rounded-xl bg-gray-900 border border-gray-800 hover:border-gray-700 transition-colors">
                      <div className="flex items-center justify-between mb-2">
                        <span className={`px-2 py-0.5 rounded text-xs border font-medium uppercase ${PRIO_CLS[t.priority] || PRIO_CLS.low}`}>{t.priority}</span>
                        <span className="text-xs text-gray-300">{AGENT_EMOJI[t.assignee] || '👤'} {t.assignee}</span>
                      </div>
                      <div className="text-sm font-semibold text-white leading-snug">{t.title}</div>
                      {t.description && <div className="text-xs text-gray-500 mt-1">{t.description}</div>}
                      <div className="flex items-center justify-between mt-3">
                        <span className={`text-xs ${t.overdue ? 'text-red-400' : 'text-gray-500'}`}>
                          {t.overdue ? '⚠️ ' : '⏰ '}{fmtDue(t.due_at)}
                        </span>
                        <button onClick={() => move(t.id, t.status)}
                          className="text-xs px-2.5 py-1 rounded-md border border-gray-700 text-gray-300 hover:border-gray-500 hover:text-white transition-colors">
                          → {COL_LABEL[NEXT[t.status]]}
                        </button>
                      </div>
                      <div className="flex items-center justify-between mt-2">
                        <span className="text-[10px] text-gray-600">{t.source} · by {t.created_by}</span>
                        {t.store_url && (
                          <a href={t.store_url} target="_blank" rel="noreferrer"
                            className="text-xs text-teal-400 hover:text-teal-300 font-medium">
                            🏪 {t.store_name} ↗
                          </a>
                        )}
                      </div>
                    </div>
                  ))}
                  {items.length === 0 && <div className="text-gray-600 text-xs px-1 py-2">—</div>}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
