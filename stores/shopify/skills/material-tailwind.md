# Material Tailwind — reference for this store's product-page rebuild

Docs: https://www.material-tailwind.com/docs/react (you have no web-fetch tool —
this file is your source, kept current as of 2026-07-17; if something here seems
wrong for the installed version, check `node_modules/@material-tailwind/react`
directly with read_store_file before guessing).

## Already installed and wired on `hydrogen-alphaforbaby`
- `@material-tailwind/react`, `tailwindcss`, `postcss`, `autoprefixer` are in
  `package.json` and `node_modules`.
- `tailwind.config.js` + `postcss.config.js` exist at the app root.
- `app/styles/app.css` starts with `@tailwind base; @tailwind components;
  @tailwind utilities;`.
- `app/root.jsx` wraps the whole app in `<ThemeProvider>` from
  `@material-tailwind/react` (required for MT components to pick up theme tokens —
  don't remove it, and don't wrap a second `<ThemeProvider>` anywhere else).
- Build verified passing with all of the above in place.

## Carousel — key gotcha: NOT externally controllable
`<Carousel>` has no prop or ref to jump it to a specific slide from outside the
component. There is no `value`/`activeIndex`/`onChange` prop. The ONLY way to
read or influence the active slide from outside is the `navigation` render-prop,
which hands you `{setActiveIndex, activeIndex, length}` — you'd have to stash
`setActiveIndex` into a ref during that render callback, then call the ref from
elsewhere. If a task needs "clicking a Color swatch jumps the gallery to that
photo," this is the mechanism, not a `value` prop — don't invent one.

Relevant props: `prevArrow` (fn, receives `{loop, handlePrev, activeIndex,
firstIndex}`), `nextArrow` (fn, receives `{loop, handleNext, activeIndex,
lastIndex}`), `navigation` (fn, receives `{setActiveIndex, activeIndex, length}`),
`autoplay` (bool), `autoplayDelay` (ms, default 5000), `loop` (bool, default
false), `transition` (Framer Motion config), `className`.

## Dialog / Modal
```jsx
import {Dialog, DialogHeader, DialogBody, DialogFooter} from '@material-tailwind/react';

const [open, setOpen] = useState(false);
const handler = () => setOpen(!open);

<Dialog open={open} handler={handler}>
  <DialogHeader>Title</DialogHeader>
  <DialogBody>content</DialogBody>
  <DialogFooter>...</DialogFooter>
</Dialog>
```
`open` (bool) and `handler` (fn that toggles `open`) are both required.

## Import checklist (check this every time)
`npm run build` does NOT catch a missing import for a component you use in JSX
(e.g. using `<Dialog>` without `import {Dialog} from '@material-tailwind/react'`)
-- it's a runtime crash, not a build error, so a passing build does not mean your
change is correct. Before you consider any MT component change done: re-read the
file you just edited and confirm every MT component name that appears in the JSX
(Dialog, DialogHeader, DialogBody, DialogFooter, Carousel, Button, etc.) also
appears in an `import {...} from '@material-tailwind/react'` at the top of that
same file. This is the single most common mistake to check for.

## General rules for this rebuild
- Product page only (`app/routes/products.$handle.jsx`, `ProductGallery.jsx`,
  `ProductForm.jsx`, `ProductPrice.jsx`, `SizeGuide.jsx`, trust badges) — not the
  rest of the site.
- Keep all existing DATA/LOGIC (size-chart values, cm/inch conversion, variant
  selection, cart behavior) — only the presentation layer changes to MT
  components + Tailwind utility classes.
- Always `read_store_file` the target file before editing it — never guess its
  current content.
- `write_store_file` is a FULL FILE OVERWRITE, not a patch. Only use it when you
  intend to replace the entire file; prefer `edit_store_file` for anything else.
  Never use `write_store_file` unless you have the complete, exact new content
  ready — a partial/summarized rewrite destroys the rest of the file.
- After any change: `npm run build` must pass before you deploy. Deploy is
  ALWAYS `--preview`, never production, unless explicitly told otherwise.
- Once the product page is fully converted, update
  `app/theme.config.json` (the store-cloning template) so future stores made via
  `./scripts/new-store.sh` inherit the Material Tailwind product page by default.
