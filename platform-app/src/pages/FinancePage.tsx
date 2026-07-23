import { useEffect, useState } from 'react';
import { apiGet, apiPost, apiPatch, apiDelete } from '../api/client';

interface CostItem {
  name: string; category: string; amount: number; currency: string;
  period: string; amount_usd: number; monthly_usd: number; note?: string;
}
interface CostRow {
  id: string; name: string; category: string; amount: number; currency: string;
  period: string; note: string;
}
const EMPTY_ROW: Omit<CostRow, 'id'> = { name: 'New item', category: '', amount: 0, currency: 'USD', period: 'monthly', note: '' };

/** Mirrors src/mcp_tools/finance.py's _to_usd/_monthly_usd — recalculates instantly
 * client-side on every edit, without waiting for a server round-trip. */
function rowMonthlyUsd(row: CostRow, ilsRate: number): number {
  const usd = row.currency === 'ILS' ? row.amount * ilsRate : row.amount;
  if (row.period === 'monthly') return usd;
  if (row.period === 'yearly') return usd / 12;
  return 0;
}

interface Summary {
  window_days: number;
  costs: { items: CostItem[]; monthly_recurring_usd: number; one_time_usd: number; ils_usd_rate: number };
  revenue: { status: string; gross_usd: number | null; net_usd: number | null; error?: string };
  agent_cost: { status: string; total_usd: number; by_agent: Record<string, { cost_usd: number; calls: number; tokens: number }>; note?: string };
  ad_spend: { status: string; spend_usd: number | null; note?: string };
  fixed_costs_window_usd: number;
  net_usd: number | null;
  pending_data: string[];
  at: string;
}

const money = (v: number | null | undefined) => (v == null ? '—' : `$${v.toFixed(2)}`);

function Stat({ label, value, sub, tone }: { label: string; value: string; sub?: string; tone?: 'good' | 'bad' | 'warn' }) {
  const color = tone === 'good' ? 'text-emerald-400' : tone === 'bad' ? 'text-rose-400' : tone === 'warn' ? 'text-amber-400' : 'text-gray-100';
  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900/60 p-4">
      <div className="text-xs uppercase tracking-wide text-gray-500">{label}</div>
      <div className={`mt-1 text-2xl font-semibold ${color}`}>{value}</div>
      {sub && <div className="mt-1 text-xs text-gray-500">{sub}</div>}
    </div>
  );
}

