# Support and verification boundary

This independent source release targets **PHP 7.0.33, Ubuntu source revision `7.0.33-0ubuntu0.16.04.16`**, with the exact cumulative patch identified in `provenance/`. PHP 7.0 reached upstream end of life on [10 January 2019](https://www.php.net/eol.php). This project is not a replacement for maintained PHP or OS security updates.

| Layer | Supported scope | What success does not prove |
|---|---|---|
| Control/source tools | Python 3.10+, Linux/macOS, `patch`; pinned archives only | Native runtime compatibility |
| `portable` build | isolated Linux regression build, minimal built-in extensions | Drop-in compatibility with a distribution's binary or modules |
| `xenial-amd64` build | Ubuntu 16.04 x86-64 NTS/non-debug with documented libraries | Arbitrary `.so`, site, OS patch level or service compatibility |
| Native checker | Python 3.5+ Linux test harness; local private socket; three codecs, progress On/Off, tiny uploads | Exploit resistance, broad PHPT acceptance, real-site upload/DB behavior or load capacity |
| Inspection | ELF architecture and checksum/build-record facts; no binary execution | A complete ABI or library compatibility verdict |
| Recovery rehearsal | real file copy/replace/restore in a NEW synthetic directory | Recovery of an activated production service |

## Intentional change

Switching `session.serialize_handler` to a different codec during a request is rejected. Applications that depend on that behavior must be adapted or use a different maintained runtime. Initial codec selection and same-codec assignments remain testable. See [behavior changes](docs/BEHAVIOR_CHANGES.md).

## Known gaps and retained historical failures

- A previously tested extension (`msgpack`) had serializer/data-transformation failures. This kit does not ship a replacement for it and must not be described as fixing that module.
- Historical broad testing included a candidate-only PHPT failure and non-distinguishing paired tests. Those were not erased by operational acceptance; see [verification](docs/VERIFICATION.md).
- External extensions, opcache interactions, full application behavior, application-specific upload/DB flows and long-running production behavior require independent operator acceptance.
- A fresh binary is a new artifact, even when source hashes match. Historical build007 binary compatibility is not inherited by a new compilation.
- Source SHA verification detects drift against bundled pins; it does not itself authenticate a compromised repository. Verify the release/tag and compare upstream provenance. The kit does not claim direct `.dsc` signer authentication.
- Portable and Xenial profiles differ. No universal prebuilt binary, OS package, automatic updater or remotely operated deployment agent is provided.

## Deployment decision

`SOURCE_VERIFIED`, `INSPECTED`, `BUILT_NOT_RUNTIME_VERIFIED`, `BENIGN_RUNTIME_PASS` and `REHEARSAL_PASS` each describe one layer. **None means `DEPLOYMENT_APPROVED`.** Do not activate a candidate until its target libraries/modules, your ordinary site flows, backup and actual service rollback have been checked. A failed prerequisite remains a failure.
