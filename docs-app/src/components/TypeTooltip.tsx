import { useState, useRef, useEffect } from 'react';
import type { TypeSchema } from '../types';

interface Props {
  schema: TypeSchema;
  children: React.ReactNode;
}

export function TypeTooltip({ schema, children }: Props) {
  const [visible, setVisible] = useState(false);
  const [pos, setPos] = useState({ top: 0, left: 0 });
  const triggerRef = useRef<HTMLSpanElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!visible || !triggerRef.current || !tooltipRef.current) return;
    const rect = triggerRef.current.getBoundingClientRect();
    const tooltip = tooltipRef.current;
    const winH = window.innerHeight;
    const top = rect.bottom + 6 + window.scrollY;
    const left = Math.min(rect.left + window.scrollX, window.innerWidth - tooltip.offsetWidth - 12);
    // Flip above if not enough space below
    const finalTop = rect.bottom + tooltip.offsetHeight + 12 > winH
      ? rect.top - tooltip.offsetHeight - 6 + window.scrollY
      : top;
    setPos({ top: finalTop, left: Math.max(8, left) });
  }, [visible]);

  return (
    <>
      <span
        ref={triggerRef}
        className="cursor-help text-sky-400 hover:text-sky-300 underline decoration-dotted font-mono text-xs transition-colors"
        onMouseEnter={() => setVisible(true)}
        onMouseLeave={() => setVisible(false)}
      >
        {children}
      </span>

      {visible && (
        <div
          ref={tooltipRef}
          className="fixed z-50 bg-gray-950 border border-gray-600 rounded-lg shadow-2xl p-3 min-w-[260px] max-w-[420px] pointer-events-none"
          style={{ top: pos.top, left: pos.left }}
        >
          {/* Header */}
          <div className="flex items-center gap-2 mb-2 pb-2 border-b border-gray-700">
            <span className="text-yellow-400 text-xs font-mono font-bold">{schema.name}</span>
            {schema.description && (
              <span className="text-gray-500 text-xs truncate">{schema.description}</span>
            )}
          </div>

          {/* Fields */}
          <div className="space-y-1.5">
            {schema.fields.map(f => (
              <div key={f.name} className="grid grid-cols-[auto_1fr] gap-x-2 text-xs">
                <span className={`font-mono ${f.required ? 'text-blue-300' : 'text-gray-400'}`}>
                  {f.name}{f.required ? '' : '?'}:
                </span>
                <span className="font-mono text-emerald-400">{f.type}</span>
                {f.description && (
                  <span className="col-span-2 text-gray-500 pl-1 truncate">{f.description}</span>
                )}
              </div>
            ))}
          </div>

          {/* Legend */}
          <div className="mt-2 pt-2 border-t border-gray-800 flex gap-3 text-[10px] text-gray-600">
            <span><span className="text-blue-300">name</span>: required</span>
            <span><span className="text-gray-400">name?</span>: optional</span>
          </div>
        </div>
      )}
    </>
  );
}
