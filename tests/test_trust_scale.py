"""rule 14 for willow-gate's trust ladder: Exiled/Rookie/Steady/Veteran/Elder
must not compare as bare integers, even though the wire format (the HMAC
header's `trust_level` field, and `TRUST_LEVELS`'s keys) stays 0..4 ints.

Ports the pattern from terpsi-music's `records/rungs.py` — non-ordinal enum
values, ordering only through named functions that say the ladder's name at
the call site — to this repo's own ladder. Every invariant here gets a test
that attempts the forbidden comparison and asserts it is refused, per this
repo's testing convention.
"""
import hashlib
import hmac
import json
import time

import pytest

from willow_gate import GateError, WillowGate, _SIGNED_FIELDS
from willow_gate.trust_scale import Trust, at_least, from_int, outranks, to_int

ALL = (Trust.EXILED, Trust.ROOKIE, Trust.STEADY, Trust.VETERAN, Trust.ELDER)


# --- rule 14, made structural -----------------------------------------------


def test_no_two_trust_levels_compare_with_an_operator():
    """The claim this module exists for. Every ordering operator must raise
    here, on every pair — not just the one pair somebody thought to try."""
    for a in ALL:
        for b in ALL:
            for op, sym in ((lambda x, y: x < y, "<"), (lambda x, y: x > y, ">"),
                            (lambda x, y: x <= y, "<="), (lambda x, y: x >= y, ">=")):
                try:
                    op(a, b)
                except TypeError:
                    continue
                raise AssertionError(f"{a} {sym} {b} did not raise")


def test_a_trust_level_is_not_an_integer_and_will_not_arithmetic():
    for a in ALL:
        assert not isinstance(a, int), f"{a} is an int; the ladder is comparable"
        for other in (0, 2, 4):
            assert a != other
            try:
                a + other  # noqa: B018
            except TypeError:
                continue
            raise AssertionError(f"{a} + {other} produced a value")


def test_the_values_carry_no_order():
    """A value like `"3"` would re-admit ordering through the back door."""
    assert {t.value for t in ALL} == {"exiled", "rookie", "steady", "veteran", "elder"}
    for t in ALL:
        assert not t.value.isdigit()


def test_a_trust_level_prints_as_its_name_never_a_number():
    assert [str(t) for t in ALL] == ["EXILED", "ROOKIE", "STEADY", "VETERAN", "ELDER"]
    assert f"{Trust.ELDER}" == "ELDER"


# --- the only ordering that exists -------------------------------------------


def test_outranks_is_strict_and_total():
    for i, a in enumerate(ALL):
        for j, b in enumerate(ALL):
            assert outranks(a, b) is (i > j), f"outranks({a}, {b})"


def test_at_least_includes_the_floor():
    for i, a in enumerate(ALL):
        for j, b in enumerate(ALL):
            assert at_least(a, b) is (i >= j), f"at_least({a}, {b})"
    assert at_least(Trust.STEADY, Trust.STEADY) and not outranks(Trust.STEADY, Trust.STEADY)


def test_the_module_is_not_broken_shut():
    assert outranks(Trust.ELDER, Trust.EXILED)
    assert at_least(Trust.VETERAN, Trust.ROOKIE)
    assert from_int(4) is Trust.ELDER


# --- the wire crossing: the only place ints enter or leave -------------------


def test_from_int_round_trips_every_wire_value():
    for n, t in ((0, Trust.EXILED), (1, Trust.ROOKIE), (2, Trust.STEADY),
                 (3, Trust.VETERAN), (4, Trust.ELDER)):
        assert from_int(n) is t
        assert to_int(t) == n


def test_from_int_refuses_rather_than_defaulting():
    """A silent downgrade to Exiled (or clamp to Elder) is the wrong failure
    direction here, same as terpsi's `parse` refusing rather than defaulting
    to L1."""
    for bad in (-1, 5, 99, "rookie", "1", None, 1.5, True):
        try:
            got = from_int(bad)
        except (ValueError, TypeError):
            continue
        raise AssertionError(f"from_int({bad!r}) returned {got}")


def test_there_are_exactly_five_trust_levels():
    assert len(list(Trust)) == 5
    assert [t.name for t in Trust] == ["EXILED", "ROOKIE", "STEADY", "VETERAN", "ELDER"]


# --- integration: the ceiling check in _authenticate is guarded -------------

SEC = b"ceiling-secret-0123456789abcdef0"


def sign(secret, h):
    canon = json.dumps({k: h[k] for k in _SIGNED_FIELDS},
                       sort_keys=True, separators=(",", ":")).encode()
    return hmac.new(secret, canon, hashlib.sha256).hexdigest()


def hdr(secret, **over):
    h = dict(agent_id="C1", agent_name="capped", last_gate="G0", pass_count=0,
              fail_count=0, drift=50, nonce="c" * 32, trust_level=1,
              timestamp=int(time.time() * 1000), tools=["read"],
              state_hash="a" * 64, signature="0" * 64, reserved=0)
    h.update(over)
    h["signature"] = sign(secret, h)
    return h


@pytest.fixture
def gate(tmp_path):
    g = WillowGate(base_dir=tmp_path, require_pgp=False)
    g.register_agent("C1", SEC, max_trust=2)  # ceiling: Steady
    return g


def test_ceiling_check_still_refuses_a_claim_above_the_registered_max(gate):
    """The wire ints (claimed=4/Elder, ceiling=2/Steady) are unchanged; the
    comparison inside _authenticate now goes through Trust/outranks() instead
    of a bare `>`, and must still refuse exactly the cases it always refused."""
    with pytest.raises(GateError, match="exceeds registered ceiling"):
        gate.check_in(hdr(SEC, trust_level=4, nonce="d" * 32))


def test_ceiling_check_still_admits_a_claim_at_or_below_the_max(gate):
    # Steady (2) also requires min_pass_count=3 per TRUST_LEVELS — unrelated
    # to the ceiling guard under test, but needed to reach it.
    ok, _, s = gate.check_in(hdr(SEC, trust_level=2, pass_count=3, nonce="e" * 32))
    assert ok and s["trust_level"] == 2


def test_wire_field_stays_a_bare_int_on_the_way_in_and_out(gate):
    """The HMAC header and the session's trust_level are unchanged by this
    port: they are plain ints, not Trust values — only the internal
    comparison gained the guard."""
    _, _, s = gate.check_in(hdr(SEC, trust_level=1, nonce="f" * 32))
    assert isinstance(s["trust_level"], int) and s["trust_level"] == 1
