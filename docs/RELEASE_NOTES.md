# Advisory coverage source release

The historical **v0.1.1 release** added complete official-advisory accounting: 2 implemented source backports, 13 absent mechanisms and 51 planned items. Its release artifact and validation results below retain that original assessment. The subsequent [necessity review](IMPLEMENTATION_NECESSITY.md) corrects current source accounting to **2/14/50** and separates actual implementation prerequisites. Another 31 vendor-patched CVEs are recorded separately. The frozen engine patch is unchanged; this assessment update implements no additional PHP protection. See the current [coverage matrix](SECURITY_COVERAGE.md).

This release contains the pinned build007 backport, source preparation and verification tools, isolated Linux build profiles, benign native FPM regression checks and bilingual operator documentation.

The v0.1.1 execution record includes its then-current 57 unit tests, fresh official-source reconstruction, and 36 named benign native checks in each of Ubuntu 22.04 and Ubuntu 16.04.7 x86-64. A separate Xenial stock/candidate comparison observed the intended serializer-policy difference. See `docs/VERIFICATION.md` for artifact hashes, correction history and evidence boundaries.

The release workflow runs unit/source checks and a fresh portable Linux build/native check before packaging the exact tag. The source archive and checksum manifest have GitHub build-provenance attestations. These attest the packaging workflow and artifact identity; they do not certify that PHP 7.0 is generally secure or that a binary is compatible with your site.

## Verify the download

Download the named source archive and `SHA256SUMS` from this release, then check the archive's SHA-256 against the manifest. With GitHub CLI:

```sh
gh attestation verify legacy-fpm-patchkit-0.1.1.tar.gz --repo Two-Weeks-Team/legacy-fpm-patchkit
```

Unpack the source and follow `README.md` or `README.ko.md`. Use Python 3.10+ for the control tools and an isolated Linux environment for compilation. No prebuilt universal binary or system package is included; build for and independently validate your target environment.

Read `SUPPORT.md`, `docs/BEHAVIOR_CHANGES.md` and `docs/VERIFICATION.md` before activation. In particular, different-codec runtime session serializer changes are intentionally rejected, external-module/application compatibility is not inherited, and retained historical failures remain documented.

The kit does not remotely deploy, auto-update, reload services or control containers. Source checks, native benign tests and synthetic file recovery are distinct evidence layers.
