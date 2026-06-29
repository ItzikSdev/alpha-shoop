import { useEffect, useState } from 'react';
import { apiGet } from '../api/client';

interface Integration {
  key: string; name: string; category: string;
  who: string[]; connected: boolean; detail: string;
}
interface Resp { integrations: Integration[]; connected: number; total: number }

export function IntegrationsPage() {
  const [data, setData] = useState<Resp | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let alive = true;
    apiGet<Resp>('/org/integrations')
      .then((d) => alive && (setData(d), setError('')))
      .catch((e) => alive && setError(String(e)))
      .finally(() => alive && setLoading(false));
    return () => { alive = false; };
  }, []);

  if (loading) return <div className="p-8 text-gray-400">Loading integrations…</div>;
  if (error) return <div className="p-8 text-rose-400">Failed to load: {error}</div>;
  if (!data) return null;

  return (
    <div className="mx-auto max-w-5xl p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-100">🔌 Integrations</h1>
        <p className="text-sm text-gray-500">
          What the team is connected to — so you know what to set up or re-authorize.
          <span className="ml-2 text-gray-400">{data.connected}/{data.total} connected.</span>
        </p>
      </div>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        {data.integrations.map((i) => (
          <div key={i.key}
            className={`rounded-xl border p-4 ${i.connected ? 'border-emerald-800/50 bg-emerald-900/10' : 'border-amber-800/50 bg-amber-900/10'}`}>
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="font-medium text-gray-100">{i.name}</div>
                <div className="text-xs text-gray-500">{i.category}</div>
              </div>
              <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${i.connected ? 'bg-emerald-500/20 text-emerald-300' : 'bg-amber-500/20 text-amber-300'}`}>
                {i.connected ? '● connected' : '○ needs setup'}
              </span>
            </div>
            <p className="mt-2 text-sm text-gray-400">{i.detail}</p>
            <div className="mt-3 flex flex-wrap gap-1">
              {i.who.map((w) => (
                <span key={w} className="rounded bg-gray-800 px-2 py-0.5 text-xs text-gray-400">{w}</span>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
