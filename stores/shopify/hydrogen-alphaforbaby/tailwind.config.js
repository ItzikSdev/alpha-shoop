import withMT from '@material-tailwind/react/utils/withMT.js';

/** @type {import('tailwindcss').Config} */
export default withMT({
  content: ['./app/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {},
  },
  plugins: [],
});
