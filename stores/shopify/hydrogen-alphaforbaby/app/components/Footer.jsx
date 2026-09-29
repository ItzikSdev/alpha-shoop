import {Link} from 'react-router';
import {config} from '~/lib/theme';

/**
 * One footer link column.
 *
 * Rendered as a native <details> so it collapses to a single heading row on
 * mobile and stays open on desktop (CSS forces `open` behaviour at >=861px).
 * Twelve always-expanded links made the footer 604px tall on a 375px screen —
 * taller than the product grid — and no amount of gap-tightening gets that
 * under the 420px target; the list length is the height. <details> gives the
 * collapse with no JS, real keyboard support and no ARIA of our own to get
 * wrong, and it degrades to a plain expanded list if CSS fails to load.
 */
function FooterCol({heading, children}) {
  return (
    <details className="tob-fcol" name="footer-col">
      <summary>
        <b>{heading}</b>
      </summary>
      <div className="tob-fcol-links">{children}</div>
    </details>
  );
}

// Dark footer — brand, Shop links (= nav), Support and legal links all from theme.config.json.
export function Footer() {
  const {name, tagline, supportEmail, copyright} = config.brand;
  const legalLinks = config.legalLinks || [];
  const payIcons = config.paymentIcons || [];
  const nameParts = name.match(/^(.*) FOR (.*)$/);
  return (
    <footer className="tob-footer">
      <div className="tob-wrap tob-fcols">
        <div className="tob-fbrand">
          <div className="tob-flogo">
            <img
              src={config.brand.logoImage}
              alt={name}
              width="28"
              height="28"
              className="tob-flogo-icon"
              loading="lazy"
            />
            {nameParts ? (
              <span>
                {nameParts[1]} <span className="tob-hlogo-accent">FOR</span> {nameParts[2]}
              </span>
            ) : (
              name
            )}
          </div>
          <p>{tagline}</p>
        </div>

        <FooterCol heading="Shop">
          {config.nav.map((l) => (
            <Link key={l.url} to={l.url} prefetch="intent">
              {l.label}
            </Link>
          ))}
        </FooterCol>

        <FooterCol heading="Support">
          <a href={`mailto:${supportEmail}`}>{supportEmail}</a>
        </FooterCol>

        <FooterCol heading="Legal">
          {legalLinks.map((l) => (
            <Link key={l.url} to={l.url} prefetch="intent">
              {l.label}
            </Link>
          ))}
        </FooterCol>
      </div>

      {payIcons.length ? (
        <div className="tob-wrap tob-fpay" aria-label="Accepted payments">
          {payIcons.map((p) => (
            <img
              key={p.src}
              src={p.src}
              alt={p.alt}
              className="tob-fpay-ico"
              width="34"
              height="23"
              loading="lazy"
            />
          ))}
        </div>
      ) : null}

      <div className="tob-wrap tob-fbottom">{copyright}</div>
    </footer>
  );
}
