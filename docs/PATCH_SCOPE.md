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

Earlier minimal EOL mitigations and rejected candidates are historical inputs to the investigation, not alternate files to apply on top of this cumulative patch. Do not stack the patch onto a newer vendor/ESM tree; the preimage check must reject it.

## Authentication limits

The downloadable archives are pinned to known SHA-256 values over HTTPS. Earlier private work authenticated an archive-index → Sources → file-digest chain; a direct `.dsc` uploader-signature check lacked the uploader key. This public tool does not reproduce that signature chain and does not claim direct PGP authentication. Independently verify the repository/tag and source provenance when establishing your own trust policy.

License/author notices are in [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md). Raw operational sources, site content, credentials and approval records are excluded.
