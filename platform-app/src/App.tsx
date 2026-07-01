import { useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Sidebar } from './components/Sidebar';
import { Overview } from './pages/Overview';
import { MCPTools } from './pages/MCPTools';
import { Agents } from './pages/Agents';
import { Endpoints } from './pages/Endpoints';
import { Architecture } from './pages/Architecture';
import { Technologies } from './pages/Technologies';
import { FinancePage } from './pages/FinancePage';
import { IntegrationsPage } from './pages/IntegrationsPage';
import { AgentLogsPage } from './pages/AgentLogsPage';
import { StoresPage } from './pages/StoresPage';
import { TicketsPage } from './pages/TicketsPage';
import { Company } from './pages/Company';

export default function App() {
  const [menuOpen, setMenuOpen] = useState(false);
  return (
    <BrowserRouter>
      <div className="flex min-h-screen bg-gray-950 text-gray-200">
        <Sidebar open={menuOpen} onClose={() => setMenuOpen(false)} />

        {/* Mobile backdrop when the drawer is open */}
        {menuOpen && (
          <div
            className="fixed inset-0 z-30 bg-black/60 md:hidden"
            onClick={() => setMenuOpen(false)}
            aria-hidden
          />
        )}

        <main className="flex-1 min-w-0 overflow-y-auto">
          {/* Mobile top bar with hamburger (hidden on desktop) */}
          <header className="md:hidden sticky top-0 z-20 flex items-center gap-3 border-b border-gray-800 bg-gray-950/95 px-4 py-3 backdrop-blur">
            <button
              onClick={() => setMenuOpen(true)}
              aria-label="Open menu"
              className="grid h-9 w-9 place-items-center rounded-lg text-xl text-gray-200 hover:bg-gray-800"
            >
              ☰
            </button>
            <span className="font-bold text-white">Alpha Shoop</span>
          </header>

          <Routes>
            <Route path="/" element={<Overview />} />
            <Route path="/company" element={<Company />} />
            <Route path="/finance" element={<FinancePage />} />
            <Route path="/integrations" element={<IntegrationsPage />} />
            <Route path="/agent-logs" element={<AgentLogsPage />} />
            <Route path="/stores" element={<StoresPage />} />
            <Route path="/tickets" element={<TicketsPage />} />
            <Route path="/tools" element={<MCPTools />} />
            <Route path="/agents" element={<Agents />} />
            <Route path="/endpoints" element={<Endpoints />} />
            <Route path="/architecture" element={<Architecture />} />
            <Route path="/technologies" element={<Technologies />} />
            {/* Live Runs retired — redirect any old links to Finance */}
            <Route path="/runs" element={<Navigate to="/finance" replace />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
