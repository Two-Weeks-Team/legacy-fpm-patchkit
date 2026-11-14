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

### Xenial x86-64 execution — 2026-11-14

A separate local Ubuntu 16.04.7 x86-64 guest compiled the `xenial-amd64` profile from the same verified source, using GCC 5.4.0 and glibc 2.23. The final native harness ran **6 codec/progress combinations with 36 named benign checks** successfully on that new binary. The build used an immutable toolkit snapshot; the final runtime harness and policy comparison used later immutable snapshots containing the documented harness fixes.

- [Build record](../evidence/xenial-build-20261114.json) and [library/toolchain package versions](../evidence/xenial-packages-20261114.txt)
- [Native result](../evidence/xenial-native-20261114.json)
- [Paired benign policy comparison](../evidence/xenial-policy-difference-20261114.json): the retained stock copy allowed `php` → `php_binary`, the candidate rejected it and retained `php`, and both started a normal session. The stock copy is identified by its hash; it is not a newly downloaded package or a distributed asset.
- [Nonexecuting inspection](../evidence/xenial-inspection-20261114.json) and [synthetic file recovery](../evidence/xenial-recovery-20261114.json), performed on the copied artifact on macOS. These are separate from Linux runtime evidence and actual service recovery.
- FPM SHA-256: `47f253738f5c1efe9834d5a5700e83ff5dd599aa05ef8dad51bc05becb6f8da9`

The old guest Python 3.5 `platform.libc_ver()` heuristic originally reported glibc 2.9 incorrectly. The [original build record](../evidence/xenial-build-legacy-python-original-20261114.json) is retained, alongside the [correction receipt](../evidence/xenial-libc-correction-20261114.json). Querying the running GNU libc reports 2.23; all other build fields and both binary hashes are unchanged. A new runtime run records the corrected environment. This metadata correction does not change a test verdict.

Earlier local attempts failed on missing multiarch configuration, a host-shared script being edited during execution, and Python 3.5 import-path handling in the policy harness. They were not counted as passes. The corrected build uses the multiarch setting and an immutable script snapshot; the policy probe uses a legacy-compatible string import path. The final records above come from completed runs. Private machine paths and raw host logs are not included.

These results cover the recorded built-in runtime behavior and intentional policy difference. They do not certify external extensions, an existing application's configuration, exploit resistance or a live deployment. No test binary is included in the source release.

### Explicit ACL/filter variant — 2026-11-14

The optional `acl-filter-20261114` source adds GHSA-62xp-839h-2637
(CVE-2026-91768, complete IPv6 ACL comparison) and GHSA-ch8v-r6jh-4vvr
(complete URL sanitizer table initialization). The default build007 remains
frozen. See [selection and commands](ACL_FILTER_VARIANT.md).

[Paired run 43592653493](https://github.com/Two-Weeks-Team/legacy-fpm-patchkit/actions/runs/43592653493)
successfully built baseline/candidate on Ubuntu 22.04 portable with the same
toolchain. Actual FPM A2 accepted the mismatching peer on baseline and rejected
it on candidate; exact-match, early-mismatch and mapped controls A1/A3/A4/A5
remained correct. Baseline Valgrind reported the exact table read at
`sanitizing_filters.c:108` 37 times; candidate had zero errors. All 270 filter
cases, five existing PHPTs plus the new PHPT, and 36 benign checks passed on each
binary. Twelve owned FPM instances exited cleanly. Baseline ordinary output
also passed, so Valgrind supplies the distinguishing filter RED.

[Public evidence](../evidence/acl-filter-portable-20261114.json) contains source,
patch, binary and raw-file hashes plus the GitHub artifact digest. This does not
establish this variant's Xenial ABI, external-module compatibility or production
deployment. Its source catalog inherits build007 and adds two implementations:
4 implemented / 14 mechanism-absent / 48 planned.

The same-commit [Checks 43592617045](https://github.com/Two-Weeks-Team/legacy-fpm-patchkit/actions/runs/43592617045)
failed before build because its coverage ledgers still pinned the previous
build driver's hash. That failure remains recorded. We compared the unchanged
configure profiles, relinked 43 unchanged source references and the driver hash,
and added a regression proving kit drift fails without prepared source.
[Checks 43593350544](https://github.com/Two-Weeks-Team/legacy-fpm-patchkit/actions/runs/43593350544)
then passed all four jobs, including 95 unit tests on Python 3.10/3.12, the Worker
checks and the actual default build007 build/FPM/inspection/recovery steps.

## Optional benign policy comparison

In an isolated environment with two trusted **copied** binaries and the required libraries:

```sh
python3 scripts/policy-diff.py \
  --stock-fpm /path/to/trusted-stock-copy \
  --candidate-fpm .work/build/php-fpm \
  --output .work/policy-difference.json
```

The probe starts separate private FPM instances and uses a fresh empty session, so a data-decoding failure cannot stand in for the policy difference. It requires all of: stock permits `php` → `php_binary`, candidate rejects it and retains `php`, and both can start a normal session. Two rejections are not a distinguishing control and yield `FAIL`.

`POLICY_DIFF_OBSERVED` establishes this deliberate benign behavior change only, not exploit resistance or closure of every vulnerability. A stock executable is not included in the distribution. Both native-report CLIs require a new output filename and preserve earlier reports.

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
| `POLICY_DIFF_OBSERVED` | The named benign serializer-policy difference was observed against a hashed stock copy |
| `LOCAL_RUNTIME_PASS` | The paired local ACL/filter controls, target Valgrind observation, output/PHPT checks and benign regressions passed on the recorded portable binaries |
| `PAIRED_MULTIPART_RUNTIME_PASS` | The recorded parent/candidate portable builds met the small multipart request, per-request warning, shutdown-tail, INI PHPT and normal regression contracts; no production or broad compatibility verdict |
| `INSPECTED` | ELF/hash facts read without binary execution |
| `REHEARSAL_PASS` | Synthetic file backup/replace/restore worked |

None means full security, arbitrary module compatibility or production acceptance. Bit-for-bit reproducibility with the old deployed binary is not claimed.

## Multipart parent/candidate evidence

The [final paired run 43599570950](https://github.com/Two-Weeks-Team/legacy-fpm-patchkit/actions/runs/43599570950), head `dba32efcad59633141adc51e30b3bc3e0d4257ea`, completed full source preparation, both portable builds, 60 FPM requests, parent/candidate INI controls and 36 normal checks per build. All stages ran. Parent source `a3b486ac…` and candidate `01ea4166…` are bound to exact executable hashes in [the public result](../evidence/multipart-portable-20261114.json); [retained raw data](../evidence/multipart-20261114/README.md) permits checking after artifact expiry.

The original run 43597987318 failed at its first parent case because its PHP fixture emitted output before starting a session. Candidate runtime and later tests did not run. This remains a tool failure. Output buffering corrected it; a further review found aggregate warnings could mask a 2+0 request distribution and a later off-channel warning. Request-specific log slices and explicit shutdown tails now reject those patterns. Their negative decision tests are synthetic; actual FPM results come from the paired runs.

Run 43598955155 completed the same source/binary behavior before the final tail guard; its 60 responses agree with the final run after removing PIDs. Same-head default-build Checks 43599554284 passed four jobs and 105 unit tests, but is not evidence for the multipart limits. The fresh multipart evidence demonstrates benign boundary/parts controls and normal preservation only; no callback END trace, Xenial/module/site acceptance, load test or production deployment is claimed.
