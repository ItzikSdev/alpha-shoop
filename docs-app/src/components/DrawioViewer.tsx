import { useEffect, useState } from 'react';

interface Props {
  url: string;
  height?: number;
}

export function DrawioViewer({ url, height = 600 }: Props) {
  const [viewerUrl, setViewerUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(url)
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.text();
      })
      .then(xml => {
        // diagrams.net viewer accepts inline XML via hash encoding
        // Format: https://viewer.diagrams.net/#HXML_ENCODED
        // XML is URI-encoded then base64-encoded
        const encoded = btoa(unescape(encodeURIComponent(xml)));
        setViewerUrl(`https://viewer.diagrams.net/?lightbox=1&highlight=0001ff&nav=1&title=Architecture#H${encoded}`);
        setLoading(false);
      })
      .catch(e => {
        setError(e.message);
        setLoading(false);
      });
  }, [url]);

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
    <div className="space-y-2">
      <div className="flex items-center gap-2 justify-end">
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
        height={height}
        className="rounded-xl border border-gray-700 bg-white"
        title="Architecture Diagram"
        sandbox="allow-scripts allow-same-origin allow-popups"
      />
    </div>
  );
}
