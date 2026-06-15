import { useEffect, useRef, useState } from 'react';

// Dynamic import avoids Vite pre-bundling conflicts with mermaid's sub-chunks
type MermaidAPI = typeof import('mermaid').default;

let _mermaid: MermaidAPI | null = null;
let _initialized = false;

async function getMermaid(): Promise<MermaidAPI> {
  if (!_mermaid) {
    const mod = await import('mermaid');
    _mermaid = mod.default;
  }
  if (!_initialized) {
    _mermaid.initialize({
      startOnLoad: false,
      theme: 'dark',
      themeVariables: {
        background: '#0f172a',
        primaryColor: '#1e293b',
        primaryTextColor: '#e2e8f0',
        lineColor: '#64748b',
        edgeLabelBackground: '#1e293b',
      },
      fontFamily: 'JetBrains Mono, monospace',
      flowchart: { curve: 'basis', padding: 20 },
    });
    _initialized = true;
  }
  return _mermaid;
}

interface Props {
  content: string;
  id: string;
}

export function MermaidDiagram({ content, id }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    const render = async () => {
      if (!containerRef.current) return;
      try {
        const mermaid = await getMermaid();
        const safeId = `m_${id.replace(/[^a-zA-Z0-9]/g, '_')}`;
        const { svg } = await mermaid.render(safeId, content);
        if (!cancelled && containerRef.current) {
          containerRef.current.innerHTML = svg;
          setError(null);
          setLoading(false);
        }
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : String(e));
          setLoading(false);
        }
      }
    };

    render();
    return () => { cancelled = true; };
  }, [content, id]);

  if (error) {
    return (
      <div className="p-4 bg-red-950/40 border border-red-800 rounded-lg">
        <p className="text-red-400 text-sm font-mono">Mermaid render error: {error}</p>
      </div>
    );
  }

  return (
    <div className="relative w-full overflow-auto bg-gray-950/50 rounded-xl p-4 border border-gray-700" style={{ minHeight: 200 }}>
      {loading && (
        <div className="absolute inset-0 flex items-center justify-center text-gray-600 text-sm animate-pulse">
          Rendering diagram...
        </div>
      )}
      <div ref={containerRef} />
    </div>
  );
}
