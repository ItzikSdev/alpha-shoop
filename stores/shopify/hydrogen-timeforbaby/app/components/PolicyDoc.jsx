/**
 * Renders a legal/policy document (from app/lib/legal.js) in the store design.
 * @param {{doc: {title: string, updated?: string, intro?: string, sections: Array}}}
 */
export function PolicyDoc({doc}) {
  if (!doc) return null;
  return (
    <article className="tobp-legal">
      <h1>{doc.title}</h1>
      {doc.updated && <p className="legal-updated">Last updated: {doc.updated}</p>}
      {doc.intro && <p className="legal-intro">{doc.intro}</p>}
      {doc.sections.map((section) => (
        <section key={section.title}>
          <h2>{section.title}</h2>
          {section.blocks.map((block, i) =>
            block.list ? (
              <ul key={i}>
                {block.list.map((item, j) => (
                  <li key={j}>{item}</li>
                ))}
              </ul>
            ) : (
              <p key={i}>{block.p}</p>
            ),
          )}
        </section>
      ))}
    </article>
  );
}
