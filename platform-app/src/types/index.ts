export interface Technology {
  id: string;
  name: string;
  color: string;
  bg: string;
  border: string;
  icon: string;
  docsUrl: string;
  category: 'ai' | 'backend' | 'database' | 'external-api' | 'infrastructure' | 'protocol';
  description: string;
}

export interface TypeField {
  name: string;
  type: string;
  required: boolean;
  description: string;
  example?: string | number | boolean | null;
}

export interface TypeSchema {
  name: string;
  description?: string;
  fields: TypeField[];
}

export interface MCPTool {
  id: string;
  groupId: string;
  groupName: string;
  name: string;
  description: string;
  techIds: string[];
  filePath: string;
  lineNumber: number;
  input: TypeSchema;
  output: TypeSchema;
  exampleArgs: Record<string, unknown>;
}

export interface ToolGroup {
  id: string;
  name: string;
  description: string;
  icon: string;
  tools: MCPTool[];
}

export interface Agent {
  id: string;
  name: string;
  model: string;
  nodeId: string;
  description: string;
  techIds: string[];
  toolIds: string[];
  color: string;
  filePath: string;
  lineNumber: number;
}

export type HttpMethod = 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH';

export interface APIEndpoint {
  id: string;
  method: HttpMethod;
  path: string;
  description: string;
  handlerFn: string;
  filePath: string;
  lineNumber: number;
  techIds: string[];
  tags: string[];
  requiresAuth: boolean;
  requestBody?: TypeSchema;
  response: TypeSchema;
}

export type Page = 'overview' | 'tools' | 'agents' | 'endpoints' | 'architecture' | 'technologies' | 'runs' | 'stores';
