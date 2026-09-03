# Changelog

## 0.1.0 (2026-09-03)


### Added

* **#9:** stance-aware friction — the second signal, chance → 84% committed accuracy ([9a1ea20](https://github.com/willow-memory/willow-gate/commit/9a1ea20a5f4b9fdcb3826b8b0758daa02a9547d0))
* **#9:** stance-aware friction — the second signal, from chance to 84% committed accuracy ([11eb146](https://github.com/willow-memory/willow-gate/commit/11eb146ef36f80583aa7a89baceb10276398e3bf))
* **H1:** Ed25519 inter-agent message integrity for the Grove/dispatch bus ([d81cd4b](https://github.com/willow-memory/willow-gate/commit/d81cd4b7d2aab7913417506d2abcdd50ab6d8fa0))
* **H1:** Ed25519 inter-agent message integrity for the Grove/dispatch bus ([c0abbad](https://github.com/willow-memory/willow-gate/commit/c0abbad7fb59f3fdafb01612c042a94ebe0d19f2))


### Fixed

* enforce entry_allowed — Exiled is refused at check-in ([#12](https://github.com/willow-memory/willow-gate/issues/12)) ([80609e2](https://github.com/willow-memory/willow-gate/commit/80609e2ff7b83aa1c8b7f12f8ca0ec1970b6b00a))
* plaintext ledger filenames doubled the kind suffix ([6bc4b5e](https://github.com/willow-memory/willow-gate/commit/6bc4b5e84d47eab9a5a2504454d9173a95185052))
* plaintext ledger filenames doubled the kind suffix ([4e0b8fe](https://github.com/willow-memory/willow-gate/commit/4e0b8fe39cab8ee701e893afa690cb16c652ec96))


### Security

* authorize off the server-side session, not the caller's copy ([6089217](https://github.com/willow-memory/willow-gate/commit/6089217128dc2428ff882b263bba8e9c3d16dace))
* gate trust rungs on a gate-witnessed tally, not the self-signed header (B12) ([bd9ad9d](https://github.com/willow-memory/willow-gate/commit/bd9ad9dccbcfe53ea06eb7222ffe3408c7cf9aac))
* pin the canonical signing encoding + expose it for reuse (A6) ([aa20faf](https://github.com/willow-memory/willow-gate/commit/aa20faf583536f51f0463878604842a39e74b9fe))
* workflow token scoped, dependabot ([3174807](https://github.com/willow-memory/willow-gate/commit/3174807df555a8b5f76fe16f25108ba8da67dd9b))


### Build

* **deps:** Bump actions/checkout from 4 to 7 ([bf95206](https://github.com/willow-memory/willow-gate/commit/bf9520601387eee662b92c50f60d6da62c39d767))
* **deps:** Bump actions/checkout from 4 to 7 ([20ea5f1](https://github.com/willow-memory/willow-gate/commit/20ea5f193d1b9f35a9473d17fb1d8e83c4f8e4d0))
* **deps:** Bump actions/setup-python from 5 to 6 ([ff696f3](https://github.com/willow-memory/willow-gate/commit/ff696f377df2af45666137c688275f0bb73f02bb))
* **deps:** Bump actions/setup-python from 5 to 6 ([89dc8c3](https://github.com/willow-memory/willow-gate/commit/89dc8c3f79b5771c969a8781e6da0a2c5b3e8c70))
* **deps:** Bump actions/setup-python from 6 to 7 ([44e37ae](https://github.com/willow-memory/willow-gate/commit/44e37aee649df9ea76c4394cceb1e144fc99d2ae))
* **deps:** Bump actions/setup-python from 6 to 7 ([9601a1a](https://github.com/willow-memory/willow-gate/commit/9601a1a44d9345db20afbd0b0ef5af139827c28d))
* **deps:** Bump actions/setup-python from 6 to 7 ([c12c7e5](https://github.com/willow-memory/willow-gate/commit/c12c7e537783744a87d1cfbbda78d5f2318bdcb9))
* **deps:** Bump actions/setup-python from 6 to 7 ([2de5eee](https://github.com/willow-memory/willow-gate/commit/2de5eeeb03b71be8a05ce06c77eb4ab52da842e3))

## Changelog

Maintained by release-please from conventional commits; the first tagged
release will be `v0.1.0`. Entries below the first release heading are written
by the tool.

## Unreleased

- The gate as it stands: trust-tiered check-in/check-out, announce-loud-for-the-
  untrusted, PGP-encrypted ledger, hard stops; `trust_scale`, `custody`,
  `message_integrity`, `friction_floor`.
