"""The Exiled-Rookie-Steady-Veteran-Elder ladder as a type that cannot be
compared as an integer.

`TRUST_LEVELS` in `__init__.py` is canonical for what each level *grants*
(read/write/export, tool sets, drift budgets — and it stays keyed on the bare
ints 0..4, because that shape is pinned across repos by
`tests/test_trust_ladder_canonical.py`/willow-mcp's twin, and 0..4 is also the
`trust_level` field's wire representation in the signed HMAC header). This
module is canonical for nothing except how the level is compared once it is
off the wire — port of terpsi-music's `records/rungs.py` (rule 14: *"scales
never compare as bare integers"*).

The wire int stays an int — the HMAC header, the registry ceiling, and
`TRUST_LEVELS`'s keys are untouched. But the box has more than one thing
called a "rung" (this ladder runs 0-4, low->high privilege; a planned vault
feature's sensitivity ladder runs 1-5, high->low exposure, and does not even
share a range with this one). Comparing two "trust levels" with a bare `>` is
exactly how the wrong scale gets compared against this one by accident, or how
`claimed_level > ceiling` silently keeps working after a call site starts
passing something that only looks like a trust level. `Trust` values are
non-ordinal, so `Trust.STEADY < Trust.ELDER` raises `TypeError`. Ordering
exists only through :func:`outranks` and :func:`at_least`, which say the
ladder's name at the call site.

Stdlib only.
"""

from __future__ import annotations

from enum import Enum


class Trust(Enum):
    """A trust level. Values are names, deliberately not the wire ints."""

    EXILED = "exiled"
    ROOKIE = "rookie"
    STEADY = "steady"
    VETERAN = "veteran"
    ELDER = "elder"

    def __str__(self) -> str:  # "Trust.ELDER", never "4"
        return self.name


#: Ascending privilege. The only place this ladder's order is written down.
_ASCENDING = (Trust.EXILED, Trust.ROOKIE, Trust.STEADY, Trust.VETERAN, Trust.ELDER)

#: The wire encoding: `trust_level` is an int 0..4 in the signed HMAC header
#: and in TRUST_LEVELS's keys. This table is the ONLY place that mapping is
#: written down; `from_int`/`to_int` are the only crossing.
_BY_INT = {0: Trust.EXILED, 1: Trust.ROOKIE, 2: Trust.STEADY, 3: Trust.VETERAN, 4: Trust.ELDER}
_TO_INT = {v: k for k, v in _BY_INT.items()}


def outranks(a: Trust, b: Trust) -> bool:
    """True when `a` is strictly more privileged than `b`."""
    return _ASCENDING.index(a) > _ASCENDING.index(b)


def at_least(a: Trust, floor: Trust) -> bool:
    """True when `a` is `floor` or more privileged."""
    return _ASCENDING.index(a) >= _ASCENDING.index(floor)


def from_int(value: int) -> Trust:
    """Coerce a wire-format int (header `trust_level`, registry `max_trust`)
    to a `Trust`, refusing anything outside 0..4 — and refusing anything that
    is not already a plain int, so a string or a float is not silently
    coerced (a fractional trust level truncating quietly is the same wrong
    failure direction as `records.rungs.parse` defaulting to L1)."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"not a trust level: {value!r}")
    try:
        return _BY_INT[value]
    except KeyError:
        raise ValueError(f"not a trust level: {value!r}") from None


def to_int(level: Trust) -> int:
    """The wire-format int for a `Trust` — the inverse of `from_int`, used
    only at the boundary (writing a header field, indexing TRUST_LEVELS)."""
    return _TO_INT[level]
