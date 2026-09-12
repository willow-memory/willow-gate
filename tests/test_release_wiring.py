"""G2-pr-title-willow-gate — the release wiring, held to what it claims.

`release-please.yml` arms auto-merge on the release PR (`gh pr merge --auto`),
so from the moment a PR merges nothing human stands between its commit types
and PyPI. Two things then have to be true, and both are checked here rather
than trusted:

1. `.github/workflows/pr-title.yml` exists. This repo merges with merge
   commits, GitHub writes the PR *title* into the merge commit body, and
   release-please parses that body alongside the commits — so a `fix:` title
   over `ci:` commits cuts a release on its own (willow-mcp v2.1.1). The guard
   is the fleet's, verbatim but for one constant; it fails the PR check when a
   title would release what its commits do not, and when a commit claims a
   release for a change nothing installs.

2. The one per-repo constant in that guard, `PACKAGED`, agrees with
   `pyproject.toml`'s wheel packages. The guard's second half asks "does this
   PR touch anything `pip install willow-gate` delivers?" and answers it by
   prefix; a constant copied from another repo (`src/kartikeya/`) would make
   every real release here look installable-free and fail the check, or —
   worse, the other way round — clear a CI-only change as a release.

The guard's embedded script is run for real, not re-derived: it is lifted out
of the workflow's heredoc and executed against a stub `gh` that answers with
whatever commits and files the test plants. Every helper below that reads the
tree is shown to fire on a planted violation in this same file, which is the
house rule `tests/test_scans_fire.py` enforces.
"""

from __future__ import annotations

import ast
import json
import os
import re
import stat
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
RELEASE_PLEASE = ".github/workflows/release-please.yml"
PR_TITLE = ".github/workflows/pr-title.yml"
RELEASE_CONFIG = "release-please-config.json"
PYPROJECT = "pyproject.toml"
PILE = "docs/ideas.md"
TRAILERS = ".github/workflows/trailers.yml"

#: The line that hands the merge to GitHub. Its presence is what makes the
#: title guard mandatory rather than nice-to-have.
ARMS_AUTOMERGE = "gh pr merge --auto"

#: The fleet's hidden set: every type that changes nothing `pip install`
#: delivers. The reasoning lives beside the setting, in the config's
#: `$comment-hidden-rule`, and that comment's presence is checked too.
HIDDEN_TYPES = frozenset({"chore", "ci", "docs", "test"})
REQUIRED_COMMENTS = ("$comment-hidden-rule", "$comment-what-cuts-a-release")

_PACKAGED_LINE = re.compile(r"^\s*PACKAGED\s*=\s*(\(.*\))\s*$", re.MULTILINE)
_WHEEL_PACKAGES = re.compile(
    r"^\[tool\.hatch\.build\.targets\.wheel\]\s*\n(?:\s*#.*\n)*\s*packages\s*=\s*(\[[^\]]*\])",
    re.MULTILINE,
)
_HEREDOC = re.compile(r"python - <<'PY'\n(.*?)\n\s*PY\n", re.DOTALL)


# ── reading the tree ─────────────────────────────────────────────────────────


def _arms_automerge(root: Path) -> bool:
    """True if this tree's release-please workflow hands the release PR to
    GitHub's auto-merge — the condition under which a PR title can publish
    unattended."""
    workflow = root / RELEASE_PLEASE
    return workflow.exists() and ARMS_AUTOMERGE in workflow.read_text(encoding="utf-8")


def _missing_title_guard(root: Path) -> list[str]:
    """`[PR_TITLE]` if this tree arms auto-merge and carries no title guard;
    `[]` when the guard is there, or when nothing is armed and a title cannot
    publish anything on its own."""
    if not _arms_automerge(root):
        return []
    return [] if (root / PR_TITLE).exists() else [PR_TITLE]


def _missing_trailers_gate(root: Path) -> list[str]:
    """`[TRAILERS]` if this tree keeps a numbered idea pile and runs no
    `reconciler verify` on it; `[]` when the gate is there, or when there is
    no pile and so no join key for a dangling trailer to forge."""
    if not (root / PILE).exists():
        return []
    return [] if (root / TRAILERS).exists() else [TRAILERS]


