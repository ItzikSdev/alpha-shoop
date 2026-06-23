import { useEffect, useRef, useState, useCallback } from 'react';

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

const STEP = 0.25;
const MIN = 0.25;
const MAX = 4.0;

interface Props {
  content: string;
  id: string;
}

export function MermaidDiagram({ content, id }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [scale, setScale] = useState(1.0);
  const [fullscreen, setFullscreen] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const render = async () => {
      if (!containerRef.current) return;
      try {
        const mermaid = await getMermaid();
        const safeId = `m_${id.replace(/[^a-zA-Z0-9]/g, '_')}`;
        const { svg } = await mermaid.render(safeId, content);
        if (cancelled || !containerRef.current) return;
        containerRef.current.innerHTML = svg;

        // Make SVG responsive: strip fixed w/h so it fills its container via viewBox
        const svgEl = containerRef.current.querySelector('svg');
        if (svgEl) {
          const w = svgEl.getAttribute('width');
          const h = svgEl.getAttribute('height');
          if (!svgEl.getAttribute('viewBox') && w && h) {
            svgEl.setAttribute('viewBox', `0 0 ${w} ${h}`);
          }
          svgEl.removeAttribute('width');
          svgEl.removeAttribute('height');
          svgEl.style.cssText = 'width:100%;height:auto;display:block;';
        }

        setError(null);
        setLoading(false);
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

  const clamp = (v: number) => Math.max(MIN, Math.min(MAX, Math.round(v * 100) / 100));
  const adjustScale = useCallback((delta: number) => setScale(s => clamp(s + delta)), []);

  // Ctrl+scroll / trackpad pinch
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      if (e.ctrlKey || e.metaKey) {
        e.preventDefault();
        adjustScale(-e.deltaY * 0.003);
      }
    };
    el.addEventListener('wheel', onWheel, { passive: false });
    return () => el.removeEventListener('wheel', onWheel);
  }, [adjustScale]);

  useEffect(() => {
    const onChange = () => setFullscreen(!!document.fullscreenElement);
    document.addEventListener('fullscreenchange', onChange);
    return () => document.removeEventListener('fullscreenchange', onChange);
  }, []);

  function toggleFullscreen() {
    if (!wrapperRef.current) return;
    document.fullscreenElement ? document.exitFullscreen() : wrapperRef.current.requestFullscreen();
  }

  if (error) {
    return (
      <div className="p-4 bg-red-950/40 border border-red-800 rounded-lg">
        <p className="text-red-400 text-sm font-mono">Mermaid render error: {error}</p>
      </div>
    );
  }

  // Zoom by resizing the inner div — SVG is responsive so it fills the div and scales naturally.
  // At scale=1 → 100% width (fits the scroll area). At scale=2 → 200% width (scrollable, text 2× bigger).
  const innerWidth = `${Math.max(100, scale * 100)}%`;

  return (
    <div
      ref={wrapperRef}
      className={fullscreen
        ? 'fixed inset-0 z-50 bg-gray-950 flex flex-col p-3 gap-2'
        : 'space-y-2'
      }
    >
      {/* Toolbar */}
      <div className="flex items-center gap-2 justify-end flex-shrink-0">
        <span className="text-gray-600 text-xs hidden sm:inline">Ctrl+scroll to zoom</span>

        <button
          onClick={() => adjustScale(-STEP)}
          disabled={scale <= MIN}
          title="Zoom out"
          className="w-7 h-7 flex items-center justify-center rounded bg-gray-800 border border-gray-700 text-gray-300 hover:bg-gray-700 disabled:opacity-40 text-lg leading-none"
        >−</button>

        <span className="text-gray-300 text-sm w-14 text-center tabular-nums select-none font-mono">
          {Math.round(scale * 100)}%
        </span>

        <button
          onClick={() => adjustScale(STEP)}
          disabled={scale >= MAX}
          title="Zoom in"
          className="w-7 h-7 flex items-center justify-center rounded bg-gray-800 border border-gray-700 text-gray-300 hover:bg-gray-700 disabled:opacity-40 text-lg leading-none"
        >+</button>

        <button
          onClick={() => setScale(1.0)}
          className="px-2 h-7 rounded bg-gray-800 border border-gray-700 text-gray-400 hover:text-gray-200 text-xs"
        >Fit</button>

        <div className="w-px h-5 bg-gray-700 mx-1" />

        <button
          onClick={toggleFullscreen}
          className="px-3 h-7 rounded bg-gray-800 border border-gray-700 text-blue-400 hover:text-blue-300 text-xs"
        >
          {fullscreen ? '✕ Exit fullscreen' : '⛶ Fullscreen'}
        </button>
      </div>

      {/* Scroll container */}
      <div
        ref={scrollRef}
        className="relative overflow-auto bg-gray-950/50 rounded-xl border border-gray-700 flex-1"
        style={fullscreen ? {} : { minHeight: 220, maxHeight: '75vh' }}
      >
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center text-gray-600 text-sm animate-pulse">
            Rendering diagram...
          </div>
        )}
        {/*
          Width controls zoom: SVG is responsive so it scales to fill this div.
          min-width: 100% ensures it never collapses narrower than the viewport.
        */}
        <div
          ref={containerRef}
          style={{ width: innerWidth, minWidth: '100%', padding: '1rem', boxSizing: 'border-box' }}
        />
      </div>
    </div>
  );
}
