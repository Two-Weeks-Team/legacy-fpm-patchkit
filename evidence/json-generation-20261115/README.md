# Retained JSON build-generation evidence

The [summary](../json-generation-portable-20261115.json) retains two existing successful Linux runs at head `9cd1fe002e9e3976bec7635356c8398071732835`:

| Run | Scope | Artifact |
|---|---|---|
| [43607944104](https://github.com/Two-Weeks-Team/legacy-fpm-patchkit/actions/runs/43607944104) | Paired cookie/FPM-log portable builds and the 96-request worker-file-log campaign | `fpm-log-paired-native`, ID 14118738912, digest `sha256:7c68291b0476d62cc1a082340e36bbd3917e6603e3f40a63aec50e83046f9387`, expires 2027-02-12T15:01:58Z |
| [43607943962](https://github.com/Two-Weeks-Team/legacy-fpm-patchkit/actions/runs/43607943962) | Default build007 portable build/native36 and four repository Checks jobs; Python 3.10/3.12 each ran 131 unit tests | `portable-build-evidence`, ID 14119580635, digest `sha256:678aba245741953f573c88d47b5433869470ac2704f58c5c8fbea55cdfe3e49e`, expires 2027-02-12T15:01:56Z |

`schema: 1` describes this retained-evidence summary. Its `verification_label`, `RETAINED_JSON_GENERATION_EVIDENCE_RECONCILED`, means that existing files and records were reconciled offline. It is **not** a runner result or a newly executed test. The original paired runner result remains `PAIRED_LEGACY_LOG_RUNTIME_PASS`, in both the summary's `runtime_campaign.runner_result` and the retained raw result file. Source/code review, local negative tests, build and actual FPM evidence remain separate layers.

## JSON tuple and build identity

All three build records report mode `pregenerated`, bundle SHA `bfa25ae262a65b6f158cf34581e82b40dc0f33c681f752bb9ed34ba937de55ce`, the same six reviewed input/generated C/companion-header hashes before and after, and the two selected JSON C targets. Each receipt binds its prepared-source SHA and is embedded in `build.json` with its file SHA. All three make logs contain **zero JSON generator commands**, normal JSON C compilation and six compiler warnings. No full binary reproducibility or unique cause of binary differences is inferred.

The verification levels differ:

- **Paired builds:** all five `SHA256SUMS` entries were verified against original file bytes, including both original CLI/FPM binaries. The public data archive excludes those binaries. After artifact expiry, their recorded hashes and the collection's verification result remain available, but the binary bytes cannot be recalculated from this data-only archive.
- **Default Checks:** CLI/FPM binary files were absent from the original artifact. Only `build.json`, `json-generation-plan.json` and `json-generation.json` were directly hashed. The two binary hashes were linked through agreement among `SHA256SUMS`, `build.json` and the actual `native-result.json`; they were **not** independently recalculated from binary bytes.
- The six JSON before/after values are recorded working-copy guard observations, independently reconciled to the fixed tuple. Generated C/header bytes are not included in these artifacts. The four existing standard/date lexer commands are preserved in the reviewed build script, followed by successful compilation under `set -e`; their generated outputs have no retained post-generation hashes, so this is indirect execution evidence.

## Actual paired behavior and prior-run comparison

The new paired run completed **48 producers + 48 barriers = 96 FPM requests**, 48 repeated trials, 328 worker-log frames and 24 clean owned-instance shutdowns. Candidate representation, the single-write parent expected-loss allowlist, exact response markers, worker continuity, empty request diagnostics and slice/shutdown reconciliation were checked. Producer PHPT passed once per build; each build separately passed 36 benign checks. Default Checks also passed its separate native36 campaign.

All 48 trial record sequences matched [the previous run 43606021097](../fpm-log-portable-20261114.json) after excluding PID/timestamps: stream, payload bytes, frame boundaries and close suffix had **zero differences**. Producer program bytes were identical. The original parent CLI/FPM binaries were directly byte-identical to that run. This is a comparison of these specific artifacts, not a promise of bit-identical recompilation or proof that JSON generation was the only cause of other binary differences.

## Retained raw data and privacy

[`raw.tar.gz`](raw.tar.gz) retains **556 original files, 2,756,346 uncompressed bytes**. [`raw-files.json`](raw-files.json) pins each member's SHA-256; the summary pins the index and archive SHA. Original artifact-relative paths are preserved under `paired/` and `checks/`. Copies remain available after the GitHub artifacts expire.

Included: paired result/response/log/trial/shutdown/PHPT/normal data, preparation records, all three build records, available source identities, JSON plans/receipts, `SHA256SUMS`, make logs, toolchain/configure arguments and the default native result. Standalone generated PHP programs, shell drivers, binaries, whole source/object trees and agent logs are excluded. PHPT files are regular test data. Every member is a unique safe relative path, regular mode 0644 with mtime 0, byte-identical to its original artifact file.

The scanner reported **12 findings**, all exact full response or JSON correlation lines for the two public synthetic labels `expansion-stderr-0` and `expansion-stderr-1`. They were classified as fixture labels without modifying raw bytes. The summary records their member/line/full-line SHA, **12 classified and zero unclassified**, rather than claiming zero scanner findings.

This is synthetic Ubuntu 22.04 portable worker-to-master **file-log** evidence. The parent allowlist assumes the single-write fixture, and arbitrary scheduling/concurrency was not accepted. Syslog delivery, full CVE-2024-9026 closure, Xenial/module/site and production acceptance remain unclaimed. Official-advisory credit added is zero: cumulative accounting remains **7 implemented / 14 mechanism-absent / 45 planned**, and default build007 **2 / 14 / 50**. Earlier FPM evidence and retained failures are unchanged.