def _verify_repo_argument(workflow_text: str) -> str | None:
    """The `--repo` argument the trailers workflow hands `reconciler verify`,
    or None when it runs no verify at all."""
    match = re.search(r"reconciler verify --repo (\S+)", workflow_text)
    return match.group(1) if match else None


def _embedded_script(workflow_text: str) -> str:
    """The Python the workflow runs, lifted out of its `python - <<'PY'`
    heredoc and dedented — the real guard, not a paraphrase of it."""
    match = _HEREDOC.search(workflow_text)
    if match is None:
        raise AssertionError("pr-title.yml no longer embeds its guard in a python heredoc")
    return textwrap.dedent(match.group(1))


def _declared_packaged(script: str) -> tuple[str, ...]:
    """The `PACKAGED = (...)` constant as the guard's script declares it."""
    match = _PACKAGED_LINE.search(script)
    if match is None:
        raise AssertionError("the guard declares no PACKAGED constant")
    return tuple(ast.literal_eval(match.group(1)))


def _wheel_packages(pyproject_text: str) -> list[str]:
    """`[tool.hatch.build.targets.wheel] packages` as pyproject spells it.

    Read with a pattern rather than `tomllib` because requires-python is
    >=3.10 and the CI floor runs there; tomllib arrived in 3.11 and the
    package declares no TOML reader as a dependency."""
    match = _WHEEL_PACKAGES.search(pyproject_text)
    if match is None:
        raise AssertionError("pyproject.toml declares no [tool.hatch.build.targets.wheel] packages")
    return list(ast.literal_eval(match.group(1)))


def _expected_packaged(pyproject_text: str) -> tuple[str, ...]:
    """What `PACKAGED` must be for this pyproject: every wheel package as a
    directory prefix, plus pyproject.toml itself (a dependency or packaging
    change alters the installed artifact — see `$comment-hidden-rule`)."""
    return tuple(f"{pkg.rstrip('/')}/" for pkg in _wheel_packages(pyproject_text)) + (PYPROJECT,)


def _hidden_types(config_text: str) -> set[str]:
    sections = json.loads(config_text)["packages"]["."]["changelog-sections"]
    return {s["type"] for s in sections if s.get("hidden")}


def _missing_comments(config_text: str) -> list[str]:
    """The reasoning blocks a release-please config must carry beside its
    hidden set, in the order the fleet names them."""
    document = json.loads(config_text)
    return [c for c in REQUIRED_COMMENTS if c not in document]


# ── running the guard ────────────────────────────────────────────────────────


_STUB_GH = """\
#!{python}
import json, os, sys
argv = sys.argv[1:]
want = argv[argv.index("--json") + 1] if "--json" in argv else ""
if want == "commits":
    print(os.environ["STUB_COMMITS"])
elif want == "files":
    print(os.environ["STUB_FILES"])
else:
    sys.exit("stub gh: unexpected call " + " ".join(argv))
"""


