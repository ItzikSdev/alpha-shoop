import { useState } from 'react';
import type { Page } from './types';
import { Sidebar } from './components/Sidebar';
import { Overview } from './pages/Overview';
import { MCPTools } from './pages/MCPTools';
import { Agents } from './pages/Agents';
import { Endpoints } from './pages/Endpoints';
import { Architecture } from './pages/Architecture';
import { Technologies } from './pages/Technologies';

export default function App() {
  const [page, setPage] = useState<Page>('overview');

  const content = {
    overview: <Overview onNavigate={setPage} />,
    tools: <MCPTools />,
    agents: <Agents />,
    endpoints: <Endpoints />,
    architecture: <Architecture />,
    technologies: <Technologies />,
  }[page];

  return (
    <div className="flex min-h-screen bg-gray-950 text-gray-200">
      <Sidebar current={page} onNavigate={setPage} />
      <main className="flex-1 overflow-y-auto">
        {content}
      </main>
    </div>
  );
}
