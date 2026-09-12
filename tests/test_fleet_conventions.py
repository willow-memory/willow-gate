"""G2-conventions-willow-gate — this tree, held to the fleet's published
conventions.

Fleet plan decision 4: every repo carries a `tests/test_fleet_conventions.py`
whose rules are READ from the fleet's published document, never restated. The
document has one home — willow-reconciler's `reconciler.conventions`,
rendered by `reconciler conventions --json` — and a rule that lived in each
repo's own test file would drift one repo at a time, which is exactly how the
incidents its `sources` name happened.

The document is vendored as `tests/fleet_conventions.json` so this suite
stays free of a reconciler dependency (the package's dev extra is pytest
alone, and CI installs nothing else). Vendoring is a copy, and a copy can
drift, so it is pinned two ways: by the SHA-256 of the bytes the reconciler
actually rendered (`DOCUMENT_SHA256`, willow-reconciler 0.6.0), and — when
`reconciler` happens to be importable — by equality with the live
`conventions()`. Re-sync from `reconciler conventions --json`
(willow-reconciler >=0.6.0) when the fleet moves, or record the decision not
to.

What each published rule means here, on this tree:

* `required_when_release_please_arms_automerge` — release-please.yml arms
  auto-merge, so `.github/workflows/pr-title.yml` is required and present
  (Bite 1 of this wave).
* `hidden_types` / `required_config_comments` — release-please-config.json
  hides exactly the published set and carries both reasoning comments. This
  repo keeps its `$comment-*` blocks at the top level of the config, beside
  `$comment-versioning`, rather than inside `packages["."]`; the rule is
  about the document, so the check reads both places.
* `contributing_must_name_test_command` — CONTRIBUTING.md names
  `TEST_COMMAND`, the command CI runs under coverage.
* `required_when_pile_exists` — this repo keeps its numbered idea pile at
  `docs/ideas.md` (Wave 3, E3-piles), so `.github/workflows/trailers.yml`
  is required and present. Wave 2 declared this rule vacuous here because
  there was no pile; the same test now bites, and the plant still proves the
  helper fires on a tree with a pile and no gate.
* `idea_id_trailer` — the join key the pile rule exists to verify. CONTRIBUTING
  names it, and the trailers workflow runs `reconciler verify` on it.

Every helper that reads the tree is shown to fire on a planted violation in
this same file — `tests/test_scans_fire.py`'s house rule.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCUMENT = Path(__file__).resolve().parent / "fleet_conventions.json"

#: Where the vendored bytes came from, and their digest as saved. The
#: reconciler renders `json.dumps(conventions(), indent=2)` plus a newline;
#: the digest covers the file exactly as `reconciler conventions --json`
#: wrote it.
DOCUMENT_SOURCE = "willow-reconciler 0.6.0, `reconciler conventions --json`"
DOCUMENT_SHA256 = "8c2ba122a7100141200d8c76ad086339f984446ab7e90dd9c27a092dbf7f5335"
SCHEMA = "willow-fleet-conventions/1"

RULES = json.loads(DOCUMENT.read_text(encoding="utf-8"))

RELEASE_PLEASE = ".github/workflows/release-please.yml"
RELEASE_CONFIG = "release-please-config.json"
CONTRIBUTING = "CONTRIBUTING.md"

#: Where this repo keeps its numbered idea pile (Wave 3, E3-piles), and the
#: other spelling the fleet uses, so a pile under either name is a pile.
PILE = "docs/ideas.md"
PILE_CANDIDATES = (PILE, "IDEAS.md")
TRAILERS = ".github/workflows/trailers.yml"

ARMS_AUTOMERGE = "gh pr merge --auto"

#: The command CONTRIBUTING.md names — the one CI runs under coverage.
TEST_COMMAND = "python -m pytest tests/ -q"


# ── the document ─────────────────────────────────────────────────────────────


def _document_digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def test_the_vendored_document_is_the_one_the_reconciler_published():
    """The pin. A hand edit to the vendored copy — even a one-byte one — is a
    fork of the fleet's rule set, and the whole point of decision 4 is that
    there is no fork."""
    assert _document_digest(DOCUMENT.read_bytes()) == DOCUMENT_SHA256, (
        f"tests/fleet_conventions.json is not the document {DOCUMENT_SOURCE} rendered: "
        "re-sync from `reconciler conventions --json` (willow-reconciler >=0.6.0), "
        "or record the decision"
    )
    assert RULES["schema"] == SCHEMA


def test_the_pin_catches_a_planted_one_byte_change():
    """Planted: the same bytes with one flipped. The digest must move."""
    raw = DOCUMENT.read_bytes()
    flipped = raw[:-2] + bytes([raw[-2] ^ 0x01]) + raw[-1:]
    assert len(flipped) == len(raw)
    assert _document_digest(raw) == DOCUMENT_SHA256
    assert _document_digest(flipped) != DOCUMENT_SHA256


def test_the_vendored_document_equals_the_live_one_when_the_reconciler_is_importable():
    """Optional, live: if willow-reconciler is installed beside this suite,
    the vendored copy must equal what it publishes today. Skipped when it is
    not — CI installs only the dev extra — so the hash pin above is the one
    that always runs."""
    conventions = pytest.importorskip("reconciler.conventions")
    assert conventions.conventions() == RULES
    assert conventions.SCHEMA == RULES["schema"]


# ── reading the tree ─────────────────────────────────────────────────────────


def _arms_automerge(root: Path) -> bool:
    workflow = root / RELEASE_PLEASE
    return workflow.exists() and ARMS_AUTOMERGE in workflow.read_text(encoding="utf-8")


def _missing_when_armed(root: Path, required: list[str]) -> list[str]:
    if not _arms_automerge(root):
        return []
    return [f for f in required if not (root / f).exists()]


def _config_hidden_types(config_text: str) -> set[str]:
    sections = json.loads(config_text)["packages"]["."]["changelog-sections"]
    return {s["type"] for s in sections if s.get("hidden")}


def _config_missing_comments(config_text: str, required: list[str]) -> list[str]:
    """The required reasoning comments absent from the config — read at the
    document's top level and inside `packages["."]`, since the rule is that
    the reasoning lives in the config file, and the fleet's configs keep it
    in either place."""
    document = json.loads(config_text)
    package = document["packages"]["."]
    return [c for c in required if c not in document and c not in package]


def _pile(root: Path) -> Path | None:
    for candidate in PILE_CANDIDATES:
        if (root / candidate).exists():
            return root / candidate
    return None


def _missing_when_pile_exists(root: Path, required: list[str]) -> list[str]:
    if _pile(root) is None:
        return []
    return [f for f in required if not (root / f).exists()]


def _names_test_command(contributing_text: str) -> bool:
    return TEST_COMMAND in contributing_text


def _names_trailer(contributing_text: str, trailer: str) -> bool:
    """True if CONTRIBUTING spells the trailer as a git trailer key
    (`Idea-Id:`), not merely mentions the word."""
    return f"`{trailer}:" in contributing_text


def _runs_verify_on(workflow_text: str, pile: str) -> bool:
    """True if the trailers workflow actually runs `reconciler verify` against
    `pile` with a path the reconciler can resolve."""
    return f"reconciler verify --repo ./ --doc {pile}" in workflow_text


# ── the real tree ────────────────────────────────────────────────────────────


def test_pr_title_guard_is_present_wherever_automerge_is_armed():
    assert _arms_automerge(REPO_ROOT), f"{RELEASE_PLEASE} no longer arms auto-merge; re-read this file's docstring"
    assert _missing_when_armed(REPO_ROOT, RULES["required_when_release_please_arms_automerge"]) == []


def test_the_configs_hidden_set_equals_the_published_set():
    text = (REPO_ROOT / RELEASE_CONFIG).read_text(encoding="utf-8")
    assert _config_hidden_types(text) == set(RULES["hidden_types"])


def test_the_configs_visible_set_is_within_the_published_release_cutting_set():
    """The two published tuples partition the types a config may list. A
    type this config lists un-hidden that the fleet does not name as
    release-cutting would be a release nobody in the fleet expects."""
    sections = json.loads((REPO_ROOT / RELEASE_CONFIG).read_text(encoding="utf-8"))["packages"]["."]
    visible = {s["type"] for s in sections["changelog-sections"] if not s.get("hidden")}
    assert visible <= set(RULES["release_cutting_types"]), visible - set(RULES["release_cutting_types"])
    assert not (visible & set(RULES["hidden_types"]))


def test_the_config_carries_every_required_reasoning_comment():
    text = (REPO_ROOT / RELEASE_CONFIG).read_text(encoding="utf-8")
    assert _config_missing_comments(text, RULES["required_config_comments"]) == []


def test_contributing_names_the_test_command():
    assert RULES["contributing_must_name_test_command"] is True
    assert _names_test_command((REPO_ROOT / CONTRIBUTING).read_text(encoding="utf-8"))


def test_trailers_workflow_is_present_because_a_pile_exists():
    """Wave 2 asserted the pile was absent and this rule vacuous. Wave 3
    cut the pile, so the rule bites: `docs/ideas.md` exists, therefore
    `trailers.yml` must, and the published rule set names exactly which
    workflow that is."""
    assert _pile(REPO_ROOT) == REPO_ROOT / PILE, "this repo keeps its pile at docs/ideas.md"
    assert TRAILERS in RULES["required_when_pile_exists"]
    assert _missing_when_pile_exists(REPO_ROOT, RULES["required_when_pile_exists"]) == []


def test_the_trailer_convention_is_named_where_a_contributor_reads():
    """The join key the pile rule exists to verify is `Idea-Id`. CONTRIBUTING
    must name it (a trailer nobody knows to write is the 0.0 recovery the
    convention started from), and the trailers workflow must run `verify`
    on the pile, not merely exist."""
    trailer = RULES["idea_id_trailer"]
    assert trailer == "Idea-Id"
    assert _names_trailer((REPO_ROOT / CONTRIBUTING).read_text(encoding="utf-8"), trailer)
    assert _runs_verify_on((REPO_ROOT / TRAILERS).read_text(encoding="utf-8"), PILE)


# ── the tree readers, planted ────────────────────────────────────────────────


def _tree(tmp_path: Path, label: str, *, arms: bool, files: tuple[str, ...] = ()) -> Path:
    root = tmp_path / label
    (root / ".github" / "workflows").mkdir(parents=True)
    body = "jobs:\n  release-please:\n    steps:\n      - run: |\n"
    body += f'          {ARMS_AUTOMERGE} --merge "$pr"\n' if arms else "          gh pr list\n"
    (root / RELEASE_PLEASE).write_text(body, encoding="utf-8")
    for f in files:
        (root / f).parent.mkdir(parents=True, exist_ok=True)
        (root / f).write_text("# planted\n", encoding="utf-8")
    return root


def test_the_armed_tree_check_fires_on_a_planted_tree_missing_the_guard(tmp_path):
    required = RULES["required_when_release_please_arms_automerge"]
    assert _missing_when_armed(_tree(tmp_path, "bare", arms=True), required) == required
    assert _missing_when_armed(_tree(tmp_path, "guarded", arms=True, files=tuple(required)), required) == []
    assert _missing_when_armed(_tree(tmp_path, "manual", arms=False), required) == []


def test_the_hidden_set_check_catches_a_planted_config_that_unhides_ci():
    """Planted: `ci` listed without `hidden`, and only one reasoning comment
    — kept inside `packages["."]`, the other place the fleet's configs put
    it — so the missing one is reported wherever the present one lives."""
    planted = json.dumps(
        {
            "packages": {
                ".": {
                    "changelog-sections": [
                        {"type": "feat", "section": "Added"},
                        {"type": "docs", "section": "Docs", "hidden": True},
                        {"type": "test", "section": "Tests", "hidden": True},
                        {"type": "ci", "section": "CI"},
                        {"type": "chore", "section": "Chores", "hidden": True},
                    ],
                    "$comment-what-cuts-a-release": "kept",
                }
            }
        }
    )
    assert _config_hidden_types(planted) == {"chore", "docs", "test"}
    assert _config_hidden_types(planted) != set(RULES["hidden_types"])
    assert _config_missing_comments(planted, RULES["required_config_comments"]) == ["$comment-hidden-rule"]

    top_level = json.dumps({"packages": {".": {"changelog-sections": []}}, "$comment-hidden-rule": "kept"})
    assert _config_missing_comments(top_level, RULES["required_config_comments"]) == ["$comment-what-cuts-a-release"]


def test_the_pile_check_fires_on_a_planted_tree_with_a_pile_and_no_verify_gate(tmp_path):
    required = RULES["required_when_pile_exists"]
    for candidate in PILE_CANDIDATES:
        with_pile = _tree(tmp_path, f"pile-{candidate.replace('/', '-')}", arms=False, files=(candidate,))
        assert _pile(with_pile) == with_pile / candidate
        assert _missing_when_pile_exists(with_pile, required) == required
    gated = _tree(tmp_path, "gated", arms=False, files=(PILE_CANDIDATES[0], *required))
    assert _missing_when_pile_exists(gated, required) == []
    assert _pile(_tree(tmp_path, "pileless", arms=False)) is None


def test_the_trailer_checks_catch_a_planted_contributing_and_workflow_that_only_mention_it():
    """Planted: a CONTRIBUTING that says the word Idea-Id in prose without
    spelling the trailer, and a workflow that installs the reconciler but
    never runs verify, or runs it with a `--repo .` the reconciler cannot
    resolve."""
    assert not _names_trailer("We like the Idea-Id convention.\n", "Idea-Id")
    assert _names_trailer("carries an `Idea-Id: willow-ideas-<num>` trailer\n", "Idea-Id")
    assert not _runs_verify_on("run: pip install willow-reconciler\n", PILE)
    assert not _runs_verify_on("run: reconciler verify --repo . --doc docs/ideas.md\n", PILE)
    assert _runs_verify_on("run: reconciler verify --repo ./ --doc docs/ideas.md\n", PILE)


def test_the_contributing_check_catches_a_planted_contributing_without_the_command():
    assert not _names_test_command("# Contributing\n\nRun the tests before pushing.\n")
    assert not _names_test_command("```sh\npytest\n```\n"), "a bare `pytest` is not the command CI runs"
    assert _names_test_command(f"```sh\n{TEST_COMMAND}\n```\n")
