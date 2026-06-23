import type { Agent } from '../types';
import { TechBadge } from './TechBadge';
import { VSCodeButton } from './ActionButtons';
import { MCP_TOOLS } from '../data/tools';

interface Props {
  agent: Agent;
}

const MODEL_LABELS: Record<string, string> = {
  'claude-opus-4-8': 'Opus 4.8',
  'claude-sonnet-4-6': 'Sonnet 4.6',
  'claude-haiku-4-5-20251001': 'Haiku 4.5',
};

export function AgentCard({ agent }: Props) {
  const tools = MCP_TOOLS.filter(t => agent.toolIds.includes(t.id));

  return (
    <div
      className="bg-gray-900 border rounded-xl p-5 hover:shadow-lg transition-shadow"
      style={{ borderColor: agent.color + '60' }}
    >
      {/* Header */}
      <div className="flex items-start gap-3">
        <div
          className="w-10 h-10 rounded-lg flex items-center justify-center text-xl shrink-0"
          style={{ backgroundColor: agent.color + '20', border: `1px solid ${agent.color}40` }}
        >
          🤖
        </div>
        <div className="flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="font-bold text-white">{agent.name}</h3>
            <span
              className="text-xs px-2 py-0.5 rounded-full font-mono"
              style={{ backgroundColor: agent.color + '20', color: agent.color, border: `1px solid ${agent.color}40` }}
            >
              {MODEL_LABELS[agent.model] || agent.model}
            </span>
          </div>
          <p className="text-gray-400 text-sm mt-1">{agent.description}</p>
        </div>
      </div>

      {/* Technologies */}
      <div className="mt-4">
        <span className="text-gray-500 text-xs uppercase tracking-wide">Technologies</span>
        <div className="flex flex-wrap gap-1 mt-1.5">
          {agent.techIds.map(id => <TechBadge key={id} techId={id} />)}
        </div>
      </div>

      {/* MCP Tools used */}
      {tools.length > 0 && (
        <div className="mt-4">
          <span className="text-gray-500 text-xs uppercase tracking-wide">MCP Tools Used</span>
          <div className="mt-2 space-y-1">
            {tools.map(tool => (
              <div key={tool.id} className="flex items-center gap-2 text-xs">
                <span className="text-violet-400 font-mono">{tool.name}</span>
                <span className="text-gray-600">—</span>
                <span className="text-gray-500 truncate">{tool.description.split('.')[0]}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Footer */}
      <div className="mt-4 pt-3 border-t border-gray-800 flex items-center gap-2">
        <VSCodeButton filePath={agent.filePath} lineNumber={agent.lineNumber} />
        <span className="text-gray-600 text-xs font-mono">{agent.filePath}:{agent.lineNumber}</span>
      </div>
    </div>
  );
}