def _run_guard(
    script: str, cwd: Path, tmp_path: Path, *, title: str, commits: list[str], files: list[str]
) -> subprocess.CompletedProcess:
    """Execute the guard's script exactly as the workflow would — `cwd` is
    where it opens release-please-config.json — with `gh` replaced by a stub
    that answers `pr view --json commits|files` from what the test plants."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    stub = bin_dir / "gh"
    stub.write_text(_STUB_GH.format(python=sys.executable), encoding="utf-8")
    stub.chmod(stub.stat().st_mode | stat.S_IXUSR)
    env = {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
        "TITLE": title,
        "PR": "1",
        "REPO": "willow-memory/willow-gate",
        "GH_TOKEN": "stub",
        "STUB_COMMITS": json.dumps(commits),
        "STUB_FILES": json.dumps(files),
    }
    return subprocess.run(
        [sys.executable, "-"],
        input=script,
        capture_output=True,
        text=True,
        cwd=cwd,
        env=env,
        check=False,
    )


@pytest.fixture(scope="module")
def guard_script() -> str:
    return _embedded_script((REPO_ROOT / PR_TITLE).read_text(encoding="utf-8"))


# ── the real tree ────────────────────────────────────────────────────────────


def test_this_tree_arms_automerge_and_so_carries_the_title_guard():
    """The premise and the consequence, both against the real files: if the
    premise ever stops holding this test should be revisited, not deleted."""
    assert _arms_automerge(REPO_ROOT), f"{RELEASE_PLEASE} no longer arms auto-merge; re-read this file's docstring"
    assert _missing_title_guard(REPO_ROOT) == []


def test_this_tree_keeps_a_pile_and_so_carries_the_trailers_gate():
    """Wave 3 cut `docs/ideas.md`; from then on a commit trailer can name an
    item, a typo'd one asserts a false LANDED, and `reconciler verify` in CI
    is what catches it. The workflow must also hand the reconciler a path it
    can resolve: `--repo .` is read as a bare repo name (no separator) and
    errors before reading anything, which would pass nothing and fail every
    PR; `./` is a path."""
    assert (REPO_ROOT / PILE).exists(), f"{PILE} is this repo's numbered pile; re-read this file's docstring"
    assert _missing_trailers_gate(REPO_ROOT) == []
    workflow = (REPO_ROOT / TRAILERS).read_text(encoding="utf-8")
    assert 'pip install "willow-reconciler>=0.6.0"' in workflow, (
        "installed from PyPI, pinned to the conventions release"
    )
    repo_arg = _verify_repo_argument(workflow)
    assert repo_arg is not None, "trailers.yml must actually run `reconciler verify`"
    assert "/" in repo_arg, f"--repo {repo_arg!r} is a bare name to the reconciler, not a path"
    assert "fetch-depth: 0" in workflow, "a shallow clone hides every trailer but the last commit's"


def test_the_guards_packaged_constant_agrees_with_pyproject(guard_script):
    """The one per-repo constant. `("src/willow_gate/", "pyproject.toml")` is
    what this pyproject's wheel packages say it must be — a copy from another
    fleet repo would be found here."""
    expected = _expected_packaged((REPO_ROOT / PYPROJECT).read_text(encoding="utf-8"))
    assert _declared_packaged(guard_script) == expected
    assert (REPO_ROOT / "src" / "willow_gate").is_dir(), "the packaged directory must exist on disk"


def test_the_guards_error_text_names_this_package(guard_script):
    """The `pip install <name>` in the error text is the other place the
    fleet template carries a per-repo name; it must be this repo's."""
    assert "pip install willow-gate" in guard_script
    assert "pip install kartikeya" not in guard_script


def test_the_guard_reads_the_release_cutting_set_from_the_config(guard_script):
    """The set of release-cutting types is read from release-please-config.json
    rather than restated, so hiding or un-hiding a type moves the guard with
    it. A guard with its own list would drift from the config it protects."""
    assert 'json.load(open("release-please-config.json"))' in guard_script
    assert 'if not s.get("hidden")' in guard_script


def test_the_hidden_set_is_exactly_the_fleets():
    text = (REPO_ROOT / RELEASE_CONFIG).read_text(encoding="utf-8")
    assert _hidden_types(text) == HIDDEN_TYPES


def test_the_config_carries_the_reasoning_beside_the_setting():
    text = (REPO_ROOT / RELEASE_CONFIG).read_text(encoding="utf-8")
    assert _missing_comments(text) == []
    document = json.loads(text)
    assert "pip install willow-gate" in document["$comment-hidden-rule"], (
        "the hidden-rule comment names the package whose install it reasons about"
    )
    assert "jeles" in document["$comment-what-cuts-a-release"], (
        "v0.4.1 was jeles's release, not this repo's; the comment must say whose lesson it repeats"
    )


# ── the guard, run for real ──────────────────────────────────────────────────


