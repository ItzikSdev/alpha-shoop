# Sol Agent Improvement Roadmap

Written after a single extended session (2026-07-07/08) covering: Hydrogen storefront
fixes, the product-upload pipeline, a local-model migration for Sol (qwen3 family via
Ollama), and several real production incidents. This is a working document for Sol's
next sessions, not a retrospective for its own sake.

## 1. Process Summary & Key Lessons

**REST vs MCP.** `src/mcp_tools/*` is REST-over-CJ's API, not true MCP — the real CJ
MCP client lives at `src/cj_mcp/`. REST (`cj_search_products`) is fine for catalog
search; MCP (`cj_product_inventory`, `cj_track_shipment`) is required for anything CJ's
REST doesn't expose — live per-country stock, shipment tracking. Conflating the two
has caused confusion in past sessions; keep the split explicit in any new tool.

**Shopify GraphQL integration.** Three non-obvious gotchas discovered this session,
all now documented in `stores/shopify/hydrogen-alphaforbaby/docs/PRODUCT_UPLOAD_PIPELINE.md`:
- Shopify's product options are a strict cartesian product — creating a Color+Size
  product auto-generates every combination, including ones the supplier doesn't
  stock. These "phantom" variants ship at $0.00 with untracked inventory (always
  orderable) unless explicitly deleted after creation.
- A newly-created product metafield is invisible to the Storefront API until a
  `MetafieldDefinition` exists for it with `access.storefront: PUBLIC_READ` — and
  even then there's a real propagation delay (~20s) before it's queryable.
- A collection's `resourcePublicationsV2` can be empty even with real products in
  it — Shopify does not auto-publish new collections to sales channels. Two
  admin-UI-created collections were found broken this way; `create_collection` now
  publishes explicitly, but pre-existing ones need a one-time manual check.

**Shipping / variant mapping.** CJ's `variantKey` format is not uniform across
listings — most are 2-dimensional ("Color-Size"), but at least one confirmed listing
was 3-dimensional ("Dark Blue-59cm-Set1"). The parser (`_split_variant_key`) assumes
2D and, on a 3D key, silently collapses height into the Color value and invents a
meaningless Size ("Set1"/"Set2") — the visible symptom was ~24 near-duplicate Color
swatches on the live PDP. CJ also mislabels units per-listing (one product's Size
values came through as "59 Yards" instead of a height in cm) even when the
product's own description states the real height/age correspondence in prose.
**Lesson: never trust CJ's per-field structure as consistent — cross-check against
the free-text description, and fail closed (reject the candidate) rather than create
a product with structurally wrong variant data.**

## 2. Human / User Weaknesses (bottlenecks in this workflow)

- **Scope arrived incrementally, not upfront.** Several tasks were specified as a
  short phrase ("add 2 more products", "fix the size table") that only revealed
  their real requirements after the first attempt was reviewed against a live
  screenshot (e.g. the Size Guide went from "a table" → a full CM/Inches chart with
  "how to measure" instructions, three iterations in). Front-loading a reference
  example (a screenshot or competitor URL) up front, before the first build attempt,
  would have saved 2-3 iteration cycles each time.
