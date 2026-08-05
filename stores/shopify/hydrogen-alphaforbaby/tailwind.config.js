import withMT from '@material-tailwind/react/utils/withMT.js';

/** @type {import('tailwindcss').Config} */
export default withMT({
  content: ['./app/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      // "Classical" design tokens (2026-08-02 product-page handoff) — cream/accent
      // palette used by the product detail page rebuild. See app/styles/app.css
      // for the CSS-variable mirror (.plate, .tnum, focus-visible) and
      // app/theme.config.json for the site-wide --tob-* palette these were
      // adapted from.
      colors: {
        bg: '#ffffff',
        surface: '#ffffff',
        ink: '#201f1d',
        divider: 'rgba(32,31,29,0.16)',
        accent: {
          DEFAULT: '#b68235',
          100: '#fff3e4', 200: '#ffe3bf', 300: '#facb8d', 400: '#e1ad66',
          500: '#c28d41', 600: '#a06f24', 700: '#7d5411', 800: '#5a3b0a', 900: '#3a270d',
        },
        classical: {
          100: '#f8f4f4', 200: '#eae7e7', 300: '#d7d3d3', 400: '#bab6b6', 500: '#9b9797',
          600: '#7d7979', 700: '#605d5d', 800: '#444141', 900: '#2d2b2b',
        },
      },
      fontFamily: {
        classical: ['FbTubicSans-Light', 'FbTubicSans-Light-en', 'Assistant', 'system-ui', 'sans-serif'],
      },
      fontSize: {
        kicker: ['11px', {lineHeight: '1.4', letterSpacing: '0.08em'}],
        meta: ['12.5px', {lineHeight: '1.5'}],
        cbody: ['15.5px', {lineHeight: '1.55'}],
        ch5: ['16px', {lineHeight: '1.2'}],
        ch4: ['20px', {lineHeight: '1.15'}],
        ch3: ['25px', {lineHeight: '1.15'}],
        ch2: ['27px', {lineHeight: '1.15'}],
        ch1: ['34px', {lineHeight: '1.1'}],
        price: ['30px', {lineHeight: '1'}],
      },
      spacing: {1: '4.6px', 2: '9.2px', 3: '13.8px', 4: '18.4px', 6: '27.6px', 8: '36.8px'},
      boxShadow: {
        csm: '0 1px 2px rgba(45,43,43,0.14)',
        cmd: '0 3px 10px rgba(45,43,43,0.16)',
        clg: '0 12px 32px rgba(45,43,43,0.22)',
      },
      maxWidth: {phone: '430px'},
    },
  },
  plugins: [],
  // Material Tailwind's Input/Select/Textarea floating-label positioning
  // classes (e.g. `-top-1.5`, `text-[11px]`) live inside minified objects in
  // its theme/components/*.js source. Some of them aren't picked up by
  // Tailwind's static content scan even though those files are included via
  // withMT()'s content globs — without this safelist the label never floats
  // out of the way of typed text (it just sits centered, overlapping the
  // value). Safelisting guarantees they're generated regardless of scanning.
  safelist: [
    '-top-1.5',
    '-top-2.5',
    '-bottom-0',
    '-bottom-1',
    '-bottom-1.5',
    '-bottom-2.5',
    'text-[11px]',
  ],
});