def test_the_guard_fires_on_a_title_that_releases_what_its_commits_do_not(guard_script, tmp_path):
    """Planted: the willow-mcp v2.1.1 shape. A `fix(ci):` title over a single
    `ci:` commit must fail — GitHub would put that title in the merge commit
    and release-please would cut 0.1.1 for a workflow edit."""
    run = _run_guard(
        guard_script,
        REPO_ROOT,
        tmp_path,
        title="fix(ci): pin the release tag format",
        commits=["ci: pin the release tag format"],
        files=[".github/workflows/release.yml"],
    )
    assert run.returncode == 1, run.stdout + run.stderr
    assert "::error::PR title starts with 'fix', which cuts a release" in run.stdout


def test_the_guard_fires_on_a_release_commit_that_touches_nothing_installable(guard_script, tmp_path):
    """Planted: the willow-mcp 2.1.5 shape. Title hidden, commit `fix:`,
    files only under .github/ — the first check passes and the second must
    catch it, naming what counts as packaged."""
    run = _run_guard(
        guard_script,
        REPO_ROOT,
        tmp_path,
        title="ci: rebuild the changelog section",
        commits=["fix(ci): rebuild the changelog section"],
        files=[".github/workflows/release-please.yml", "tests/test_release_wiring.py"],
    )
    assert run.returncode == 1, run.stdout + run.stderr
    assert "::error::a commit in this PR cuts a release, but nothing installable changes." in run.stdout
    assert "src/willow_gate/, pyproject.toml" in run.stdout
    assert "pip install willow-gate" in run.stdout


def test_the_guard_passes_a_real_release_and_a_hidden_only_pr(guard_script, tmp_path):
    """The two honest shapes must clear: a `fix:` that changes shipped code,
    and a `ci:` PR whose commits are all hidden (this PR)."""
    real = _run_guard(
        guard_script,
        REPO_ROOT,
        tmp_path,
        title="fix: cap a claimed trust level at the registered ceiling",
        commits=["fix: cap a claimed trust level at the registered ceiling"],
        files=["src/willow_gate/gate.py", "tests/test_willowgate.py"],
    )
    assert real.returncode == 0, real.stdout + real.stderr
    assert "OK — title cuts a release, and so do the commits." in real.stdout

    hidden = _run_guard(
        guard_script,
        REPO_ROOT,
        tmp_path,
        title="ci: pr-title guard; the meta-scan",
        commits=["ci: pr-title guard", "test: the meta-scan", "docs: CONTRIBUTING names the test command"],
        files=[".github/workflows/pr-title.yml", "tests/test_scans_fire.py", "CONTRIBUTING.md"],
    )
    assert hidden.returncode == 0, hidden.stdout + hidden.stderr
    assert "OK — title does not cut a release on its own." in hidden.stdout


def test_a_breaking_marker_counts_as_releasing_whatever_the_type(guard_script, tmp_path):
    """Planted: `ci!:` — a hidden type carrying the breaking marker. The
    conventional-commit `!` releases (a 1.0.0, below 1.0), so a title wearing
    it over hidden commits is the same asymmetry as `fix:` over `ci:`."""
    run = _run_guard(
        guard_script,
        REPO_ROOT,
        tmp_path,
        title="ci!: drop the 3.10 leg",
        commits=["ci: drop the 3.10 leg"],
        files=[".github/workflows/tests.yml"],
    )
    assert run.returncode == 1, run.stdout + run.stderr
    assert "breaking=True -> releases=True" in run.stdout


