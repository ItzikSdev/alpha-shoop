import { TECHNOLOGIES } from '../data/technologies';

interface Props {
  techId: string;
  size?: 'sm' | 'md';
}

export function TechBadge({ techId, size = 'md' }: Props) {
  const tech = TECHNOLOGIES[techId];
  if (!tech) return null;

  const pad = size === 'sm' ? 'px-1.5 py-0.5 text-[10px]' : 'px-2 py-1 text-xs';

  return (
    <a
      href={tech.docsUrl}
      target="_blank"
      rel="noopener noreferrer"
      title={tech.description}
      className={`inline-flex items-center gap-1 rounded-full font-semibold whitespace-nowrap transition-opacity hover:opacity-80 ${pad}`}
      style={{ backgroundColor: tech.bg, color: tech.color, border: `1px solid ${tech.border}` }}
    >
      <span>{tech.icon}</span>
      <span>{tech.name}</span>
    </a>
  );
}
