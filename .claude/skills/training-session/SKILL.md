---
name: training-session
description: The landing-page structural-pattern training loop (agents-training/) — Sol practices applying design patterns from reference e-commerce sites to real Shopify catalog products, on the free local qwen3:14b model plus one bounded Claude-vision critique per session. Use when asked to run/check/debug a training session, add a reference URL, inspect agents-training/lessons learned, or extend the store_building_patterns RAG.
---

# Training session — landing-page pattern loop

Sol has no vision and a small local model for this work — this loop exists so he (and any
future agent) can query real, quality-gated design patterns instead of guessing, without ever
touching the paid Anthropic tiers except for one bounded critique call per day.

## 0. The one thing to internalize before touching this

**`agents-training/lessons.md` is dead — do not read or write it.** It's Step 1 / Step 2-v1,
superseded 2026-09-05. The real source of truth is the **`store_building_patterns` RAG corpus**
(Redis, via `src/rag/index.py` — same infra as Sol's `playbook` corpus), queried through the
`search_training_patterns` tool. Markdown session files (`sessions/YYYY-MM-DD/SESSION.md`) are
the human-readable audit trail behind each promotion, never the retrieval mechanism.

## 1. Architecture

```
agents-training/
  urls.md              5 reference Shopify store URLs (fbclid stripped automatically)
  pipeline.py           shared lib: fetch, structural skeleton, local-model calls,
                         RAG dedup/promotion, screenshots, vision critique, session I/O
  run_session.py        orchestrator + CLI (--limit N bounded test, --daily the real job)
  state.json             which reference URLs have been processed, and when
  CHANGELOG.md           append-only, one line per session date
  sessions/YYYY-MM-DD/
    SESSION.md            what was learned that day, per reference URL, + the visual critique
    output/               *.html + two screenshots (reference + generated) per URL
  lessons.md, output/    LEGACY (Step 1/2-v1) — do not touch
```

Per reference URL, one pass (`process_one_url_full` in `run_session.py`):

1. **Fetch** the reference page (`httpx`, fbclid/gclid/etc. already stripped by
   `pipeline.strip_tracking_params`).
2. **Structural skeleton** (`pipeline.build_structural_skeleton`) — a stdlib `html.parser` walk
   that records tag type, class/id keyword hints, and a regex content-type guess (price-like,
   count-like, countdown-like) for interesting elements, **in document order, with zero actual
   page text ever included**. This is what makes "never copy the reference site's copy" a
   structural guarantee, not a prompt request.
3. **Extract candidate lessons** — local qwen3:14b (`pipeline.call_local_model`, `/no_think` +
   `<think>`-block stripping) reads the skeleton and returns 2-5 categories of plain-language
   structural observations.
4. **Tier-1 automated gate** (`pipeline.passes_sanity_check` + `pipeline.is_new_lesson_via_rag`)
   — reject lessons that are too short/too long/ad-copy-flavored, and reject anything that's a
   near-duplicate (cosine similarity ≥ 0.90) of something already promoted.
5. **Build training HTML** for one REAL, currently-active product from the live Shopify catalog
   (title/price/images/description via `_shopify_gql` — never invented), applying prior-promoted
   RAG lessons + this session's surviving candidates as layout guidance (still local qwen3).
6. **Screenshot both** the reference page and the generated HTML (Playwright, headless Chromium,
   1280×900 viewport, `full_page=False`).
7. **Visual critique** — the ONE Claude-vision call (`get_llm("executive")`, i.e. Sonnet) per
   URL processed. qwen3 has no vision capability at all; this is a deliberate, scoped, budget-
   capped exception to "local only." Ends with a machine-parsed `VERDICT: CLEAN` or
   `VERDICT: NEEDS REVIEW` line.
8. **Tier-2 gate**: lessons only promote into the real RAG (`pipeline.promote_lesson`) if the
   critique came back CLEAN. A NEEDS REVIEW verdict holds all of that URL's candidate lessons —
   they stay written in `SESSION.md` but never reach `search_training_patterns`.
9. **Write `SESSION.md`** for the day (all URLs processed that day, one file) and append one
   `CHANGELOG.md` line.

## 2. Running it

**Manual bounded test** (from repo root, needs `.venv`):
```bash
.venv/bin/python3 agents-training/run_session.py --limit 1
```
Processes the next N not-yet-processed reference URLs (per `state.json`) and stops. This is how
Step 1 and Step 4 were validated — always do this after touching `pipeline.py`/`run_session.py`
before trusting the daily job with it.

**The daily job** (Step 2, `--daily`): a heartbeat tick, `_training_tick` in
`src/org/heartbeat.py`, fires once per 24h on its own from `agent_heartbeat()`. It launches
`run_session.py --daily --max-minutes 240` as a **background OS subprocess**
(`asyncio.create_subprocess_exec`), not an awaited call — a 4-hour blocking call inside a tick
that runs every 60s would freeze sourcing, tickets, stock watch, and every other agent's turn for
the whole session (same failure class as the 2026-08-09 org-freeze incident). The subprocess is
independently capped at 4h15m and killed if it overruns. Time is re-checked before every single
URL inside `run_daily_session`, not pre-planned, so a slow real run stops exactly at the cap.

Flow once first-pass (never-seen) URLs are exhausted: up to 2 bounded "deeper" passes over all 5
URLs looking for genuinely new patterns (extraction prompt is told which categories are already
promoted for that domain and asked to find something different). The moment a full deeper pass
finds nothing new, the session stops early — **it never fabricates a lesson to fill the time
budget.** With only 5 reference URLs, expect most days to finish in well under an hour; if you
want deeper coverage, add more URLs to `urls.md`.

**Result**: one `📚 Daily training session` message in **Sol's own Telegram topic** (never the
main channel — this is routine work, not an escalation). A clean day just states the numbers. A
day where the critique flagged something adds one line naming how many lessons are held pending
review and where to look (`SESSION.md`), in the SAME message — no separate ping.

