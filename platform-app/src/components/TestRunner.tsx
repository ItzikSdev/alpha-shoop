import { useState } from 'react';
import type { APIEndpoint, MCPTool } from '../types';

const API_BASE = 'http://localhost:8000';

interface EndpointRunnerProps {
  endpoint: APIEndpoint;
}

export function EndpointTestRunner({ endpoint }: EndpointRunnerProps) {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{ status: number; body: unknown } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);

  const run = async () => {
    setLoading(true);
    setError(null);
    setResult(null);

    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (endpoint.requiresAuth) {
      headers['Authorization'] = 'Bearer YOUR_JWT_TOKEN';
    }

    let body: string | undefined;
    if (endpoint.requestBody) {
      const example: Record<string, unknown> = {};
      endpoint.requestBody.fields.forEach(f => {
        if (f.example !== undefined && f.example !== null) example[f.name] = f.example;
      });
      body = JSON.stringify(example);
    }

    const path = endpoint.path.replace('{thread_id}', 'test-thread-id');

    try {
      const resp = await fetch(`${API_BASE}${path}`, {
        method: endpoint.method,
        headers,
        body: ['GET', 'DELETE'].includes(endpoint.method) ? undefined : body,
        signal: AbortSignal.timeout(10_000),
      });
      const data = await resp.json().catch(() => ({}));
      setResult({ status: resp.status, body: data });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  const statusColor = result
    ? result.status < 300 ? 'text-emerald-400' : result.status < 500 ? 'text-yellow-400' : 'text-red-400'
    : '';

  return (
    <div>
      <div className="flex items-center gap-2">
        <button
          onClick={() => { setOpen(!open); if (!open && !result && !error) run(); else if (open) {} }}
          disabled={loading}
          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium bg-indigo-900/60 text-indigo-300 border border-indigo-700 hover:bg-indigo-800/80 hover:text-white transition-all disabled:opacity-50"
        >
          {loading ? '⏳ Running...' : '▶ Run Test'}
        </button>
        {result && <span className={`text-xs font-mono ${statusColor}`}>HTTP {result.status}</span>}
        {error && <span className="text-xs text-red-400">⚠ {error.substring(0, 60)}</span>}
        {result && (
          <button onClick={() => setOpen(o => !o)} className="text-xs text-gray-500 hover:text-gray-300">
            {open ? '▲ hide' : '▼ show'}
          </button>
        )}
      </div>

      {open && result && (
        <pre className="mt-2 p-3 bg-gray-950 border border-gray-700 rounded-lg text-xs font-mono text-green-300 overflow-x-auto max-h-48">
          {JSON.stringify(result.body, null, 2)}
        </pre>
      )}
      {open && error && (
        <div className="mt-2 p-3 bg-red-950/40 border border-red-800 rounded-lg text-xs text-red-300 font-mono">
          {error}
          <div className="mt-1 text-gray-500">Is the FastAPI server running? Run: <code>make dev</code></div>
        </div>
      )}
    </div>
  );
}

// ── MCP Tool test runner ───────────────────────────────────────────────────────

interface ToolRunnerProps {
  tool: MCPTool;
}

export function ToolTestRunner({ tool }: ToolRunnerProps) {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);

  const run = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const resp = await fetch(`${API_BASE}/api/v1/tools/invoke`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer YOUR_JWT_TOKEN' },
        body: JSON.stringify({ tool_name: tool.name, arguments: tool.exampleArgs }),
        signal: AbortSignal.timeout(15_000),
      });
      const data = await resp.json();
      setResult(data);
      setOpen(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setOpen(true);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div className="flex items-center gap-2">
        <button
          onClick={run}
          disabled={loading}
          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium bg-violet-900/60 text-violet-300 border border-violet-700 hover:bg-violet-800/80 hover:text-white transition-all disabled:opacity-50"
        >
          {loading ? '⏳ Running...' : '▶ Test Tool'}
        </button>
        {result && <span className="text-xs text-emerald-400">✓ success</span>}
        {error && <span className="text-xs text-red-400">⚠ {error.substring(0, 50)}</span>}
        {(result || error) && (
          <button onClick={() => setOpen(o => !o)} className="text-xs text-gray-500 hover:text-gray-300">
            {open ? '▲ hide' : '▼ show'}
          </button>
        )}
      </div>

      {open && result && (
        <pre className="mt-2 p-3 bg-gray-950 border border-gray-700 rounded-lg text-xs font-mono text-green-300 overflow-x-auto max-h-48">
          {JSON.stringify(result, null, 2)}
        </pre>
      )}
      {open && error && (
        <div className="mt-2 p-3 bg-red-950/40 border border-red-800 rounded-lg text-xs text-red-300">
          {error}
          <div className="mt-1 text-gray-500">Run <code>make dev</code> first, then set a valid JWT in the token field.</div>
        </div>
      )}
    </div>
  );
}
