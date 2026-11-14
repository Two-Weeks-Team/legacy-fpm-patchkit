# Security policy

This kit addresses selected legacy-runtime changes; it is not a maintained PHP security branch. Upgrading to supported PHP is the recommended long-term remediation.

## Report privately

Use [GitHub private vulnerability reporting](https://github.com/Two-Weeks-Team/legacy-fpm-patchkit/security/advisories/new) when available. If the form is unavailable, open an issue requesting a private reporting channel **without technical vulnerability details**, then wait for a maintainer-provided private channel. Do not publish exploit payloads, account details or access logs in an issue.

Provide the kit commit/tag, source/binary hashes, build profile/toolchain and a minimal sanitized reproduction. Separate source integrity, runtime behavior and application impact. Do not send passwords, cookies, real session data or private configuration.

## Trust boundaries

- Source preparation verifies pinned archives, rejects links/special archive entries and writes only a new staging directory.
- Build and native tests execute source/binaries. Run them in a disposable isolated Linux environment without credentials or access to production networks.
- `inspect` reads ELF/hash metadata without running the candidate. Native checks explicitly run the provided trusted test binary.
- No remote deployment, service manager, container lifecycle or automatic production file replacement is implemented.
- CI has read-only repository permissions; source/build tests receive no deployment secrets. Release integrity records are distinct from a claim that the runtime has no vulnerabilities.

There is no guaranteed response SLA. Publish coordinated fixes with regression evidence and preserved failure history.
