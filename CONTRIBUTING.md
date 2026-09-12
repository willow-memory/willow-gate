# Contributing to willow-gate

## Run the gate before you push

The test command — quote it, and its last line, in the PR:

```sh
python -m pytest tests/ -q
```

CI (`.github/workflows/tests.yml`) is the fleet CI floor: a lint job, a
Linux leg for every Python minor that `pyproject.toml`'s classifiers list (the
matrix is read from them, so add a classifier to add a leg), a Windows leg on
the lowest and highest of those, and one aggregate check named `test` that
fails unless every leg succeeded. The Linux legs run the suite under
coverage; the floor is 90% of `src/willow_gate/` — a floor, not a target;
ratchet it up, never down.

```sh
pip install -e '.[dev]' coverage ruff==0.16.7 bandit
ruff check src tests
ruff format --check src tests
bandit -r src -ll -q
coverage run --include='src/willow_gate/*' -m pytest tests/ -q && coverage report --fail-under=90
```

Pin ruff to CI's version. A newer ruff finds things CI does not, and an older
one misses things CI finds; both read as "passes locally, fails on the PR".

`ruff format` is enforced too. One file is excluded from the formatter on
purpose, `src/willow_gate/friction_floor.py`, until Wave 6 reconciles it with
Forge's vendored copy; the reason sits beside the setting in `pyproject.toml`.

## Receipts, not claims

A PR says what it ran and what came back — the command above and its result
line — rather than "tests pass". A claim without a command behind it is not
evidence, and the reviewer cannot re-run a claim.

## Commit types decide releases

release-please cuts releases from conventional-commit types, and
`release-please.yml` arms auto-merge on the release PR, so nothing human
stands between a commit type and PyPI. The rule lives beside the setting, in
`release-please-config.json` (`$comment-hidden-rule`): `docs:`, `test:`,
`ci:` and `chore:` change nothing `pip install willow-gate` delivers and are
hidden; every other listed type cuts a release on its own, not just `feat`
and `fix`.

The PR *title* counts too. This repo merges with merge commits, GitHub writes
the title into the merge commit body, and release-please reads that body —
so `.github/workflows/pr-title.yml` fails a title that would cut a release
its commits would not, and a commit that claims a release for a change
nothing installs.

## Scans are planted

A test that reads the tree — a workflow carries a guard, a config hides the
right types, a constant agrees with pyproject — is only evidence once it has
been shown to fail on a tree without the property. `tests/test_scans_fire.py`
enforces that: every scan helper in `tests/` needs a test in the same file,
named with `plant`, `fires` or `catches`, that calls it.

## The Idea-Id commit-trailer convention

A commit that lands an idea recorded in `docs/ideas.md` carries an
`Idea-Id: willow-ideas-<num>` git trailer (add `Idea-Status: partial` when a
commit only partly lands it). It is the durable join key willow-reconciler
reads; a wrong id is worse than no id, so never type one by hand:

    reconciler id --repo ./ --doc docs/ideas.md --grep "words from the item"
    reconciler install-hook --repo ./          # derives it from a branch named idea-NN

`.github/workflows/trailers.yml` runs `reconciler verify` on every PR and fails
on a trailer that names an item the doc does not contain. (`--repo ./`, not
`.`: the reconciler reads an argument with no path separator as a bare repo
name, and `.` has none.)

## Fleet conventions

`tests/fleet_conventions.json` is the fleet's published rule set
(`reconciler conventions --json`, willow-reconciler 0.6.0), pinned by hash,
and `tests/test_fleet_conventions.py` holds this tree to it, the pile rule
included: this repo keeps a numbered pile at `docs/ideas.md`, so the trailer
gate above is required. Re-sync the
file from the reconciler rather than editing it by hand. A published rule
this repo cannot meet is recorded in the PR, not bent in the test.
