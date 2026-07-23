import config from '../theme.config.json';

/**
 * The whole storefront's look + content lives in app/theme.config.json.
 * Import this to read it, or call themeCss() to get the CSS-variable overrides
 * injected into <head> (so colors + font sizes are driven by the JSON).
 */
export {config};

/** Build the `.tob { --tob-*: … }` override block from the JSON tokens. */
export function themeCss() {
  const {colors = {}, fonts = {}, fontSizes = {}} = config.tokens || {};
  const vars = {
    '--tob-ink': colors.ink,
    '--tob-muted': colors.muted,
    '--tob-line': colors.line,
    '--tob-soft': colors.soft,
    '--tob-hero-bg': colors.heroBg,
    '--tob-hero-ink': colors.heroInk,
    '--tob-hero-accent': colors.heroAccent,
    '--tob-hero-eyebrow': colors.heroEyebrow,
    '--tob-footer-bg': colors.footerBg,
    '--tob-footer-text': colors.footerText,
    '--tob-star': colors.star,
    '--tob-verified': colors.verified,
    '--tob-font-body': fonts.body,
    '--tob-font-display': fonts.display,
    '--tob-fs-logo': fontSizes.logo,
    '--tob-fs-nav': fontSizes.nav,
    '--tob-fs-marquee': fontSizes.marquee,
    '--tob-fs-hero-eyebrow': fontSizes.heroEyebrow,
    '--tob-fs-hero-title': fontSizes.heroTitle,
    '--tob-fs-hero-sub': fontSizes.heroSub,
    '--tob-fs-button': fontSizes.button,
    '--tob-fs-section': fontSizes.sectionHeading,
    '--tob-fs-card-title': fontSizes.cardTitle,
    '--tob-fs-card-price': fontSizes.cardPrice,
    '--tob-fs-tile': fontSizes.tileLabel,
    '--tob-fs-pill': fontSizes.pill,
    '--tob-fs-testimonial': fontSizes.testimonial,
    '--tob-fs-footer': fontSizes.footer,
    '--tob-fs-product-title': fontSizes.productTitle,
    '--tob-fs-product-price': fontSizes.productPrice,
    '--tob-fs-option': fontSizes.optionButton,
    '--tob-fs-desc': fontSizes.description,
  };
  const body = Object.entries(vars)
    .filter(([, v]) => v != null && v !== '')
    .map(([k, v]) => `${k}:${v}`)
    .join(';');
  return `.tob{${body}}`;
}
