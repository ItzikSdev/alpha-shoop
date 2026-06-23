import { useEffect, useRef, useState } from 'react';

interface Props {
  url: string;
  height?: number;
}

export function DrawioViewer({ url, height = 600 }: Props) {
  const [viewerUrl, setViewerUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [fullscreen, setFullscreen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetch(url)
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.text();
      })
      .then(xml => {
        // diagrams.net viewer accepts inline XML via hash encoding — fully
        // self-contained, no GitHub login or external storage involved.
        // Format: https://viewer.diagrams.net/#HXML_ENCODED
        // XML is URI-encoded then base64-encoded
        const encoded = btoa(unescape(encodeURIComponent(xml)));
        // toolbar=zoom gives real zoom in/out/fit/reset controls instead of
        // the static lightbox preview (which had no usable zoom UI).
        setViewerUrl(`https://viewer.diagrams.net/?toolbar=zoom&nav=1&fit=1&resize=1&edit=_blank&title=Architecture#H${encoded}`);
        setLoading(false);
      })
      .catch(e => {
        setError(e.message);
        setLoading(false);
      });
  }, [url]);

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

  if (loading) {
    return (
      <div className="flex items-center justify-center h-48 bg-gray-900 border border-gray-700 rounded-xl">
        <span className="text-gray-500 text-sm animate-pulse">Loading diagram...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 bg-yellow-950/40 border border-yellow-800 rounded-xl">
        <p className="text-yellow-400 text-sm">Could not load {url}: {error}</p>
        <p className="text-gray-500 text-xs mt-1">Make sure <code>make docs</code> copied the file to docs-app/public/</p>
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
          href={viewerUrl!}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-blue-400 hover:text-blue-300"
        >
          ↗ Open in diagrams.net
        </a>
        <a
          href={url}
          download="architecture.drawio"
          className="text-xs text-gray-400 hover:text-gray-300"
        >
          ↓ Download .drawio
        </a>
      </div>
      <iframe
        src={viewerUrl!}
        width="100%"
        height={fullscreen ? 'calc(100% - 2rem)' : height}
        className="rounded-xl border border-gray-700 bg-white"
        title="Architecture Diagram"
        sandbox="allow-scripts allow-same-origin allow-popups"
      />
    </div>
  );
}
