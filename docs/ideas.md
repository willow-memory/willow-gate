# willow-gate — idea pile

This repo's numbered idea pile, in the shape willow-reconciler reads: top-level
`N. ` items at column 0, optional legend tags, stable numbers. It is read by

```sh
reconciler run --repo ./ --doc docs/ideas.md --validate
```

(`--repo ./`, not `.`: willow-reconciler 0.6.0 reads an argument with no path
separator as a bare repo *name* to resolve beside your checkout, and `.` has
none.)

Legend: ✅ shipped · 🟡 partial · (untagged) proposed

**Numbers are permanent join keys.** `reconciler/ids.py` derives
`willow-ideas-<num>` from the number written on the line, so a number is an
identity, not an ordinal. Never renumber; never write a markdown-auto-numbered
list (`1.` repeated) here — retire a number instead and leave the gap.

A legend tag counts only when it LEADS the item text. `hardening-plan.md` is
the reasoning behind section A (the OWASP mapping, each item's caveats, the
sequencing, the H6/H7 duality); this file is the tracked index of it, and the
status of every H-item is read from here, not from the plan's own headings.
"PR #N" appears in an item's text only where that pull request landed the
item; a bare `#N` is a reference, not evidence.

---

## A. The hardening plan (H1–H8), each with its gate

Gates are quoted from `docs/hardening-plan.md`: the observable that proves an
item done. Verify, don't assert.

