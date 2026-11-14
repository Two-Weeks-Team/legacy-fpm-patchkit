# Patch scope and provenance

## Exact inputs

Baseline: Ubuntu PHP `7.0.33-0ubuntu0.16.04.16`, from the three official archive files pinned in [inputs.json](../provenance/inputs.json). Preparation overlays the **entire** Debian source archive, including four binary EXIF regression fixtures outside `debian/`, and applies 84 vendor patches before the project patch.

Build007 cumulative patch SHA-256:

```text
a7db5d018d5f7cef41c726b61eccd794356c5d06bb1bb4322027dde88fbd108c
```

The [source manifest](../provenance/build007-source.json) records 46 changed files and their before/after digests. It is a retained source-freeze record; its historical `stage` field is not the public release's verification result. Consult fresh [verification](VERIFICATION.md).

## Normalization

Historical source freezing included 12 `.orig` patch backups, producing a different whole-tree hash from a clean reconstruction. Quilt `.pc/` bookkeeping also depends on the extraction method. Public whole-source hashing therefore uses regular-file relative-path/SHA maps serialized as compact sorted JSON, excluding `.pc/` and `.orig` backups. Symlinks are rejected. The normalized clean source has 19,001 files; the public candidate has the same file set with the frozen changes.

Both normalized expected digests are pinned in `inputs.json`. A changed compiled source file is not excused by normalization. Archive content, patch identity, all changed pre/post images and the complete normalized inventory are checked independently.

## Origins and rationale

The upstream basis is [PHP commit 01a40e89fbfc499936e3b05888d8f00bfde886df](https://github.com/php/php-src/commit/01a40e89fbfc499936e3b05888d8f00bfde886df), “Avoid state corruption via bailout,” concerning CVE-2026-109618 and CVE-2026-109619. See the upstream [OOM advisory](https://github.com/php/php-src/security/advisories/GHSA-w8hw-w9fx-j79w) and [request-state advisory](https://github.com/php/php-src/security/advisories/GHSA-6wmf-4rv5-p3rp) for the original scope.

The PHP 7.0 port addresses allocator/failure propagation, consistent data-structure state, safe execution boundaries, request teardown/initialization and session handling. Subsequent changes include serializer-transition restrictions and the build007 `zend_call_function` OOM-entry condition. The adaptation is independent and is not claimed to be identical to a vendor-maintained package or certified by upstream.

### Problem-to-source mapping

All paths below are sections of the frozen [cumulative patch](../patches/build007.patch), not additional patches to stack onto it.

| Problem or protective adaptation | Principal changed source | Mechanism and evidence boundary |
|---|---|---|
| OOM bailout/state-corruption class described in CVE-2026-109618 | `Zend/zend_alloc.c`, `Zend/zend_execute.c`, `Zend/zend_execute_API.c`, `Zend/zend_vm_def.h`, `Zend/zend_vm_execute.h`, allocation callers | Delayed soft OOM, safe execution boundaries and explicit failure propagation replace unsafe continuation/early exits on the targeted paths. Source identity is verified; the fresh benign runtime suite does not inject OOM or prove complete exploit resistance. |
| Stale request-state class described in CVE-2026-109619 | `Zend/zend_execute_API.c`, `main/main.c`, `ext/standard/basic_functions.c`, `ext/session/session.c` | Reset released executor/error/superglobal state and initialize relevant state before early request/session work. Upstream's supported-version demonstrations are context, not proof that every case applies to PHP 7.0 or that this adaptation covers every state lifetime. |
| Early upload-progress object handling | `ext/session/session.c`, `ext/standard/var.c`, `ext/standard/var_unserializer.re`, `ext/standard/php_var.h` | Scoped early decoding avoids user-class resolution, preserves a representation, restores mode and allows ordinary initialization to decode normally. This is a source-level protective adaptation; public plain-data upload tests do not exercise object-callback security cases. |
| Session format changes across request phases | `ext/session/session.c` | Different-codec runtime changes are rejected regardless of the current progress flag. The published paired stock/candidate result distinguishes this behavior, and native checks exercise all three codecs with progress On/Off. |
| Pending OOM at function entry/return and request teardown | `Zend/zend_execute_API.c`, VM sources, `main/main.c` | Handle pending failure before later result use and clear temporary OOM/early-mode state at request boundaries. These are related port correctness protections, not separately identified CVEs or a guarantee against unknown future defects. |

The official advisories report severe consequences, including remote code execution, in supported PHP branches. In particular, the OOM advisory distinguishes a demonstrated mod_php attack from FPM source-analysis susceptibility without a complete FPM exploit; the stale-state advisory reports a demonstrated FPM session-lifecycle path. Do not collapse these different upstream claims into a fresh PHP 7.0 FPM exploit test. See [verification](VERIFICATION.md) for what actually ran here.

Earlier minimal EOL mitigations and rejected candidates are historical inputs to the investigation, not alternate files to apply on top of this cumulative patch. Do not stack the patch onto a newer vendor/ESM tree; the preimage check must reject it.

## Authentication limits

The downloadable archives are pinned to known SHA-256 values over HTTPS. Earlier private work authenticated an archive-index → Sources → file-digest chain; a direct `.dsc` uploader-signature check lacked the uploader key. This public tool does not reproduce that signature chain and does not claim direct PGP authentication. Independently verify the repository/tag and source provenance when establishing your own trust policy.

License/author notices are in [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md). Raw operational sources, site content, credentials and approval records are excluded.
