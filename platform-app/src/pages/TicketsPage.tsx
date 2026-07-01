import { useEffect, useState, useCallback } from 'react';
import { apiGet, apiPost, apiPatch } from '../api/client';

interface Ticket {
  id: string; title: string; description: string; created_by: string;
  assignee: string; status: string; priority: string; source: string;
  due_at: string; overdue?: boolean;
}

const COLUMNS = ['todo', 'doing', 'blocked', 'done'];
const COL_LABEL: Record<string, string> = { todo: 'Todo', doing: 'Doing', blocked: 'Blocked', done: 'Done' };
const PRIO_COLOR: Record<string, string> = { critical: '#e5484d', high: '#f76808', medium: '#0091ff', low: '#8f8f8f' };
const NEXT: Record<string, string> = { todo: 'doing', doing: 'done', blocked: 'doing', done: 'todo' };
const AGENT_EMOJI: Record<string, string> = { Ava: '👑', Hunter: '🎯', Remy: '🎨', Devon: '🛠️', Max: '📣' };

function fmtDue(iso: string): string {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
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

  const move = async (id: string, status: string) => {
    await apiPatch(`/org/tickets/${id}`, { status: NEXT[status] });
    load();
  };
  const scan = async () => {
    setScanning(true);
    await apiPost('/org/tickets/scan', {}).catch(() => {});
    setScanning(false); load();
  };

  const open = tickets.filter((t) => t.status !== 'done').length;
  const overdue = tickets.filter((t) => t.overdue).length;

  return (
    <div style={{ padding: 24 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
        <div>
          <h1 style={{ margin: 0 }}>🎫 Tickets</h1>
          <div style={{ color: '#8f8f8f', fontSize: 14, marginTop: 4 }}>
            Agents open tickets from problems; Ava assigns owner, priority &amp; deadline.
            &nbsp;·&nbsp; {open} open &nbsp;·&nbsp; <span style={{ color: overdue ? '#e5484d' : '#8f8f8f' }}>{overdue} overdue</span>
          </div>
        </div>
        <button onClick={scan} disabled={scanning}
          style={{ padding: '10px 18px', borderRadius: 8, border: 'none', background: '#161616', color: '#fff', cursor: 'pointer' }}>
          {scanning ? 'Scanning…' : '🔍 Run quality scan'}
        </button>
      </div>

      {loading ? <div style={{ color: '#8f8f8f' }}>Loading…</div> : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, alignItems: 'start' }}>
          {COLUMNS.map((col) => {
            const items = tickets.filter((t) => t.status === col);
            return (
              <div key={col} style={{ background: '#f6f6f6', borderRadius: 12, padding: 12, minHeight: 120 }}>
                <div style={{ fontWeight: 700, marginBottom: 10, fontSize: 13, textTransform: 'uppercase', letterSpacing: '.05em', color: '#555' }}>
                  {COL_LABEL[col]} <span style={{ color: '#aaa' }}>({items.length})</span>
                </div>
                {items.map((t) => (
                  <div key={t.id} style={{ background: '#fff', borderRadius: 10, padding: 12, marginBottom: 10, boxShadow: '0 1px 3px rgba(0,0,0,.08)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                      <span style={{ fontSize: 11, fontWeight: 700, color: '#fff', background: PRIO_COLOR[t.priority] || '#888', padding: '2px 8px', borderRadius: 6, textTransform: 'uppercase' }}>{t.priority}</span>
                      <span title={t.assignee} style={{ fontSize: 13 }}>{AGENT_EMOJI[t.assignee] || '👤'} {t.assignee}</span>
                    </div>
                    <div style={{ fontWeight: 600, fontSize: 14, lineHeight: 1.3 }}>{t.title}</div>
                    {t.description && <div style={{ color: '#888', fontSize: 12, marginTop: 4 }}>{t.description}</div>}
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 10 }}>
                      <span style={{ fontSize: 12, color: t.overdue ? '#e5484d' : '#8f8f8f' }}>
                        {t.overdue ? '⚠️ ' : '⏰ '}{fmtDue(t.due_at)}
                      </span>
                      <button onClick={() => move(t.id, t.status)}
                        style={{ fontSize: 11, padding: '4px 10px', borderRadius: 6, border: '1px solid #ddd', background: '#fafafa', cursor: 'pointer' }}>
                        → {COL_LABEL[NEXT[t.status]]}
                      </button>
                    </div>
                    <div style={{ fontSize: 10, color: '#bbb', marginTop: 6 }}>{t.source} · by {t.created_by}</div>
                  </div>
                ))}
                {items.length === 0 && <div style={{ color: '#bbb', fontSize: 12, padding: 8 }}>—</div>}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
