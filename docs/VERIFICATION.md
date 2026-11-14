# Verification record

This page separates fresh public-kit execution from historical development evidence. CI results are linked from the README; consult the exact commit/run rather than a badge alone.

## Fresh public-kit checks

- Pinned public archives were freshly downloaded and SHA-verified on 2026-11-14.
- Fresh reconstruction applied 84 Ubuntu vendor patches and the unchanged build007 cumulative patch.
- All 46 pre/post image hashes and the complete normalized baseline/candidate source digests matched.
- Unit tests cover unsafe archive paths/links, existing-output preservation, hash drift, vendor binary fixtures, FastCGI protocol/error/budget handling, nonexecuting ELF inspection and synthetic backup/restore.
- Native build and regression results are recorded as separate JSON evidence under `evidence/`; only completed records are published as passes. In-progress or failed runs are not implied to pass by source checks.

### Portable Linux execution — 2026-11-14

[CI run 43552541737](https://github.com/Two-Weeks-Team/legacy-fpm-patchkit/actions/runs/43552541737) completed successfully on Ubuntu 22.04 x86-64/glibc 2.35. It freshly fetched/prepared the source, compiled CLI/FPM, ran **6 codec/progress combinations with 36 named benign checks**, inspected the artifact and completed synthetic recovery. Python 3.10 and 3.12 unit jobs also passed.

- [Build record](../evidence/portable-build-20261114.json)
- [Native result](../evidence/portable-native-20261114.json)
- FPM SHA-256: `6f28b2dd8ca41108bca126e53b9cda476ee0f3c57cb4a01d1dd006583819e7ee`

Earlier CI runs [43551910076](https://github.com/Two-Weeks-Team/legacy-fpm-patchkit/actions/runs/43551910076) and [43552196161](https://github.com/Two-Weeks-Team/legacy-fpm-patchkit/actions/runs/43552196161) failed compilation when modern Bison regenerated an incompatible old grammar skeleton. The first run also failed to retain hidden-directory logs; the second preserved the cause. Those runs remain failed. Using the verified release-generated parser sources corrected the build without weakening implicit-declaration/integer-conversion checks.

The recorded portable binary is **not** claimed compatible with Xenial or external modules. A later tag reruns its own CI; compare the relevant run and binary identity rather than assuming a previous binary hash is the new output.

The Linux checker exercises the three built-in session codecs, progress On/Off, same-handler assignment, different-handler rejection, plain session round trips, small multipart upload/digest/temp cleanup and same-worker continuity. It uses no production INI, external modules, user accounts, database or remote site.

## Historical evidence and limits

The original project built and evaluated build007 in a legacy environment and performed a narrowly scoped FPM deployment. That is context, not fresh acceptance of this public build. Private operational receipts and risk-acceptance tokens are not shipped.

Historical broad testing also recorded:

- V3: three msgpack-related failures; no replacement msgpack module is distributed here.
- V2: one candidate-only PHPT failure; this source release does not claim a completely green broad PHP suite.
- An initial V4 run was invalid. A later paired expectation test passed on both stock and candidate and therefore was not a distinguishing security negative control.

These results remain failures/limits, not exceptions silently promoted to PASS. Fresh benign regression success neither erases them nor proves every exploitation path closed.

## Meaning of result labels

| Label | Evidence |
|---|---|
| `INPUTS_VERIFIED` | Bundled patch matches the frozen manifest |
| `ARCHIVES_VERIFIED` | Downloaded inputs match pinned hashes |
| `SOURCE_VERIFIED` | Exact vendor baseline and patched source inventory agree |
| `BUILT_NOT_RUNTIME_VERIFIED` | Compilation produced recorded binaries; separate runtime evidence needed |
| `BENIGN_RUNTIME_PASS` | The named local benign behaviors passed on the recorded binary |
| `INSPECTED` | ELF/hash facts read without binary execution |
| `REHEARSAL_PASS` | Synthetic file backup/replace/restore worked |

None means full security, arbitrary module compatibility or production acceptance. Bit-for-bit reproducibility with the old deployed binary is not claimed.
