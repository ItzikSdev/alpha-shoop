import { NavLink } from 'react-router-dom';

// Swagger/ReDoc live on the SAME host the dashboard is served from (so the links
// work on a phone too, not just localhost).
const API_HOST = typeof window !== 'undefined' ? window.location.hostname : 'localhost';
const API_BASE = `http://${API_HOST}:8000`;

const NAV: { path: string; icon: string; label: string; highlight?: boolean }[] = [
  { path: '/', icon: '🏠', label: 'Overview' },
  { path: '/company', icon: '🏢', label: 'The Company', highlight: true },
  { path: '/finance', icon: '💰', label: 'Finance', highlight: true },
  { path: '/integrations', icon: '🔌', label: 'Integrations' },
  { path: '/agent-logs', icon: '💬', label: 'Agent Logs' },
  { path: '/stores', icon: '🏪', label: 'My Stores' },
  { path: '/tools', icon: '🧩', label: 'MCP Tools' },
  { path: '/agents', icon: '🤖', label: 'AI Agents' },
  { path: '/endpoints', icon: '⚡', label: 'API Endpoints' },
  { path: '/architecture', icon: '🗺️', label: 'Architecture' },
  { path: '/technologies', icon: '🎨', label: 'Technologies' },
];

export function Sidebar({ open = false, onClose }: { open?: boolean; onClose?: () => void }) {
  return (
    // Mobile: a fixed off-canvas drawer that slides in when `open` (with a backdrop
    // rendered by App). Desktop (md+): a normal sticky in-flow column, unchanged.
    <aside
      className={`fixed inset-y-0 left-0 z-40 h-screen w-64 shrink-0 bg-gray-950 border-r border-gray-800 flex flex-col
        transform transition-transform duration-200 ease-out
        ${open ? 'translate-x-0' : '-translate-x-full'}
        md:sticky md:top-0 md:w-56 md:translate-x-0`}
    >
      {/* Logo */}
      <div className="p-4 border-b border-gray-800 flex items-center justify-between">
        <div>
          <div className="font-bold text-white text-lg">Alpha Shoop</div>
          <div className="text-gray-500 text-xs mt-0.5">Autonomous Arbitrage System</div>
        </div>
        {/* Close (mobile only) */}
        <button
          onClick={onClose}
          aria-label="Close menu"
          className="md:hidden grid h-8 w-8 place-items-center rounded-lg text-gray-400 hover:bg-gray-800 hover:text-gray-200"
        >
          ✕
        </button>
      </div>

      {/* Quick links */}
      <div className="p-3 border-b border-gray-800">
        <a
          href={`${API_BASE}/docs`}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-2 px-2 py-1.5 rounded-lg text-xs text-teal-400 hover:bg-teal-900/30 hover:text-teal-300 transition-colors"
        >
          <span>⚡</span>
          <span>FastAPI Swagger UI</span>
          <span className="ml-auto opacity-50">↗</span>
        </a>
        <a
          href={`${API_BASE}/redoc`}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-2 px-2 py-1.5 rounded-lg text-xs text-teal-400 hover:bg-teal-900/30 hover:text-teal-300 transition-colors"
        >
          <span>📖</span>
          <span>FastAPI ReDoc</span>
          <span className="ml-auto opacity-50">↗</span>
        </a>
      </div>

      {/* Nav */}
      <nav className="flex-1 p-3 space-y-0.5 overflow-y-auto">
        {NAV.map(item => (
          <NavLink
            key={item.path}
            to={item.path}
            end={item.path === '/'}
            onClick={onClose}
            className={({ isActive }) =>
              `w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm text-left transition-colors ${isActive
                ? 'bg-indigo-900/60 text-indigo-200 font-medium'
                : item.highlight
                  ? 'text-emerald-400 hover:text-emerald-300 hover:bg-emerald-900/20'
                  : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/60'
              }`
            }
          >
            {({ isActive }) => (
              <>
                <span>{item.icon}</span>
                <span>{item.label}</span>
                {item.highlight && !isActive && (
                  <span className="ml-auto w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                )}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="p-4 border-t border-gray-800 text-xs text-gray-600 space-y-1">
        <div>FastAPI: <span className="text-gray-500">:8000</span></div>
        <div>React Docs: <span className="text-gray-500">:5173</span></div>
      </div>
    </aside>
  );
}