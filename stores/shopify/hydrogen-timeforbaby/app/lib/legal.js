import {config} from './theme';

/**
 * Content for the two pages Shopify does NOT generate: Accessibility Statement
 * and Contact. Everything else (Privacy / Refund / Shipping / Terms of Service)
 * is pulled LIVE from Shopify via routes/policies.$handle.jsx.
 *
 * Built from theme.config.json → legal. Fields that are empty are OMITTED (no
 * placeholder text shown). NOT legal advice.
 */

const L = config.legal || {};
const BRAND = config.brand?.name || 'the Store';
const EMAIL = L.contactEmail || config.brand?.supportEmail || '';

export function getPolicy(slug) {
  switch (slug) {
    case 'accessibility': {
      const coord = L.accessibility || {};
      const clist = [];
      if (coord.coordinatorName) clist.push(`Name: ${coord.coordinatorName}`);
      clist.push(`Email: ${coord.coordinatorEmail || EMAIL}`);
      if (coord.coordinatorPhone) clist.push(`Phone: ${coord.coordinatorPhone}`);
      return {
        title: 'Accessibility Statement',
        updated: coord.lastReviewed || L.lastUpdated,
        intro: `${BRAND} is committed to making our website accessible to everyone, including people with disabilities.`,
        sections: [
          {title: 'Our commitment', blocks: [
            {p: `We aim to conform to ${coord.standard || 'WCAG 2.1 Level AA'} and relevant accessibility regulations. Accessibility is an ongoing effort and we keep improving.`},
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
          {title: 'Contact us about accessibility', blocks: [
            {p: 'If you encounter an accessibility barrier, please contact us:'},
            {list: clist},
          ]},
        ],
      };
    }

    case 'contact': {
      const entity = L.legalEntityName || BRAND;
      let line = `${BRAND} is operated by ${entity}`;
      if (L.companyNumber) line += ` (registration no. ${L.companyNumber})`;
      if (L.registeredCountry) line += `, registered in ${L.registeredCountry}`;
      line += '.';
      const bits = [{p: line}];
      if (L.businessAddress) bits.push({p: `Business address: ${L.businessAddress}.`});
      bits.push({p: `Contact: ${EMAIL}${L.contactPhone ? ` · ${L.contactPhone}` : ''}.`});
      return {
        title: 'Contact Us',
        updated: L.lastUpdated,
        intro: 'We are a real business and happy to help. The fastest way to reach us is by email.',
        sections: [
          {title: 'Customer support', blocks: [
            {p: `Email: ${EMAIL} — we reply within 1–2 business days.`},
          ]},
          {title: 'Business details', blocks: bits},
        ],
      };
    }

    default:
      return null;
  }
}
