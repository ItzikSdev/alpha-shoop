import { AGENTS } from '../data/agents';
import { AgentCard } from '../components/AgentCard';
import { PipelineSimulator } from '../components/PipelineSimulator';

export function Agents() {
  return (
    <div className="p-8 max-w-5xl mx-auto space-y-8">

      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white">AI Agents</h1>
        <p className="text-gray-400 text-sm mt-1">
          5 LangGraph nodes in a Director → Worker loop. Director routes on every iteration;
          workers return control to Director after completing their task.
        </p>
      </div>

      {/* Pipeline Simulator */}
      <PipelineSimulator />

      {/* Graph flow */}
      <div className="bg-gray-900 border border-gray-700 rounded-xl p-4">
        <div className="text-gray-500 text-xs uppercase tracking-wide mb-3">LangGraph node flow</div>
        <div className="flex items-center gap-2 flex-wrap justify-center text-sm">
          {[
            'Director (Opus)',
            '→',
            'Trend Scraper (Haiku)',
            '→',
            'E-com Manager (Sonnet)',
            '→',
            'Marketing (Sonnet)',
            '→',
            'Fulfillment (Haiku)',
            '↺ loop',
          ].map((t, i) => (
            <span
              key={i}
              className={
                t.startsWith('→') || t.startsWith('↺')
                  ? 'text-gray-600 font-mono text-lg'
                  : 'px-2 py-0.5 rounded bg-gray-800 border border-gray-700 text-gray-300 font-mono text-xs'
              }
            >
              {t}
            </span>
          ))}
        </div>
        <p className="text-gray-600 text-xs text-center mt-3">
          Fulfillment runs out-of-band — triggered by Shopify Order webhook, not by the Director.
        </p>
      </div>

      {/* Agent cards */}
      <div>
        <div className="text-gray-500 text-xs uppercase tracking-wide mb-4">Agent definitions</div>
        <div className="grid gap-4 md:grid-cols-2">
          {AGENTS.map(agent => (
            <AgentCard key={agent.id} agent={agent} />
          ))}
        </div>
      </div>
    </div>
  );
}
