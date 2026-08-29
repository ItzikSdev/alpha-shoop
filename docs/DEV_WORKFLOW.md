# Dev Workflow — standing playbook

Applies to **any** change to a store's storefront code (Hydrogen apps
under `stores/shopify/`), regardless of who's doing the work — this
session, a future Claude Code session, or an agent (Sol or otherwise)
once it has real git/PR tooling. Not a one-off process for a single
ticket; skipping a step here is a process bug, not a judgment call.

## 1. Branch naming

`<store-slug>/<feature-description>` — never work directly on `main`.

```
alphaforbaby/pdp-conversion-improvements
timeofbaby/hero-video-refresh
```

`<store-slug>` matches the store's directory name under
`stores/shopify/` (`hydrogen-alphaforbaby` → `alphaforbaby`). See
`stores/shopify/hydrogen-alphaforbaby/../CONTRIBUTING.md` for the
short version of this rule; this file is the fuller process doc it
points back to.

Non-store work (agent/pipeline code under `src/`, docs, etc.) doesn't
need the store-slug prefix — a plain descriptive branch name is fine.

## 2. No production without explicit human review

Never merge to `main` or trigger a production deploy without Itzik's
explicit go-ahead — no exceptions, regardless of urgency, and
regardless of how confident the change looks. "Urgent" is a reason to
move fast on the branch and get a preview in front of him quickly, not
a reason to skip the review step itself.

## 3. Always produce a preview before requesting review

The human should see real running changes, not a description of a
diff. Before asking for review:

- Push the branch — the store's Oxygen GitHub integration deploys
  every push to a Preview environment automatically (confirm via the
  "Deploy to Oxygen" check on the commit, not just "the push
  succeeded" — a green push doesn't mean a green deploy).
- Get the actual preview URL and share it, not just "CI passed."
  Historically the Shopify CLI only writes this URL to an ephemeral
  `h2_deploy_log.json` on the CI runner — it does **not** show up in
  the GitHub check-run output or the GitHub Deployments API. Options
  to retrieve it, in order of preference:
  1. Shopify Admin → the Hydrogen storefront → Deployments tab (no
     credentials needed beyond normal Admin access).
  2. A local `npx shopify hydrogen deploy` from the branch, using the
     deployment token in `store-profiles/<store>/store.env` — this
     prints the URL directly, but is an external/production-adjacent
     action and may require explicit human confirmation depending on
     the session's permission mode. Don't silently retry around a
     block on this — surface it and ask.
  3. A direct Admin GraphQL query for `hydrogenStorefronts` — same
     confirmation caveat as above.
- If the preview URL genuinely can't be retrieved in a given session,
  say so explicitly (with what was tried) rather than reporting the
  CI checkmark as if it were the deliverable.

## 4. Commit discipline

One commit per meaningful change. Message explains what changed and
**why**, not just what — the reviewer should be able to read `git log
--oneline` and understand the shape of the work without opening every
diff.

## 5. Log as you go, not retroactively

Every real change or decision gets a note in `docs/DECISIONS_LOG.md`
at the time it happens — new entry at the top, dated, specific enough
that a future session can trust it without re-deriving the same
findings. A summary written after the fact tends to smooth over the
blockers and dead ends that are exactly what the next session needs to
know about.

## 6. Status honesty — hard rule

Never mark a ticket `done` without a checkable artifact attached as
proof: a commit SHA, a PR URL, a live preview link, a query result —
something a different session could independently verify, not just
the claim itself. This is a hard rule, not a guideline, following the
2026-08-29 incident where a ticket was marked `done` with zero real
work behind it (no git tooling existed to have done the work at all —
see `docs/DECISIONS_LOG.md`, "Sol false-completion on TKT-68b77b1e").
If the real state is "code exists on a branch, preview pending
review," the status should say that (e.g. `doing`), not `done`.
