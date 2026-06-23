import { useState } from 'react';
import type { APIEndpoint } from '../types';
import { TechBadge } from './TechBadge';
import { TypeTooltip } from './TypeTooltip';
import { CopyButton, VSCodeButton, buildCurl } from './ActionButtons';
import { EndpointTestRunner } from './TestRunner';

const METHOD_COLORS: Record<string, string> = {
  GET: 'bg-emerald-900/50 text-emerald-300 border-emerald-700',
  POST: 'bg-blue-900/50 text-blue-300 border-blue-700',
  PUT: 'bg-amber-900/50 text-amber-300 border-amber-700',
  DELETE: 'bg-red-900/50 text-red-300 border-red-700',
  PATCH: 'bg-orange-900/50 text-orange-300 border-orange-700',
};

interface Props {
  endpoint: APIEndpoint;
}

export function EndpointCard({ endpoint }: Props) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="bg-gray-900 border border-gray-700 rounded-xl overflow-hidden hover:border-gray-600 transition-colors">
      {/* Header */}
      <button
        onClick={() => setExpanded(e => !e)}
        className="w-full text-left p-4 flex items-start gap-3"
      >
        <span className={`shrink-0 mt-0.5 px-2 py-0.5 rounded border text-xs font-bold font-mono ${METHOD_COLORS[endpoint.method]}`}>
          {endpoint.method}
        </span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <code className="text-white font-mono text-sm">{endpoint.path}</code>
            {endpoint.requiresAuth && (
              <span className="text-yellow-500 text-xs" title="Requires JWT auth">🔐 JWT</span>
            )}
          </div>
          <p className="text-gray-400 text-sm mt-1">{endpoint.description}</p>
          <div className="flex flex-wrap gap-1 mt-2">
            {endpoint.techIds.map(id => <TechBadge key={id} techId={id} size="sm" />)}
          </div>
        </div>
        <span className="text-gray-500 shrink-0">{expanded ? '▲' : '▼'}</span>
      </button>

      {/* Expanded body */}
      {expanded && (
        <div className="border-t border-gray-700 p-4 space-y-4">
          {/* Types row */}
          <div className="flex flex-wrap gap-6">
            {endpoint.requestBody && (
              <div>
                <span className="text-gray-500 text-xs uppercase tracking-wide">Request Body</span>
                <div className="mt-1">
                  <TypeTooltip schema={endpoint.requestBody}>
                    {endpoint.requestBody.name}
                  </TypeTooltip>
                </div>
              </div>
            )}
            <div>
              <span className="text-gray-500 text-xs uppercase tracking-wide">Response</span>
              <div className="mt-1">
                <TypeTooltip schema={endpoint.response}>
                  {endpoint.response.name}
                </TypeTooltip>
              </div>
            </div>
          </div>

          {/* cURL example */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <span className="text-gray-500 text-xs uppercase tracking-wide">cURL</span>
              <CopyButton text={buildCurl(endpoint)} label="Copy cURL" />
            </div>
            <pre className="p-3 bg-gray-950 border border-gray-800 rounded-lg text-xs font-mono text-green-300 overflow-x-auto">
              {buildCurl(endpoint)}
            </pre>
          </div>

          {/* Action bar */}
          <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-gray-800">
            <VSCodeButton filePath={endpoint.filePath} lineNumber={endpoint.lineNumber} />
            <span className="text-gray-600 text-xs font-mono">{endpoint.filePath}:{endpoint.lineNumber}</span>
            <div className="ml-auto">
              <EndpointTestRunner endpoint={endpoint} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
