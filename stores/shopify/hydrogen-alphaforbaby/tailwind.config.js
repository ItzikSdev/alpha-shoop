import withMT from '@material-tailwind/react/utils/withMT.js';

/** @type {import('tailwindcss').Config} */
export default withMT({
  content: ['./app/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {},
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
