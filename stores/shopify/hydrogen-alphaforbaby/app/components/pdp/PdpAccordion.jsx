import {useState} from 'react';
import {ChevronDown} from 'lucide-react';

/**
 * Q&A accordion. One component serves both the "Size guide & shipping" block
 * and the FAQ — same {question, answer} shape, different heading.
 *
 * @param {{heading?: string, items: Array<{question: string, answer: string}>}}
 */
export function PdpAccordion({
  heading = 'Frequently asked questions', items = [], sectionId = 'faq',
}) {
  const [open, setOpen] = useState(null);
  if (!items.length) return null;

  return (
    <section className="pt-10" data-accordion data-section={sectionId}>
      <h2 className="m-0 text-ch2 font-normal">{heading}</h2>
      <ul className="mt-3 list-none border-t border-divider p-0">
        {items.map((item, i) => {
          const isOpen = open === i;
          return (
            <li key={item.question} className="border-b border-divider">
              <button
                type="button"
                aria-expanded={isOpen}
                onClick={() => setOpen(isOpen ? null : i)}
                className="flex w-full items-center justify-between gap-4 py-3.5 text-left"
              >
                <span className="text-[14.5px] font-semibold">{item.question}</span>
                <ChevronDown
                  size={18}
                  className={`flex-none transition-transform ${isOpen ? 'rotate-180' : ''}`}
                />
              </button>
              {isOpen && (
                <p className="mb-4 mt-0 max-w-2xl text-[14px] leading-[1.55] text-ink/75">{item.answer}</p>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
