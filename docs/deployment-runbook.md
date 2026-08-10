# Deploying willow-gate — the `/willowgate` runbook

How to stand up `WillowGate.BASE_DIR` (`/willowgate`) for real use, and what has
to be true about it before the gate protects anything.

This is the missing half of the README. The README shows the API; nothing until
now documented the directory that API depends on, and **every security property
the gate claims rests on filesystem permissions the code does not set itself.**

If you only want to run the tests or exercise the logic, skip to
[Development](#development-no-willowgate-needed) — you do not need any of this.

---

## 0. The decision that governs everything

willow-gate is a **library**. There is no daemon, no socket, no service. The
gate runs inside whatever process calls it, and that process is what writes
`/willowgate`.

That makes one question load-bearing, and it is not the kind of thing you can
change later without re-registering every agent:

| Topology | How you call it | Who writes `/willowgate` | Earned-rung protection |
|---|---|---|---|
| **Supervisor** — gate in a wrapper/hook process, agent is a separate process at a different uid | `gate.authorize_tool(...)` from your pre-tool hook | the supervisor's uid | **holds** |
| **In-process** — gate embedded in the agent | `gate.bind_tools(...)` → `room.call(...)` | the agent's uid | **does not hold** |

`src/willow_gate/__init__.py` describes `base_dir` as somewhere "the agent's uid
cannot write (willow-gate#181)". That is what makes the B12 fix work: the gate
keeps its own per-agent tally in `trust_tally.json` rather than trusting the
agent's self-reported `pass_count`.

**Embed the gate in the agent's own process and that sentence stops being true.**
The agent's uid is now the writing uid, so it can rewrite `trust_tally.json` and
grant itself Elder — which is precisely the bug B12 closed. `bind_tools` is still
worth using for its real benefit (a denied tool's function never runs, and there
is no un-gated path to the callable); it just cannot also give you tamper-proof
rung accounting on a shared uid.

> **Pick supervisor topology if the agent is untrusted.** In-process is
> appropriate when the gate is preventing *mistakes* rather than defending
> against the agent itself.

The rest of this runbook assumes supervisor topology and writes `GATE_USER` for
the uid running the gate, `AGENT_USER` for the uid running the agent.

---

## 1. Provision the directory

The code does `self.ledger_dir.mkdir(parents=True, exist_ok=True)` and **no
`chmod` anywhere**. Modes come from the process umask. On a default `umask 0002`
the observed result is:

```
drwxrwxr-x  /willowgate/ledger
-rw-rw-r--  /willowgate/registry.json      <-- contains shared secrets
-rw-rw-r--  /willowgate/trust_tally.json
-rw-rw-r--  /willowgate/used_nonces
-rw-rw-r--  /willowgate/announcements.log
```

Group- and world-readable, including the secrets. Do not let the gate create the
directory on first run — create it first, with the modes you want:

```bash
GATE_USER=willow-gate          # uid that runs the gate
GATE_GROUP=willow-gate

sudo groupadd -f "$GATE_GROUP"
sudo useradd -r -g "$GATE_GROUP" -s /usr/sbin/nologin "$GATE_USER" 2>/dev/null || true

sudo install -d -o "$GATE_USER" -g "$GATE_GROUP" -m 0750 /willowgate
sudo install -d -o "$GATE_USER" -g "$GATE_GROUP" -m 0750 /willowgate/ledger
```

`0750` is the primary control. The agent's uid is not in `$GATE_GROUP`, so it
cannot traverse the directory and the mode of any individual file inside stops
mattering. Everything below is defence in depth.

**Verify the agent genuinely cannot reach it:**

```bash
sudo -u "$AGENT_USER" ls /willowgate && echo "FAIL: agent can read the gate root"
sudo -u "$AGENT_USER" touch /willowgate/probe && echo "FAIL: agent can write the gate root"
```

Both must fail with *Permission denied*. If either succeeds, the earned-rung
protection and the nonce burn are decorative.

---

## 2. What lives there, and why each file matters

| File | Holds | If the agent can **read** | If the agent can **write** |
|---|---|---|---|
| `registry.json` | agent id → **HMAC shared secret (hex)** + trust ceiling | forge any header for any registered agent | raise its own ceiling |
| `trust_tally.json` | gate-witnessed pass/fail per agent | — | self-certify Elder (defeats B12) |
| `used_nonces` | burnt nonces, persisted across restart | — | replay a previous check-in |
| `ledger/<nonce>.<kind>.gpg` | custody records, PGP-encrypted | — | rewrite history |
| `announcements.log` | append-only announcement trail | — | erase its own loud entry |

`registry.json` is the one that ends the engagement if it leaks: the identity
binding is **symmetric**, so the secret that verifies a header is the same secret
that signs one.

Tighten it once, after registering agents:

```bash
sudo chmod 0600 /willowgate/registry.json
sudo chmod 0600 /willowgate/trust_tally.json
```

This survives. `register_agent()` uses `Path.write_text()`, which truncates the
existing inode rather than recreating it, so a later registration preserves the
mode you set — verified, not assumed.

---

## 3. PGP — the ledger recipient

`_verify_pgp()` **fails closed** and will not fall back to a packaged key. It
requires all three:

1. `python-gnupg` importable *and* the `gpg` binary on PATH
2. a fingerprint, from `operator_key_fpr=` or `WILLOWGATE_KEY_FPR`
3. that fingerprint present in the gate user's keyring

Point 3 is the one that bites: the keyring belongs to **`$GATE_USER`**, not to
you. Importing the key into your own account is not enough.

```bash
# export the public key you want the ledger encrypted TO
gpg --armor --export "$FPR" | sudo -u "$GATE_USER" gpg --import

sudo -u "$GATE_USER" gpg --list-keys "$FPR"          # must list it
```

Only the **public** key is needed — the gate encrypts, it never decrypts. Keep
the private key off the gate host entirely; that is the point of encrypting the
ledger to an operator key rather than a service key.

Set the fingerprint in the gate process's environment:

```bash
WILLOWGATE_KEY_FPR=9B6F87BE...           # full fingerprint, no spaces
```

A wrong or absent fingerprint raises `GateError` at construction, before any
session exists. That is intended — a gate that cannot write an encrypted ledger
should not run.

---

## 4. Register agents

Out-of-band, from the operator side, **never from a gate tool**:

```python
from willow_gate import WillowGate

gate = WillowGate(operator_key_fpr=FPR)          # base_dir defaults to /willowgate
gate.register_agent("R1", secret=os.urandom(32), max_trust=1)
```

- `secret` must be **32+ bytes** and is the agent's half of the HMAC. Transport
  it to the agent over a channel you would send a private key over.
- `max_trust` is a **ceiling, 0..4**, not a grant. A header claiming a higher
  level is refused outright rather than silently capped:
  `trust claim 4 exceeds registered ceiling 1`.
- A newly registered agent starts at **zero earned rungs** regardless of ceiling.

Re-run `chmod 0600` on `registry.json` after the first registration creates it.

---

## 5. Earned rungs (optional, off by default)

`WILLOW_GATE_ENFORCE_EARNED_RUNGS` makes the rung gate read `trust_tally.json` —
the gate's own witnessed count — instead of the agent's self-reported header
fields. It is **off by default** so existing deployments keep header semantics
until the operator has seeded a tally.

Migrating an already-trusted agent:

```bash
sudo -u "$GATE_USER" tee /willowgate/trust_tally.json >/dev/null <<'JSON'
{"R1": {"pass": 40, "fail": 2}}
JSON
sudo chmod 0600 /willowgate/trust_tally.json
```

Then set the flag in the gate process's environment. It accepts
`1`, `true`, `yes`, or `on` (case-insensitive, whitespace-trimmed); **anything
else — including `0` and `false` — reads as off**, so a typo fails safe toward
header semantics rather than erroring:

```bash
WILLOW_GATE_ENFORCE_EARNED_RUNGS=1
```

Mind the two spellings: this one has an underscore after `WILLOW`, while the PGP
variable is `WILLOWGATE_KEY_FPR` without it. They are inconsistent in the code
itself, and a misspelled env var is silently ignored by both.

Do not enable this in in-process topology. On a shared uid the agent can edit the
file the flag tells the gate to trust, which is strictly worse than the header
semantics it replaces — it moves the trust decision to a source that *looks*
authoritative and is not.

---

## 6. Verification

Run as `$GATE_USER`, with the real environment. Each line proves a specific
property rather than just exercising the API:

```python
from willow_gate import GateError, Tool, WillowGate

gate = WillowGate()                       # no base_dir, no require_pgp override
assert gate.base_dir.as_posix() == "/willowgate"
assert gate.require_pgp                   # production default
assert gate.operator_key_fpr              # PGP recipient resolved
```

Then a round trip, which should read:

```
check_in       : True — CHECK-IN ACCEPTED — large announcement, read-only
read allowed   : 'page'
write denied   : DENIED — 'write' not in this session's grant
write_fn ran?  : False          <- prevention, not audit
trust_level=4  : refused — trust claim 4 exceeds registered ceiling 1
check_out      : True — CHECK-OUT COMPLETE
```

`write_fn ran? False` is the assertion that matters. If the function ran and was
merely *recorded*, you have a ledger, not a gate — see the README's
"Enforcement vs. audit".

Finally, confirm the ledger is actually encrypted. The extension is the tell —
`_write_ledger` writes `<nonce>.<kind>.gpg` when `require_pgp` is on and swaps
the suffix to `.json` when it is not:

```bash
sudo -u "$GATE_USER" ls /willowgate/ledger/
# want: <nonce>.entry.gpg, <nonce>.exit.gpg
# any *.json here means require_pgp=False leaked into production

sudo -u "$GATE_USER" file /willowgate/ledger/*.gpg     # "PGP ... encrypted data"
```

Note the two files are not independent: a `.gpg` that fails to encrypt raises
`GateError` rather than falling back, so a missing ledger entry means a refused
check-in, not a silent plaintext write.

---

## Development (no `/willowgate` needed)

Never run this configuration anywhere real — it writes a **plaintext ledger**:

```python
gate = WillowGate(base_dir=Path("./willowgate"), require_pgp=False)
```

`willowgate/` and `.willowgate/` are already in `.gitignore`. The test suite uses
`tmp_path` and needs no setup at all:

```bash
python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'
.venv/bin/pytest -q
```

---

## What this does not give you

Stated plainly so nobody assumes otherwise:

- **No protection from root**, or from anyone who can `sudo -u $GATE_USER`.
- **No protection in in-process topology** for anything under `/willowgate`, per
  §0. The tool-call prevention still holds; the file-backed accounting does not.
- **No network authentication.** The identity binding is HMAC over a header the
  caller hands you. It proves possession of the shared secret, nothing about
  where the call came from.
- **No revocation channel.** Removing an agent means editing `registry.json` and
  restarting the gate; live sessions are held in memory.
- **No ledger integrity check on read.** Encryption protects confidentiality;
  detecting deletion of a ledger file is the custody layer's job
  (`docs/custody-ledger-spec.md`), not this directory's.
