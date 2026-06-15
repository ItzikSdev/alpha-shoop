import { TECH_LIST } from '../data/technologies';
import type { Technology } from '../types';

const CATEGORIES: { id: Technology['category']; label: string; icon: string }[] = [
  { id: 'ai', label: 'AI / LLM', icon: '🧠' },
  { id: 'backend', label: 'Backend', icon: '⚡' },
  { id: 'external-api', label: 'External APIs', icon: '🌐' },
  { id: 'database', label: 'Databases', icon: '💾' },
  { id: 'infrastructure', label: 'Infrastructure', icon: '🏗️' },
  { id: 'protocol', label: 'Protocols', icon: '🔌' },
];

export function Technologies() {
  return (
    <div className="p-8 max-w-5xl mx-auto space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-white">Technologies</h1>
        <p className="text-gray-400 text-sm mt-1">
          Every technology used in Alpha Shoop, with its role, color badge, and link to documentation.
        </p>
      </div>

      {CATEGORIES.map(cat => {
        const techs = TECH_LIST.filter(t => t.category === cat.id);
        if (!techs.length) return null;
        return (
          <div key={cat.id}>
            <h2 className="text-lg font-bold text-gray-300 mb-3 flex items-center gap-2">
              <span>{cat.icon}</span>
              <span>{cat.label}</span>
            </h2>
            <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-3">
              {techs.map(tech => (
                <a
                  key={tech.id}
                  href={tech.docsUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="bg-gray-900 border border-gray-700 rounded-xl p-4 hover:border-gray-500 transition-colors group block"
                >
                  <div className="flex items-center gap-3 mb-2">
                    {/* Badge preview */}
                    <span
                      className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-semibold"
                      style={{ backgroundColor: tech.bg, color: tech.color, border: `1px solid ${tech.border}` }}
                    >
                      {tech.icon} {tech.name}
                    </span>
                  </div>
                  <p className="text-gray-400 text-xs leading-relaxed">{tech.description}</p>
                  <p className="text-gray-600 text-xs mt-2 group-hover:text-gray-400 transition-colors">
                    {tech.docsUrl.replace('https://', '')} ↗
                  </p>
                </a>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