def test_the_guard_follows_the_config_when_a_planted_config_unhides_ci(guard_script, tmp_path):
    """Planted: a config that lists `ci` without `hidden`. The same `ci:`
    title over a `ci:` commit that the real config clears must now be held
    to the packaged-files rule — proving the releasing set is read from the
    config, not baked into the guard."""
    planted_root = tmp_path / "unhidden"
    planted_root.mkdir()
    (planted_root / RELEASE_CONFIG).write_text(
        json.dumps(
            {
                "packages": {
                    ".": {
                        "changelog-sections": [
                            {"type": "feat", "section": "Added"},
                            {"type": "ci", "section": "CI"},
                            {"type": "test", "section": "Tests", "hidden": True},
                        ]
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    run = _run_guard(
        guard_script,
        planted_root,
        tmp_path,
        title="ci: touch a workflow",
        commits=["ci: touch a workflow"],
        files=[".github/workflows/tests.yml"],
    )
    assert run.returncode == 1, run.stdout + run.stderr
    assert "release-cutting types here: ['ci', 'feat']" in run.stdout
    assert "nothing installable changes" in run.stdout


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


def test_the_guard_check_fires_on_a_planted_tree_that_arms_automerge_without_it(tmp_path):
    """Planted: an armed tree with no pr-title.yml — this repo before this
    bite — must be reported; a guarded one and an unarmed one must not."""
    assert _missing_title_guard(_tree(tmp_path, "bare", arms=True)) == [PR_TITLE]
    assert _missing_title_guard(_tree(tmp_path, "guarded", arms=True, files=(PR_TITLE,))) == []
    assert _missing_title_guard(_tree(tmp_path, "manual", arms=False)) == []
    assert _missing_title_guard(tmp_path / "no-such-tree") == [], "no workflow at all arms nothing"


def test_the_trailers_check_fires_on_a_planted_tree_with_a_pile_and_no_gate(tmp_path):
    """Planted: a tree with `docs/ideas.md` and no trailers.yml — this repo
    between the pile commit and the gate commit — must be reported; a gated
    tree and a pile-less tree must not. And the `--repo` reader must tell a
    bare `.` from a path."""
    assert _missing_trailers_gate(_tree(tmp_path, "piled", arms=False, files=(PILE,))) == [TRAILERS]
    assert _missing_trailers_gate(_tree(tmp_path, "gated", arms=False, files=(PILE, TRAILERS))) == []
    assert _missing_trailers_gate(_tree(tmp_path, "pileless", arms=False)) == []
    assert _verify_repo_argument("run: reconciler verify --repo . --doc docs/ideas.md\n") == "."
    assert _verify_repo_argument("run: reconciler verify --repo ./ --doc docs/ideas.md\n") == "./"
    assert _verify_repo_argument("run: echo no verify here\n") is None


def test_the_packaged_check_catches_a_planted_constant_copied_from_another_repo():
    """Planted: the fleet template's own `src/kartikeya/` left in place, and a
    pyproject that packages `src/willow_gate`. The two must disagree, and a
    pyproject with two wheel packages must demand both prefixes."""
    copied = 'x = 1\nPACKAGED = ("src/kartikeya/", "pyproject.toml")\n'
    pyproject = '[tool.hatch.build.targets.wheel]\npackages = ["src/willow_gate"]\n'
    assert _declared_packaged(copied) == ("src/kartikeya/", "pyproject.toml")
    assert _expected_packaged(pyproject) == ("src/willow_gate/", "pyproject.toml")
    assert _declared_packaged(copied) != _expected_packaged(pyproject)

    two = '[tool.hatch.build.targets.wheel]\n# a comment between\npackages = ["src/a", "src/b/"]\n'
    assert _expected_packaged(two) == ("src/a/", "src/b/", "pyproject.toml")
    with pytest.raises(AssertionError):
        _declared_packaged("no constant here\n")
    with pytest.raises(AssertionError):
        _wheel_packages("[project]\nname = 'x'\n")


def test_the_heredoc_lift_catches_a_planted_workflow_without_one():
    """Planted: a workflow whose step is not a python heredoc, and one whose
    heredoc is indented as GitHub's `run: |` blocks are."""
    with pytest.raises(AssertionError):
        _embedded_script("run: echo hi\n")
    lifted = _embedded_script(
        "        run: |\n          python - <<'PY'\n          import sys\n          sys.exit(3)\n          PY\n"
    )
    assert lifted == "import sys\nsys.exit(3)"


def test_the_hidden_set_check_catches_a_planted_config_that_unhides_ci():
    """Planted: `ci` listed without `hidden` and one reasoning comment gone —
    the config jeles had before v0.4.1 taught it otherwise."""
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
                    ]
                }
            },
            "$comment-what-cuts-a-release": "kept",
        }
    )
    assert _hidden_types(planted) == {"chore", "docs", "test"}
    assert _hidden_types(planted) != HIDDEN_TYPES
    assert _missing_comments(planted) == ["$comment-hidden-rule"]
