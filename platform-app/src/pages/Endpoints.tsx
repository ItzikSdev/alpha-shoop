import { ENDPOINTS } from '../data/endpoints';
import { EndpointCard } from '../components/EndpointCard';

export function Endpoints() {
  return (
    <div className="p-8 max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">API Endpoints</h1>
        <p className="text-gray-400 text-sm mt-1">
          Expand any endpoint to see its Pydantic types (hover for schema), copy a cURL command,
          open the handler in VSCode, or run a live test against{' '}
          <code className="text-teal-400 text-xs">localhost:8000</code>.
        </p>
        <div className="mt-2 flex gap-2">
          <a
            href="http://localhost:8000/docs"
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-teal-400 hover:text-teal-300 underline"
          >
            ↗ Open FastAPI Swagger UI
          </a>
          <span className="text-gray-700">·</span>
          <a
            href="http://localhost:8000/redoc"
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-teal-400 hover:text-teal-300 underline"
          >
            ↗ Open ReDoc
          </a>
        </div>
      </div>

      <div className="space-y-3">
        {ENDPOINTS.map(ep => (
          <EndpointCard key={ep.id} endpoint={ep} />
        ))}
      </div>
    </div>
  );
}
