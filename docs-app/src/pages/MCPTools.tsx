import { useState } from 'react';
import { TOOL_GROUPS } from '../data/tools';
import { ToolCard } from '../components/ToolCard';

export function MCPTools() {
  const [activeGroup, setActiveGroup] = useState(TOOL_GROUPS[0].id);
  const group = TOOL_GROUPS.find(g => g.id === activeGroup)!;

  return (
    <div className="p-8 max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">MCP Tools</h1>
        <p className="text-gray-400 text-sm mt-1">
          10 tools across 5 groups. Expand any tool to see its type signature, copy a Python example, open the source in VSCode, or run a live test.
        </p>
      </div>

      {/* Group tabs */}
      <div className="flex flex-wrap gap-2">
        {TOOL_GROUPS.map(g => (
          <button
            key={g.id}
            onClick={() => setActiveGroup(g.id)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm transition-colors ${
              activeGroup === g.id
                ? 'bg-violet-900/70 text-violet-200 border border-violet-700'
                : 'bg-gray-800 text-gray-400 border border-gray-700 hover:text-gray-200'
            }`}
          >
            <span>{g.icon}</span>
            <span>{g.name}</span>
            <span className={`text-xs px-1.5 py-0.5 rounded-full ${activeGroup === g.id ? 'bg-violet-800 text-violet-200' : 'bg-gray-700 text-gray-500'}`}>
              {g.tools.length}
            </span>
          </button>
        ))}
      </div>

      {/* Group description */}
      <div className="bg-gray-900/50 border border-gray-700 rounded-lg p-3 flex items-center gap-3">
        <span className="text-2xl">{group.icon}</span>
        <p className="text-gray-300 text-sm">{group.description}</p>
      </div>

      {/* Tool cards */}
      <div className="space-y-3">
        {group.tools.map(tool => (
          <ToolCard key={tool.id} tool={tool} />
        ))}
      </div>
    </div>
  );
}
