import { useState } from 'react';
import type { MCPTool } from '../types';
import { TechBadge } from './TechBadge';
import { TypeTooltip } from './TypeTooltip';
import { CopyButton, VSCodeButton, buildMCPExample } from './ActionButtons';
import { ToolTestRunner } from './TestRunner';

interface Props {
  tool: MCPTool;
}

export function ToolCard({ tool }: Props) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="bg-gray-900 border border-gray-700 rounded-xl overflow-hidden hover:border-violet-700/50 transition-colors">
      {/* Header */}
      <button
        onClick={() => setExpanded(e => !e)}
        className="w-full text-left p-4 flex items-start gap-3"
      >
        <span className="shrink-0 mt-0.5 px-2 py-0.5 rounded border text-xs font-bold font-mono bg-violet-900/50 text-violet-300 border-violet-700">
          fn
        </span>
        <div className="flex-1 min-w-0">
          <code className="text-white font-mono text-sm">{tool.name}</code>
          <p className="text-gray-400 text-sm mt-1">{tool.description}</p>
          <div className="flex flex-wrap gap-1 mt-2">
            {tool.techIds.map(id => <TechBadge key={id} techId={id} size="sm" />)}
          </div>
        </div>
        <span className="text-gray-500 shrink-0">{expanded ? '▲' : '▼'}</span>
      </button>

      {/* Expanded */}
      {expanded && (
        <div className="border-t border-gray-700 p-4 space-y-4">
          {/* Signature */}
          <div className="flex flex-wrap gap-6">
            <div>
              <span className="text-gray-500 text-xs uppercase tracking-wide">Input</span>
              <div className="mt-1">
                <TypeTooltip schema={tool.input}>
                  {tool.input.name}
                </TypeTooltip>
              </div>
            </div>
            <div>
              <span className="text-gray-500 text-xs uppercase tracking-wide">Output</span>
              <div className="mt-1">
                <TypeTooltip schema={tool.output}>
                  {tool.output.name}
                </TypeTooltip>
              </div>
            </div>
          </div>

          {/* Python example */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <span className="text-gray-500 text-xs uppercase tracking-wide">Python Example</span>
              <CopyButton text={buildMCPExample(tool)} label="Copy" />
            </div>
            <pre className="p-3 bg-gray-950 border border-gray-800 rounded-lg text-xs font-mono text-sky-300 overflow-x-auto">
              {buildMCPExample(tool)}
            </pre>
          </div>

          {/* Action bar */}
          <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-gray-800">
            <VSCodeButton filePath={tool.filePath} lineNumber={tool.lineNumber} />
            <span className="text-gray-600 text-xs font-mono">{tool.filePath}:{tool.lineNumber}</span>
            <div className="ml-auto">
              <ToolTestRunner tool={tool} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
