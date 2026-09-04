import { useEffect, useState } from 'react';

interface Entry {
  heading: string;
  paragraphs: string[];
}

// Minimal inline markdown → HTML: escapes first, then **bold** and `code`.
// Content is our own docs/DECISIONS_LOG.md (trusted, not user-supplied).
function mdInline(text: string): string {
  const escaped = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
  return escaped
    .replace(/`([^`]+)`/g, '<code class="text-indigo-300 bg-gray-800 px-1 py-0.5 rounded text-xs">$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong class="text-gray-200">$1</strong>');
}

function parseLog(raw: string): Entry[] {
  const chunks = raw.split(/\n---\n/).map(c => c.trim()).filter(Boolean);
  // First chunk is the file's title/intro, not a dated entry.
  return chunks.slice(1).map(chunk => {
    const lines = chunk.split('\n');
    const headingLine = lines.find(l => l.startsWith('## ')) ?? lines[0];
    const heading = headingLine.replace(/^##\s*/, '');
    const bodyStart = chunk.indexOf(headingLine) + headingLine.length;
    const body = chunk.slice(bodyStart).trim();
    const paragraphs = body.split(/\n\n+/).map(p => p.trim()).filter(Boolean);
    return { heading, paragraphs };
  });
}

export function UpdatesPage() {
  const [entries, setEntries] = useState<Entry[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch('/decisions-log.md')
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.text();
      })
      .then(raw => setEntries(parseLog(raw)))
      .catch(e => setError(e.message));
  }, []);

  return (
    <div className="p-8 max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">📰 Updates</h1>
        <p className="text-gray-400 text-sm mt-1">
          Chronological record of diagnostics and fixes across the org — mirrors{' '}
          <code className="text-gray-500">docs/DECISIONS_LOG.md</code>. Newest first.
        </p>
      </div>

      {error && (
        <div className="p-4 bg-yellow-950/40 border border-yellow-800 rounded-xl">
          <p className="text-yellow-400 text-sm">Could not load updates: {error}</p>
        </div>
      )}

      {!entries && !error && (
        <div className="p-4 bg-gray-900 border border-gray-700 rounded-xl text-gray-500 text-sm animate-pulse">
          Loading updates...
        </div>
      )}

      <div className="space-y-4">
        {entries?.map((e, i) => (
          <details key={i} open={i < 2} className="group bg-gray-900 border border-gray-800 rounded-xl p-4">
            <summary className="cursor-pointer text-white font-semibold text-sm marker:text-indigo-500">
              {e.heading}
            </summary>
            <div className="mt-3 space-y-3">
              {e.paragraphs.map((p, j) => (
                <p
                  key={j}
                  className="text-gray-400 text-sm leading-relaxed"
                  dangerouslySetInnerHTML={{ __html: mdInline(p) }}
                />
              ))}
            </div>
          </details>
        ))}
      </div>
    </div>
  );
}
