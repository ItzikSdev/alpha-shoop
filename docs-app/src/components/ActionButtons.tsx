import { useState } from 'react';
import type { APIEndpoint, MCPTool } from '../types';

const PROJECT_ROOT = '/Users/itziksavaia/Documents/git/alpha-shoop';

// ── Copy Button ───────────────────────────────────────────────────────────────

interface CopyButtonProps {
  text: string;
  label?: string;
}

export function CopyButton({ text, label = 'Copy' }: CopyButtonProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  };

  return (
    <button
      onClick={handleCopy}
      title="Copy to clipboard"
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium transition-all border ${
        copied
          ? 'bg-emerald-900/50 text-emerald-300 border-emerald-700'
          : 'bg-gray-800 text-gray-300 border-gray-600 hover:bg-gray-700 hover:text-white'
      }`}
    >
      {copied ? '✓ Copied' : `📋 ${label}`}
    </button>
  );
}

// ── VSCode Button ─────────────────────────────────────────────────────────────

interface VSCodeButtonProps {
  filePath: string;
  lineNumber: number;
}

export function VSCodeButton({ filePath, lineNumber }: VSCodeButtonProps) {
  const vscodeUrl = `vscode://file/${PROJECT_ROOT}/${filePath}:${lineNumber}`;

  return (
    <a
      href={vscodeUrl}
      title={`Open ${filePath}:${lineNumber} in VSCode`}
      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium bg-gray-800 text-gray-300 border border-gray-600 hover:bg-blue-900/50 hover:text-blue-300 hover:border-blue-700 transition-all"
    >
      <span>⬡</span>
      <span>Open in VSCode</span>
    </a>
  );
}

// ── Curl generator ────────────────────────────────────────────────────────────

export function buildCurl(endpoint: APIEndpoint): string {
  const base = 'http://localhost:8000';
  const headers = [
    '-H "Content-Type: application/json"',
    ...(endpoint.requiresAuth ? ['-H "Authorization: Bearer $TOKEN"'] : []),
  ];

  let body = '';
  if (endpoint.requestBody) {
    const example: Record<string, unknown> = {};
    endpoint.requestBody.fields.forEach(f => {
      if (f.example !== undefined && f.example !== null) example[f.name] = f.example;
    });
    body = ` \\\n  -d '${JSON.stringify(example, null, 2).replace(/\n/g, '\n  ')}'`;
  }

  return `curl -X ${endpoint.method} "${base}${endpoint.path.replace('{thread_id}', 'YOUR_THREAD_ID')}" \\\n  ${headers.join(' \\\n  ')}${body}`;
}

// ── MCP call example ──────────────────────────────────────────────────────────

export function buildMCPExample(tool: MCPTool): string {
  return `# Python — direct MCP tool call\nimport asyncio\nfrom src.mcp_tools.server import invoke_tool\n\nresult = asyncio.run(invoke_tool(\n    "${tool.name}",\n    ${JSON.stringify(tool.exampleArgs, null, 4).replace(/\n/g, '\n    ')}\n))\nprint(result)`;
}
