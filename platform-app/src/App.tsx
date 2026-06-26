import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Sidebar } from './components/Sidebar';
import { Overview } from './pages/Overview';
import { MCPTools } from './pages/MCPTools';
import { Agents } from './pages/Agents';
import { Endpoints } from './pages/Endpoints';
import { Architecture } from './pages/Architecture';
import { Technologies } from './pages/Technologies';
import { RunsPage } from './pages/RunsPage';
import { StoresPage } from './pages/StoresPage';
import { Company } from './pages/Company';

export default function App() {
  return (
    <BrowserRouter>
      <div className="flex min-h-screen bg-gray-950 text-gray-200">
        <Sidebar />
        <main className="flex-1 overflow-y-auto">
          <Routes>
            <Route path="/" element={<Overview />} />
            <Route path="/company" element={<Company />} />
            <Route path="/runs" element={<RunsPage />} />
            <Route path="/stores" element={<StoresPage />} />
            <Route path="/tools" element={<MCPTools />} />
            <Route path="/agents" element={<Agents />} />
            <Route path="/endpoints" element={<Endpoints />} />
            <Route path="/architecture" element={<Architecture />} />
            <Route path="/technologies" element={<Technologies />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
