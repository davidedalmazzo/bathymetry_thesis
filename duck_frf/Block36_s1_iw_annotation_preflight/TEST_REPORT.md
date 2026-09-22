# Block36 test report

The focused synthetic annotation/transport suite passed before the repository
suite. The final authoritative count is the one full-suite invocation recorded
verbatim in `FULL_SUITE.json`; focused tests are not added to that count.

- Focused suite: 17 passed (diagnostic run only).
- Authoritative complete suite: **360 passed in 47.13 s**, zero failures or
  skips, using `.venv-umbra-thesis/Scripts/python.exe`.
- Frozen audit: **810 verified, zero mismatches**.

Checks cover parsing and selected-product identity, invalid sample masks,
partial bursts, a burst join, a known synthetic Jacobian and k transform,
axial direction conventions, response size/type rejection, manifest references,
credential-path restrictions, password/MFA/refresh lifecycle, bounded auth
attempts, bearer secrecy and persistent transaction/byte accounting. These are
offline code tests, not evidence that protected CDSE
SAR pixels were read. The authenticated annotation bodies were independently
parsed during the preflight; the suite also covers their timezone lexical form.

`FROZEN_AUDIT.json` verifies the Block34 baseline through the current path
resolver without rewriting historical files. `MANIFEST.json` records SHA-256
for every versionable Block36 artifact and relevant code source.
