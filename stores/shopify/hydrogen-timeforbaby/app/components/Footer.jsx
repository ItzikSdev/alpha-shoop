import {Link} from 'react-router';
import {config} from '~/lib/theme';

// CCPA "Do Not Sell or Share" — open Shopify's privacy preferences if the built-in
// privacy banner is active; otherwise fall through to the Privacy Policy link.
function openPrivacyChoices(e) {
  if (typeof window !== 'undefined' && window.privacyBanner?.showPreferences) {
    e.preventDefault();
    window.privacyBanner.showPreferences();
  }
}

// Dark footer — brand, Shop links (= nav), Support and legal links all from theme.config.json.
export function Footer() {
  const {name, tagline, supportEmail, copyright} = config.brand;
  const legalLinks = config.legalLinks || [];
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

      {/* CCPA/CPRA required footer control */}
      <div className="tob-wrap tob-fchoices">
        <a
          href="/policies/privacy-policy"
          onClick={openPrivacyChoices}
          className="tob-dns"
        >
          Do Not Sell or Share My Personal Information
        </a>
      </div>

      <div className="tob-wrap tob-fbottom">{copyright}</div>
    </footer>
  );
}
