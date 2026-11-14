# Changelog

## Unreleased — implementation necessity before patching

- Reviewed the original 51 planned items against official fixes and the pinned source: 22 required in the published Xenial FPM scope, 23 prerequisite-dependent, 5 other OS/SAPI, and 1 exact mechanism absent.
- Corrected current catalog counts to 2 implementations / 14 mechanism-absent / 50 review-or-implementation planned; preserved the prior JPEG assessment and separate short-read follow-up.
- Added explicit prerequisite gates for conditional source work, source-bound assessment validation, reproducible bilingual tables and exact Xenial crypt-backend evidence.
- The engine patch and historical release artifacts remain unchanged. The 0.1.1 figures below are the earlier assessment, superseded by the current [necessity review](docs/IMPLEMENTATION_NECESSITY.md).

## 0.1.1 — official advisory coverage

- Complete 2026-11-14 official repository catalog snapshot: 66 advisories, including four without CVE IDs.
- Reviewed implementation accounting: 2 source backports, 13 absent mechanisms and 51 unresolved protections with concrete implementation plans.
- Separate source evidence for 31 CVEs named by enabled Ubuntu vendor patches.
- Bilingual coverage matrices, source-file hashes, per-advisory reasoning and official fix/introduction references.
- Twelve accounting regression tests plus CI checks prevent missing advisories, unsupported statuses, uncredited protections counted as fixed, stale generated tables and source-evidence drift.
- The frozen build007 engine patch is unchanged; the 51 planned protections are not implemented by this release.

## 0.1.0 — initial source release

- Frozen build007 cumulative backport and exact public source archive pins.
- Offline source reconstruction with vendor binary fixtures and whole-tree verification.
- Independent Linux build profiles, fresh build records and local ELF inspection.
- Benign native FPM/session/serializer/upload regression harness.
- Synthetic backup/replacement/restore rehearsal.
- English/Korean user documentation, license inventory, CI and scoped verification records.

This is a source/toolkit release, not a declaration of universal binary or application compatibility. See the verification record for the actual execution results accompanying this tag.
