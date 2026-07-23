import {Link} from 'react-router';
import {config} from '~/lib/theme';

// Dark footer — brand, Shop links (= nav), Support and legal links all from theme.config.json.
export function Footer() {
  const {name, tagline, supportEmail, copyright} = config.brand;
  const legalLinks = config.legalLinks || [];
  const payIcons = config.paymentIcons || [];
  return (
    <footer className="tob-footer">
      <div className="tob-wrap tob-fcols">
        <div className="tob-fbrand">
          <div className="tob-flogo">{name}</div>
          <p>{tagline}</p>
        </div>

        <div className="tob-fcol">
          <b>Shop</b>
          {config.nav.map((l) => (
            <Link key={l.url} to={l.url} prefetch="intent">
              {l.label}
            </Link>
          ))}
        </div>

        <div className="tob-fcol">
          <b>Support</b>
          <a href={`mailto:${supportEmail}`}>{supportEmail}</a>
        </div>

        <div className="tob-fcol">
          <b>Legal</b>
          {legalLinks.map((l) => (
            <Link key={l.url} to={l.url} prefetch="intent">
              {l.label}
            </Link>
          ))}
        </div>
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
