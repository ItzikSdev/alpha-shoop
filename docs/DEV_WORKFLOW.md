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

## 2. Production branches — one per store

Each store that's been migrated gets its own dedicated production
branch, `<store-slug>/production` (e.g. `alphaforbaby/production`),
and that store's Oxygen "Production" environment is bound to it in
Shopify Admin (the Hydrogen storefront → Settings → Environments) —
**not** to `main`. Feature branches for that store PR into
`<store-slug>/production`, not `main`.

**Why**: this repo hosts multiple Shopify/Hydrogen storefronts. Each
store's Oxygen deploy is independently directory-scoped already (a
push touching only `stores/shopify/hydrogen-alphaforbaby/**` only
triggers alphaforbaby's own deploy check, confirmed empirically), so
two stores sharing `main` don't actually collide on *triggering* a
deploy. The real reason for a dedicated branch is **rollback
isolation** — with everything on one shared `main`, moving that single
branch pointer back to undo one store's bad deploy also reverts every
other store's unrelated commits sitting on the same branch between
those two points. A dedicated production branch per store means
rolling back store A never touches store B.

**Migration status**: `alphaforbaby` was the first store migrated to
this convention, 2026-08-30 (see `docs/DECISIONS_LOG.md` for the full
sequence and verification). A store not yet migrated keeps deploying
from `main` until it is — this isn't an all-or-nothing repo-wide
switch, it's done store by store.

**`main`'s role after migration**: stays the default branch and the
target for anything not store-specific (org backend under `src/`,
docs, cross-store infra like the PR-merge-notify pipeline) — exactly
what "non-store work" above already targets. It does not itself
trigger any store's production deploy once that store has its own
`<store-slug>/production` branch.

**Migrating a store — safe order** (verified working for alphaforbaby,
2026-08-30):
1. Create `<store-slug>/production` from the store's current
   production tip (identical content — zero-risk, just a new ref).
   Note: saving the new branch name in Shopify Admin may auto-create
   the branch on GitHub if it doesn't already exist — check before
   assuming you need to create it yourself.
2. In Shopify Admin, rebind that store's Production environment to the
   new branch. Since the branch is byte-identical to the old target at
   that moment, this causes no redeploy and no live-site change — only
   future deploy targeting changes.
3. **Verify the binding actually took effect** — don't assume a saved
   Admin setting is live. `npx shopify hydrogen env list` from the
   store's directory shows the real bound branch and confirms the
   custom domain still maps to Production:
   ```
   Production (handle: production, branch: <store-slug>/production)
       https://<custom-domain>
   ```
4. Retarget any PRs open against the old branch (`gh pr edit <n> --base
   <store-slug>/production`) — do this only after step 3 confirms,
   and do it before anything else lands on either branch, so the diff
   stays clean.
5. Don't merge anything during the migration window between steps 1
   and 3 — the old branch is still the live trigger until the Admin
   rebind is confirmed.

## 3. No production without explicit human review

Never merge to `main` or trigger a production deploy without Itzik's
explicit go-ahead — no exceptions, regardless of urgency, and
regardless of how confident the change looks. "Urgent" is a reason to
move fast on the branch and get a preview in front of him quickly, not
a reason to skip the review step itself.

## 4. Always produce a preview before requesting review

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

## 5. Commit discipline

One commit per meaningful change. Message explains what changed and
**why**, not just what — the reviewer should be able to read `git log
--oneline` and understand the shape of the work without opening every
diff.

## 6. Log as you go, not retroactively

Every real change or decision gets a note in `docs/DECISIONS_LOG.md`
at the time it happens — new entry at the top, dated, specific enough
that a future session can trust it without re-deriving the same
findings. A summary written after the fact tends to smooth over the
blockers and dead ends that are exactly what the next session needs to
know about.

## 7. Status honesty — hard rule

Never mark a ticket `done` without a checkable artifact attached as
proof: a commit SHA, a PR URL, a live preview link, a query result —
something a different session could independently verify, not just
the claim itself. This is a hard rule, not a guideline, following the
2026-08-29 incident where a ticket was marked `done` with zero real
work behind it (no git tooling existed to have done the work at all —
see `docs/DECISIONS_LOG.md`, "Sol false-completion on TKT-68b77b1e").
If the real state is "code exists on a branch, preview pending
review," the status should say that (e.g. `doing`), not `done`.