export function FinancePage() {
  const [data, setData] = useState<Summary | null>(null);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(30);
  const [error, setError] = useState('');

  // Editable cost rows — separate from `data` (which comes from the read-only
  // /finance/summary snapshot) so edits recalculate the monthly total INSTANTLY,
  // without waiting on a server round-trip.
  const [rows, setRows] = useState<CostRow[]>([]);
  const [rowsLoaded, setRowsLoaded] = useState(false);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    apiGet<Summary>(`/finance/summary?days=${days}`)
      .then((d) => alive && (setData(d), setError('')))
      .catch((e) => alive && setError(String(e)))
      .finally(() => alive && setLoading(false));
    return () => { alive = false; };
  }, [days]);

  useEffect(() => {
    let alive = true;
    apiGet<{ items: CostRow[] }>('/finance/costs')
      .then((d) => alive && setRows(d.items))
      .finally(() => alive && setRowsLoaded(true));
    return () => { alive = false; };
  }, []);

  function patchRow(id: string, field: keyof CostRow, value: string | number) {
    setRows((prev) => prev.map((r) => (r.id === id ? { ...r, [field]: value } : r)));
  }

  async function commitRow(id: string, field: keyof CostRow, value: string | number) {
    try {
      await apiPatch(`/finance/costs/${id}`, { [field]: value });
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to save');
    }
  }

  async function addRow() {
    try {
      const created = await apiPost<CostRow>('/finance/costs', EMPTY_ROW);
      setRows((prev) => [...prev, created]);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to add row');
    }
  }

  async function removeRow(id: string) {
    setRows((prev) => prev.filter((r) => r.id !== id)); // optimistic — instant feedback
    try {
      await apiDelete(`/finance/costs/${id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to delete row');
    }
  }

  if (loading && !data) return <div className="p-8 text-gray-400">Loading finance…</div>;
  if (error) return <div className="p-8 text-rose-400">Failed to load: {error}</div>;
  if (!data) return null;

  const ilsRate = data.costs.ils_usd_rate;
  // Live, client-side recalculated total — reflects every edit immediately,
  // independent of the /finance/summary snapshot's (possibly stale) value.
  const liveMonthlyTotal = rowsLoaded
    ? rows.reduce((sum, r) => sum + rowMonthlyUsd(r, ilsRate), 0)
    : data.costs.monthly_recurring_usd;
  const liveOneTimeTotal = rowsLoaded
    ? rows.filter((r) => r.period === 'one_time')
        .reduce((sum, r) => sum + (r.currency === 'ILS' ? r.amount * ilsRate : r.amount), 0)
    : data.costs.one_time_usd;
  const totalMonthlyCost = liveMonthlyTotal;
  const periodCost = (data.agent_cost.total_usd || 0) + (data.ad_spend.spend_usd || 0) + data.fixed_costs_window_usd;

  const inputCls = 'w-full bg-transparent px-1 py-0.5 text-gray-200 focus:outline-none focus:ring-1 focus:ring-indigo-600 rounded';

  return (
    <div className="mx-auto max-w-6xl p-6">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">💰 Finance</h1>
          <p className="text-sm text-gray-500">Expenses vs revenue · what the business pays for, what it earns, and the net.</p>
        </div>
        <select value={days} onChange={(e) => setDays(Number(e.target.value))}
          className="rounded-lg border border-gray-700 bg-gray-900 px-3 py-1.5 text-sm text-gray-200">
          <option value={7}>Last 7 days</option>
          <option value={30}>Last 30 days</option>
        </select>
      </div>

      {/* Top line */}
      <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label={`Revenue (${days}d)`} value={data.revenue.net_usd == null ? 'n/a' : money(data.revenue.net_usd)}
          sub={data.revenue.status === 'ok' ? 'PayPal net' : 'PayPal not connected'} tone={data.revenue.net_usd ? 'good' : 'warn'} />
        <Stat label={`Cost (${days}d)`} value={money(periodCost)} sub="agents + ads + fixed (prorated)" />
        <Stat label="Fixed run-rate" value={`${money(totalMonthlyCost)}/mo`} sub={`+ $${liveOneTimeTotal.toFixed(2)} one-time`} />
        <Stat label={`NET (${days}d)`} value={data.net_usd == null ? 'n/a' : money(data.net_usd)}
          sub={data.net_usd == null ? 'needs revenue connected' : data.net_usd >= 0 ? 'profit' : 'loss'}
          tone={data.net_usd == null ? 'warn' : data.net_usd >= 0 ? 'good' : 'bad'} />
      </div>

      {data.pending_data.length > 0 && (
        <div className="mb-6 rounded-lg border border-amber-700/40 bg-amber-900/15 p-3 text-sm text-amber-300">
          ⚠️ Not connected yet: <b>{data.pending_data.join(', ')}</b>. These show honest placeholders until wired
          (PayPal needs the “Transaction Search” permission; Google Ads metrics are still mocked).
        </div>
      )}

      {/* Fixed costs table — editable: click any cell, edit, tab/blur to save.
          The monthly run-rate footer recalculates instantly on every change. */}
      <div className="mb-2 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-200">Fixed / known costs</h2>
        <button onClick={addRow}
          className="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium">
          + Add row
        </button>
      </div>
      {/* overflow-x-auto (not overflow-hidden) so every column is reachable by
          horizontal scroll on a narrow phone; min-w keeps columns legible. */}
      <div className="mb-8 overflow-x-auto rounded-xl border border-gray-800">
        <table className="w-full min-w-[700px] text-sm">
          <thead className="bg-gray-900/80 text-left text-xs uppercase tracking-wide text-gray-500">
            <tr>
              <th className="px-3 py-2">What</th><th className="px-3 py-2">Category</th>
              <th className="px-3 py-2 text-right whitespace-nowrap">Price</th>
              <th className="px-3 py-2">Currency</th><th className="px-3 py-2">Billing</th>
              <th className="px-3 py-2">Note</th>
              <th className="px-3 py-2 text-right whitespace-nowrap">≈ $/mo</th>
              <th className="px-2 py-2" />
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800">
            {rows.map((r) => (
              <tr key={r.id} className="hover:bg-gray-900/40">
                <td className="px-1 py-1">
                  <input className={inputCls} value={r.name}
                    onChange={(e) => patchRow(r.id, 'name', e.target.value)}
                    onBlur={(e) => commitRow(r.id, 'name', e.target.value)} />
                </td>
                <td className="px-1 py-1">
                  <input className={inputCls} value={r.category}
                    onChange={(e) => patchRow(r.id, 'category', e.target.value)}
                    onBlur={(e) => commitRow(r.id, 'category', e.target.value)} />
                </td>
                <td className="px-1 py-1">
                  <input type="number" step="0.01" className={`${inputCls} text-right`} value={r.amount}
                    onChange={(e) => patchRow(r.id, 'amount', Number(e.target.value))}
                    onBlur={(e) => commitRow(r.id, 'amount', Number(e.target.value))} />
                </td>
                <td className="px-1 py-1">
                  <select className={inputCls} value={r.currency}
                    onChange={(e) => { patchRow(r.id, 'currency', e.target.value); commitRow(r.id, 'currency', e.target.value); }}>
                    <option value="USD">USD</option>
                    <option value="ILS">ILS</option>
                  </select>
                </td>
                <td className="px-1 py-1">
                  <select className={inputCls} value={r.period}
                    onChange={(e) => { patchRow(r.id, 'period', e.target.value); commitRow(r.id, 'period', e.target.value); }}>
                    <option value="monthly">monthly</option>
                    <option value="yearly">yearly</option>
                    <option value="one_time">one_time</option>
                    <option value="variable">variable</option>
                  </select>
                </td>
                <td className="px-1 py-1">
                  <input className={`${inputCls} text-xs text-gray-500`} value={r.note}
                    onChange={(e) => patchRow(r.id, 'note', e.target.value)}
                    onBlur={(e) => commitRow(r.id, 'note', e.target.value)} />
                </td>
                <td className="px-3 py-1 text-right font-medium text-gray-200 whitespace-nowrap">
                  {rowMonthlyUsd(r, ilsRate) ? `$${rowMonthlyUsd(r, ilsRate).toFixed(2)}` : '—'}
                </td>
                <td className="px-2 py-1 text-center">
                  <button onClick={() => removeRow(r.id)} title="Delete row"
                    className="text-gray-600 hover:text-red-400 text-xs">✕</button>
                </td>
              </tr>
            ))}
            {rows.length === 0 && rowsLoaded && (
              <tr><td colSpan={8} className="px-3 py-6 text-center text-gray-500">No cost rows yet — add one above.</td></tr>
            )}
          </tbody>
          <tfoot className="bg-gray-900/80 text-sm">
            <tr>
              <td className="px-3 py-2 font-semibold text-gray-200" colSpan={6}>Monthly recurring run-rate</td>
              <td className="px-3 py-2 text-right font-bold text-rose-300 whitespace-nowrap" colSpan={2}>${totalMonthlyCost.toFixed(2)}/mo</td>
            </tr>
          </tfoot>
        </table>
        <div className="bg-gray-900/40 px-4 py-1.5 text-xs text-gray-500">₪→$ at {ilsRate} (≈ 1 USD / {(1 / ilsRate).toFixed(1)} ILS). Edits save automatically per cell.</div>
      </div>

      {/* Dynamic costs */}
      <h2 className="mb-2 text-lg font-semibold text-gray-200">Operating costs (last {days}d)</h2>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        <div className="rounded-xl border border-gray-800 bg-gray-900/60 p-4">
          <div className="mb-2 flex items-center justify-between">
            <span className="font-medium text-gray-200">🤖 Agents (Claude tokens)</span>
            <span className="font-semibold text-gray-100">{money(data.agent_cost.total_usd)}</span>
          </div>
          {Object.keys(data.agent_cost.by_agent).length === 0 ? (
            <p className="text-xs text-gray-500">{data.agent_cost.note || 'No traced LLM spend (running on the free local model → ~$0).'}</p>
          ) : (
            <ul className="space-y-1 text-sm">
              {Object.entries(data.agent_cost.by_agent).map(([name, a]) => (
                <li key={name} className="flex justify-between text-gray-300">
                  <span>{name}</span><span>{money(a.cost_usd)} · {a.calls} calls</span>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="rounded-xl border border-gray-800 bg-gray-900/60 p-4">
          <div className="mb-2 flex items-center justify-between">
            <span className="font-medium text-gray-200">📣 Ads (Google)</span>
            <span className="font-semibold text-gray-100">{data.ad_spend.spend_usd == null ? 'n/a' : money(data.ad_spend.spend_usd)}</span>
          </div>
          <p className="text-xs text-gray-500">{data.ad_spend.note}</p>
        </div>
      </div>
    </div>
  );
}
