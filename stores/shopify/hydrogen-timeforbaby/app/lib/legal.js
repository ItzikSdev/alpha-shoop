import {config} from './theme';

/**
 * Content for the two pages Shopify does NOT generate: Accessibility Statement
 * and Contact. Everything else (Privacy / Refund / Shipping / Terms of Service)
 * is pulled LIVE from Shopify (admin → Settings → Legal) via routes/policies.$handle.jsx —
 * Shopify is the single source of truth for those.
 *
 * Built from theme.config.json → legal. NOT legal advice; fill the business details.
 * Each doc: { title, updated?, intro?, sections: [{ title, blocks: [{p}|{list}] }] }
 */

const L = config.legal || {};
const BRAND = config.brand?.name || 'the Store';
const EMAIL = L.contactEmail || config.brand?.supportEmail || '';

// Show a value, or a clearly-marked TODO so the owner knows to fill it (template only).
function v(val, todo) {
  return val && String(val).trim() ? val : `[TODO: ${todo}]`;
}

export function getPolicy(slug) {
  switch (slug) {
    case 'accessibility':
      return {
        title: 'Accessibility Statement',
        updated: L.accessibility?.lastReviewed || L.lastUpdated,
        intro: `${BRAND} is committed to making our website accessible to everyone, including people with disabilities.`,
        sections: [
          {title: 'Our commitment', blocks: [
            {p: `We aim to conform to ${L.accessibility?.standard || 'WCAG 2.1 Level AA'} and relevant accessibility regulations. Accessibility is an ongoing effort and we keep improving.`},
          ]},
          {title: 'Measures taken', blocks: [
            {list: [
              'Semantic HTML, keyboard-navigable controls and visible focus states.',
              'Alt text on product images, sufficient color contrast, responsive text sizing.',
              'Labels and ARIA on interactive elements (cart, search, menus).',
            ]},
          ]},
          {title: 'Known limitations', blocks: [
            {p: 'Some third-party content or older items may not yet be fully accessible. We are working to fix these.'},
          ]},
          {title: 'Accessibility coordinator', blocks: [
            {p: 'If you encounter an accessibility barrier, contact our accessibility coordinator:'},
            {list: [
              `Name: ${v(L.accessibility?.coordinatorName, 'coordinator name (legally required)')}`,
              `Email: ${L.accessibility?.coordinatorEmail || EMAIL}`,
              `Phone: ${v(L.accessibility?.coordinatorPhone, 'coordinator phone')}`,
            ]},
          ]},
        ],
      };

    case 'contact':
      return {
        title: 'Contact Us',
        updated: L.lastUpdated,
        intro: 'We are a real business and happy to help. The fastest way to reach us is by email.',
        sections: [
          {title: 'Customer support', blocks: [
            {p: `Email: ${EMAIL} — we reply within 1–2 business days.`},
          ]},
          {title: 'Business details', blocks: [
            {p: `${BRAND} is operated by ${v(L.legalEntityName, 'registered business / legal entity name')} (registration no. ${v(L.companyNumber, 'company / business number')}), registered in ${L.registeredCountry || '[TODO: country]'}.`},
            {p: `Business address: ${v(L.businessAddress, 'business address — do NOT use a fake address')}.`},
            {p: `Contact: ${EMAIL}${L.contactPhone ? ` · ${L.contactPhone}` : ''}.`},
          ]},
        ],
      };

    default:
      return null;
  }
}