1. ✅ **shipped**: H1, inter-agent message integrity (ASI07). Gate: a message with a forged sender or altered body is rejected at receive; a test forging `sender=hanuman` fails to trigger any action. Landed as Ed25519 (asymmetric, per the plan's own HMAC caveat: Grove is a shared multi-reader bus) in `src/willow_gate/message_integrity.py` with 13 tests, PR #15, 2026-07-22. Wiring the Grove send/receive edge to it is item 15.
2. H2, egress authorization is a regex (ASI05, B-37). Gate: a task requesting egress with no valid lease is denied regardless of its text; a task with a valid lease and matching identity passes; the regex alone can no longer authorize. The three-key model (capability + consent + unexpired lease) and the enforcement point live in willow-mcp's executor, where lease minting already exists; nothing in this repo yet. Dep: the willow-mcp lease path and the decommission Phase-1 cutover.
3. H3, memory/context poisoning (ASI06). Gate: an atom sourced from a non-granted path is refused at `kb_ingest`; web-fetched content cannot reach `canonical` without an explicit promote step. The mandatory provenance tags the fix needs (`session_id`, `actor`, `lineage_id` on every write) are the custody ledger's event fields, already in `src/willow_gate/custody.py` (#1), so build the ingest refusal and the `contested` quarantine tier on those rather than a second set. Dep: the Data-Vault-as-repo boundary.
4. 🟡 **partial**: H4, the friction floor as enforcement (ASI09). Gate: a session's `drift` header field is populated by measurement, not by the agent's claim; a sustained-low-friction ramp raises a persistent flag a human sees. The signal exists: `src/willow_gate/friction_floor.py` (2026-07-10) plus the stance-aware second signal (#16, from chance to 84% committed accuracy), which is the plan's "deterministic drift signals as inputs" step. Still open: wiring it into the pre-tool hook as a persistent advisory, and populating `drift` from it at check-in so the ladder is earned, not asserted. Dep: the characterization battery maturing into a scored check-in probe.
5. ✅ **shipped**: H5, check-out reconciliation, the exit half made real. Gate: an agent that check-in-declares `tools:[read]` then writes is caught at check-out with a reconciliation failure, and the mismatch lands in the ledger. Custody ledger Tier 2 (`session.checkout` reconciliation over the session's own capability events) landed in PR #1 and was hardened through six audit rounds to PR #14; the gate's own `check_out` adversarial tests landed in PR #10. `tests/test_custody.py::test_checkout_catches_declared_read_then_wrote` is the gate, verbatim. The plan said "lands in the FRANK ledger"; the spec makes the custody ledger the action ledger, so it lands there.
6. H6, intent verification (ASI01-semantic): the operator-voice injection that carries the right identity and asks for nothing to refuse. Gate as written: a shape-detector that catches it without a model judging content. Refined 2026-07-11 to *undecidable at the input layer* (operator-authentic and attacker-mimic are the same distribution by construction), so H6 dissolves into H5 plus a consequence gate (item 7); the shape signal is logged as advisory and never gates. Blocked on more injection-test runs (n>1). Do not ship a model judging content and call it done.
7. A consequence gate: a high-consequence action requires human ratification regardless of how legitimate the frame felt. H6's realistic form, since blast radius is the one thing decidable at the door; optionally coupled to H7, so a high-consequence action landing on the back of a sustained low-friction ramp requires ratification too.
8. H7, sycophantic amplification, the frictionless mirror (the safety axis: no adversary). Gate: a session that runs N turns of pure agreement while stakes rise raises a persistent, human-visible flag; the mirror signal is measured, not the agent's self-report; it never blocks; positive control: injecting specific, verifiable, *other* content measurably raises the specificity ratio and clears the flag. Signals: agreement-rate/echo ramp, specificity ratio, relationship-level check-out beside H5's tool-level one. The seed is `friction_floor.py`; the measured signals and the reply-edge hook are the work. n>1 before any threshold is trusted. Do not ship a model judging its own sincerity.
9. H8 (candidate), quis custodiet: the custody ledger's own trust root once H3/H5/H7 lean on it. Gate: the agent process cannot mint or read the checkpoint key; a burst of `capture_gap` events raises an alert rather than silently degrading reconciliation. Operator-held key (the sudo invariant), rate-limit and alert on gap bursts, append-only storage the agent process cannot rewrite. Not novel; do not skip once the ledger is load-bearing.

## B. Custody ledger open questions

From `docs/custody-ledger-spec.md`, "decide / test before building past Tier 2".

10. Checkpoint interval: per session close, every N events, or both. Cost against granularity; the spec's operational answer today is "checkpoint at every session close, keep the unsealed window small".
11. Retention. Archive-don't-delete says never prune, and a high-volume action ledger grows unbounded. Resolution proposed for ratification: checkpoint, then compress cold segments, never delete; the hash chain must survive compaction (compact the payloads, keep the hashes).
12. Sidecar authority weight: how loudly to mark sidecar-verified custody as weaker than ledger-verified, so nobody treats a signed slice as a complete history. The sidecar proves authenticity, never completeness, and its honesty label is inside the signature since Tier 4 round 2.
13. `capture_gap` policy: does an unexplained hash jump merely flag, or also dock trust. Leaning flag-only until the false-positive rate is measured (n>1).

## C. Integration follow-ups

Carried from `docs/HANDOFF.md` ("Open threads"), the plan's H1 resolution, and
the README.

14. Tier-3b integration: wire the custody ledger into the gate's pre-tool hook and the integrations egress lane so the active `session_id` is injected on every capability event. Until it exists, an untagged capability call is outside reconciliation by construction; the ledger is a library, not yet a wall or even a witness at that seam.
15. Wire the Grove send/receive edge to `sign_message` / `MessageVerifier` (H1's named follow-up). `grove_db.py` lives in safe-app-willow-grove, so the landing commit is in that repo; this item tracks the gate's side of the seam (key registry, rotation, nonce store) staying stable for it.
16. Asymmetric agent-to-gate check-in binding: "agent signs, gate verifies with only a public key" needs the 13-field header's `signature` widened beyond 64 hex (README, "Enforcement vs. audit"). Distinct from item 1, which is bus messages between agents; this is the check-in HMAC itself.

## D. Fleet conventions (the willow fleet loop plan)

17. ✅ **shipped**: keep this numbered pile at `docs/ideas.md`, in the reconciler's form, converted from `hardening-plan.md` and the docs' open items, and validated by `reconciler run --repo ./ --doc docs/ideas.md --validate` (Wave 3, E3-piles). The plan stays as the reasoning and points here.
18. Adopt `Idea-Id` commit trailers (fleet CONVENTION, decision-2026-09-11): a commit that lands an item here carries `Idea-Id: willow-ideas-<num>` in its trailer block, generated with `reconciler id --grep`, never typed; `.github/workflows/trailers.yml` runs `reconciler verify` on every PR so a dangling id (worse than none: rule 2a asserts LANDED from it) fails CI; CONTRIBUTING names the convention; `tests/test_fleet_conventions.py`'s pile rule bites (Wave 3, E3-trailers).
19. `src/willow_gate/friction_floor.py` is the declared ORIGIN of Forge's vendored copy; Forge pins its own body with a named spelling-only divergence (`re.I` vs `re.IGNORECASE`, typing spellings). Reconcile both sides in one hour (Wave 6): one body, one origin, the divergence either adopted here or dropped there.

## E. Hygiene

Recorded in #38's "seen, not touched" (Wave 2); none of them changes what
`pip install willow-gate` delivers.

20. `release-please.yml` runs `python tools/changelog_dedup.py` in two steps and this repo has no `tools/` directory. Harmless by accident: a missing script exits 2, which the step reads as "warn and carry on", so the changelog-rebuild and release-body-sync steps are dead code here. Port the tool from willow-mcp or drop the steps (`ci:`).
21. `release-please-config.json`'s `$comment-versioning` is jeles's text (`willow_institutional_search`, `jeles/_egress.py`, "99 commits and 8 tags"), and `$comment-initial-version` says "remove after v0.1.0 is cut" when v0.1.0 was cut in #36. Make the config's comments true of this repo (`chore:`).
22. `.coverage` (SQLite) is committed at the repo root and absent from `.gitignore`; it changes on every local test run. Untrack it and ignore it (`chore:`).
