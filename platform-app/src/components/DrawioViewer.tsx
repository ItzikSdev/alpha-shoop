import { useEffect, useRef, useState } from 'react';

interface Props {
  url: string;
  height?: number;
}

declare global {
  interface Window {
    GraphViewer?: { processElements: () => void };
  }
}

// The iframe-based viewer.diagrams.net embed (previous approach) is the same
// app as the full editor and pops an unprompted "Authorization required —
// Authorize this app in GitHub" dialog on load, even in pure view mode with
// no `edit` param — there's no way to view a diagram there without hitting
// that dialog. diagrams.net's own docs recommend a different, genuinely
// backend-free embed for read-only display: `viewer-static.min.js` scans the
// page for `.mxgraph` elements and renders the diagram as inline SVG,
// entirely client-side — no iframe, no viewer.diagrams.net backend call, so
// there's nothing that could ever ask you to sign in.
let scriptPromise: Promise<void> | null = null;
function loadViewerScript(): Promise<void> {
  if (window.GraphViewer) return Promise.resolve();
  if (!scriptPromise) {
    scriptPromise = new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = 'https://viewer.diagrams.net/js/viewer-static.min.js';
      script.async = true;
      script.onload = () => resolve();
      script.onerror = () => reject(new Error('Failed to load diagrams.net viewer script'));
      document.body.appendChild(script);
    });
  }
  return scriptPromise;
}

export function DrawioViewer({ url, height = 600 }: Props) {
  const [xml, setXml] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [fullscreen, setFullscreen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setXml(null);
    setError(null);
    fetch(url)
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.text();
      })
      .then(setXml)
      .catch(e => setError(e.message));
  }, [url]);

  useEffect(() => {
    if (!xml || !graphRef.current) return;
    // Reset the render marker viewer-static sets, so switching diagrams
    // (a fresh `xml` on the same mounted node) gets re-processed.
    graphRef.current.removeAttribute('data-processed');
    graphRef.current.innerHTML = '';
    graphRef.current.setAttribute(
      'data-mxgraph',
      JSON.stringify({ toolbar: 'zoom layers', nav: true, resize: true, xml }),
    );
    let cancelled = false;
    loadViewerScript()
      .then(() => {
        if (!cancelled) window.GraphViewer?.processElements();
      })
      .catch(e => setError(e.message));
    return () => {
      cancelled = true;
    };
  }, [xml]);

  useEffect(() => {
    function onFsChange() {
      setFullscreen(!!document.fullscreenElement);
    }
    document.addEventListener('fullscreenchange', onFsChange);
    return () => document.removeEventListener('fullscreenchange', onFsChange);
  }, []);

  function toggleFullscreen() {
    if (!containerRef.current) return;
    if (document.fullscreenElement) {
      document.exitFullscreen();
    } else {
      containerRef.current.requestFullscreen();
    }
  }

  if (error) {
    return (
      <div className="p-4 bg-yellow-950/40 border border-yellow-800 rounded-xl">
        <p className="text-yellow-400 text-sm">Could not load {url}: {error}</p>
        <p className="text-gray-500 text-xs mt-1">Make sure <code>make docs</code> copied the file to platform-app/public/</p>
      </div>
    );
  }

  if (!xml) {
    return (
      <div className="flex items-center justify-center h-48 bg-gray-900 border border-gray-700 rounded-xl">
        <span className="text-gray-500 text-sm animate-pulse">Loading diagram...</span>
      </div>
    );
  }

  return (
    <div ref={containerRef} className={fullscreen ? 'bg-gray-900 p-2 h-screen' : 'space-y-2'}>
      <div className="flex items-center gap-3 justify-end">
        <button
          onClick={toggleFullscreen}
          className="text-xs text-blue-400 hover:text-blue-300"
        >
          {fullscreen ? '✕ Exit fullscreen' : '⛶ Fullscreen'}
        </button>
        <a
          href={url}
          download="architecture.drawio"
          className="text-xs text-gray-400 hover:text-gray-300"
        >
          ↓ Download .drawio
        </a>
      </div>
      <div
        className="rounded-xl border border-gray-700 bg-white overflow-auto p-2"
        style={{ height: fullscreen ? 'calc(100% - 2rem)' : height }}
      >
        <div ref={graphRef} className="mxgraph" style={{ maxWidth: '100%' }} />
      </div>
    </div>
  );
}
