// Shapes mirror the API (src/org/models.py to_public, src/org/inbox.py, src/org/tickets.py).

export interface AgentPublic {
  agent_id: string;
  name: string;
  role: string;
  skill: string;
  team: string;
  status: string;
  task?: string;
  last_result?: Record<string, unknown>;
}

export interface Msg { ts: string; name: string; role: string; text: string }

export interface Capability {
  agent: string;
  ok: boolean;
  connected: string[];
  not_connected: { tool: string; missing_env: string[]; error?: string }[];
  missing_tools: { need: string; why: string; fix: string }[];
}

export interface InboxItem {
  id: string;
  kind: 'social_draft' | 'proposal' | 'connection' | 'missing_tool' | 'blocker';
  decide: boolean;
  title: string;
  agent: string;
  context: string;
  status: string;
  created_at: string | null;
  summary: string;
  body: string;
  media_url: string;
  link: string;
  error: string | null;
}

export interface Ticket {
  id: string;
  title: string;
  assignee: string;
  status: string;
  priority: string;
  due_at: string;
  created_at: string;
}

export interface Meeting { meeting_id: string; kind: string; held_at: string; attendees: string[] }

export type AgentState = 'speaking' | 'working' | 'waiting' | 'meeting' | 'gym';

export const STATE_COLOR: Record<AgentState, string> = {
  speaking: '#16a34a',
  working: '#16a34a',
  waiting: '#d97706',
  meeting: '#2563eb',
  gym: '#94a3b8',
};

export const STATE_LABEL: Record<AgentState, string> = {
  speaking: 'מדבר',
  working: 'עובד',
  waiting: 'ממתין לך',
  meeting: 'בישיבה',
  gym: 'בחדר הכושר',
};

export const ROLE_COLOR: Record<string, string> = {
  CEO: '#f5b942',
  'Product Sourcer & Copywriter': '#38bdf8',
  'Video Producer': '#f472b6',
  'Social Media Manager': '#e879f9',
  'Customer Support': '#a78bfa',
  Fulfillment: '#34d399',
  'Growth Marketing Analyst': '#fb923c',
  Nova: '#2dd4bf',
};
export const colorFor = (role: string) => ROLE_COLOR[role] ?? '#94a3b8';

export function timeAgo(iso: string | null | undefined): string {
  if (!iso) return '';
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (Number.isNaN(s)) return '';
  if (s < 60) return 'עכשיו';
  if (s < 3600) return `לפני ${Math.round(s / 60)} ד׳`;
  if (s < 86400) return `לפני ${Math.round(s / 3600)} ש׳`;
  return new Date(iso).toLocaleDateString('he-IL');
}