## 3. Querying the patterns (for any agent, not just Sol)

```python
from src.rag.index import search
hits = await search("store_building_patterns", "where should the CTA go", top_k=5)
```
Or as a bound tool: `search_training_patterns(query, count=5)` — in Sol's `_TOOLS`
(`src/org/agent_loop.py`). Each hit is `{id, text, score, session_date, category,
source_domain, session_path}` — `session_path` links back to the human-readable reasoning
behind that lesson if you want more context than the one-line pattern.

## 4. The quality gate, precisely

| Check | What it catches | Where |
|---|---|---|
| Sanity | Empty/too-short, >45 words (prose smell), ad-copy punctuation | `pipeline.passes_sanity_check` |
| RAG dedup | Semantic near-duplicate (≥0.90 cosine) of an already-promoted lesson | `pipeline.is_new_lesson_via_rag` |
| Visual critique | The generated page doesn't actually reflect the patterns, or is structurally broken (this is the one that matters most — verified 2026-09-05 to catch a real bug: a hero `<img>` with `max-width` but no `max-height` let the raw photo's real pixel size dominate the entire above-the-fold viewport, hiding price/CTA/trust entirely) | `pipeline.vision_critique` |

A lesson is only "in the system" (promotable, retrievable) after ALL THREE pass. Held lessons
are not lost — they're in that day's `SESSION.md` — but the next session's `is_new_lesson_via_rag`
check won't see them (they're not in the RAG), so a held lesson may get re-extracted and
re-attempted on a future run of the same URL. This is intentional, not a bug: a held lesson gets
another real chance rather than being permanently blocked by one bad day's critique.

## 5. Debugging

- **qwen3 returns an empty string**: it burned its entire token budget inside a `<think>` block
  before answering — same documented failure mode as `heartbeat.py`/`conversation.py`. Fix is
  budget, not prompt: extraction needs ≥3800 tokens, HTML-build needs ≥6000, even though the
  visible answer is far shorter. `pipeline.call_local_model` already appends `/no_think` and
  strips `<think>` blocks defensively, but insufficient `max_tokens` defeats that regardless.
- **Playwright errors**: `playwright install chromium` may need re-running after a Python/venv
  rebuild — the browser binary isn't reinstalled by `pip install` alone.
- **`search_training_patterns` returns nothing**: check the RAG actually has entries —
  `await list_all("store_building_patterns")` (returns metadata only, never vector bytes). An
  empty result after several sessions likely means every candidate has been held (check recent
  `SESSION.md` verdicts) rather than a wiring bug.
- **A session ran but nothing changed**: check `CHANGELOG.md`'s last line — "0 lesson(s)
  promoted, N held" means the critique flagged that session; the HTML and reasoning are still in
  that day's `sessions/YYYY-MM-DD/` for you to look at.

## 6. Extending

- **Add a reference site**: append the URL to `urls.md` (fbclid stripped automatically on load —
  no need to clean it yourself). It'll be picked up as a "pending" URL on the next run/tick.
- **New corpus fields**: edit `_CORPUS_SCHEMAS["store_building_patterns"]` in `src/rag/index.py`
  — `upsert`/`search`/`get`/`list_all`/`delete` are all corpus-agnostic, so a new metadata field
  just needs adding to that one dict entry plus wiring it into `pipeline.promote_lesson`'s
  metadata dict.
- **Loosen/tighten the quality gate**: `_RAG_DEDUP_THRESHOLD` (cosine similarity) and the bounds
  in `passes_sanity_check` are both in `pipeline.py`, both simple constants.