- **Edge cases surfaced reactively.** The $0 phantom variant, the 3D-variantKey
  duplicate-swatch product, and the off-niche CJ results were all found by the user
  spot-checking the live site after the fact, not specified as acceptance criteria
  beforehand ("no product should ever show $0" or "reject anything not genuinely
  baby apparel" were rules written only after each incident). This is a reasonable
  way to work, but it means every new capability ships once before its guardrails
  exist — worth explicitly asking "what should never happen" before building, not
  just "what should happen."
- **Business-logic ambiguity**: pricing markup (10-15% requested vs. the existing
  2.5-3x cost multiplier already in production) and per-product vs. universal size
  charts both required a clarifying question mid-task because the request conflicted
  with, or under-specified relative to, what already existed. Neither was wrong, but
  both cost a round trip.

## 3. Sol Agent (qwen3 / Ollama) Weaknesses

- **Generation speed is the fundamental constraint.** qwen3.6:35b and :27b both
  generated at only ~5-7 tokens/sec on this hardware (partial CPU offload even at
  27b); qwen3:14b (100% GPU) reaches ~250 tok/s on prompt *processing* but generation
  itself is still the bottleneck for any response requiring substantial "thinking."
  A single tool-call decision can take 1-3+ minutes; a full sourcing task (search →
  evaluate → create → publish) realistically takes 15-40 minutes end to end.
- **Context window truncation caused silent failures**, not errors: with `num_ctx`
  too small (4096, then a stale 16384 from a shared Ollama model slot), Sol's
  responses came back with tool_calls=[] and empty content — the loop just stopped
  with nothing done, no visible error, because the *real* prompt (system prompt +
  ~13 tool schemas + growing transcript) never fit and got silently clipped.
  **This is the single most impactful bug found this session** — it looked like
  "Sol isn't doing anything" for hours before the root cause was found.
- **Off-task drift under load.** At least once, mid-run, Sol abandoned the assigned
  keyword ("newborn girl romper") and started searching an unrelated one ("baby boy
  cotton onesie") without being asked. Tightly-scoped, single-outcome task prompts
  ("add exactly 1 X, using exactly this keyword, do not search anything else")
  measurably reduced this versus open-ended instructions.
- **Hallucinated a store-memory changelog entry.** `STORE_MEMORY.md` (Sol's own
  persistent memory file) contained fabricated entries dated a day in the future,
  claiming 10 products and 45 deleted collections that never existed — almost
  certainly written by an earlier malfunctioning run under the same context-
  truncation conditions. Sol's own memory file is not automatically trustworthy;
  it needs occasional cross-checking against real Shopify state, not blind append.
- **Guard-following is inconsistent, not absent.** Given explicit "if rejected, try
  the next candidate" instructions, Sol mostly complied — but also, on one run,
  produced a final summary declaring failure ("no valid candidate passed") when a
  bypass script run moments later, with an improved keyword, succeeded on the first
  new search. It's unclear whether Sol genuinely exhausted good options or gave up
  after the first rejection cluster.

## 4. Actionable Recommendations

**System prompt / tool schema:**
- Keep `STORE_MEMORY.md`'s injected slice small (already capped at 4500 chars) —
  don't let it grow unbounded; consider pruning old "Recent changes" entries older
  than N days rather than letting the file grow to 24KB+ with everything appended.
- Consider trimming tool docstrings for the local-model path specifically — Claude
  reads verbose docstrings fine; qwen3 pays a real prompt-eval-time and context-
  budget cost for every extra sentence across ~13 tool schemas, every single turn.

**Tool usage / error handling:**
- `cj_add_product`'s reject-and-explain pattern (return `{"error": ...}`, no
  exception) worked well for guiding retries — extend this pattern to any new guard
  rather than throwing.
- Add a lightweight sanity check Sol can call cheaply (e.g. "does this product's
  Color option contain a height-like substring") *before* a full `cj_add_product`
  call, so a bad candidate is skippable in one cheap tool call rather than a full
  slow generation cycle.
- Consider a hard per-task step budget lower than the current defaults (15-18
  worked better than 25-30 for keeping a single run's scope from drifting).

**Communication pipeline (Claude ↔ Sol):**
- For anything time-sensitive or where a wrong result is costly (payment-adjacent,
  live product data), have Claude verify Sol's output against the actual Shopify
  Admin API afterward — this session caught a $0 variant, a duplicate product, an
  off-niche product, and a structurally-broken product this way, none of which Sol
  self-reported as a problem.
- For genuinely infrastructure-shaped work (webhooks, background jobs, anything
  needing sustained testing) — do not delegate to a single autonomous Sol task run;
  that needs design + iteration from Claude directly, with Sol used afterward only
  for well-scoped, single-outcome execution steps.
- When Sol's run stalls, checking `ollama ps` / the Ollama server log (token
  progress, `n_ctx_slot` vs actual prompt size) distinguishes "genuinely slow" from
  "silently truncating" much faster than reading Slack narration alone.

## Open items for next session

- Order-fulfillment automation (Shopify order webhook → CJ order creation →
  tracking sync → customer notification) is unbuilt infrastructure, not a Sol task —
  needs a dedicated session with real budget for design and testing.
- `_split_variant_key` only handles 2D CJ variantKeys; 3D keys are currently
  rejected outright rather than parsed. Worth a proper fix if 3D-key products turn
  out to be common in the CJ catalog.
- Per-product Size Guide data (vs. today's universal static chart) has the
  plumbing already built (`custom.size_guide` metafield) but is currently unused by
  the frontend — revive only if a real per-product need shows up.
