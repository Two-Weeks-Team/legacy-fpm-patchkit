# Troubleshooting

| Symptom | Check and next action |
|---|---|
| Archive SHA mismatch | Keep the file, compare its URL/hash to the pinned input and investigate upstream/repository integrity. Do not edit the expected digest to bypass the mismatch. |
| Output already exists | Choose a new `--output` or build destination. Preserve earlier results until reviewed. |
| Baseline/preimage mismatch | Confirm the three exact inputs and all 84 vendor patches. Do not apply the cumulative patch to a newer or already patched tree. |
| Whole-tree hash differs | Check packaging files outside `debian/`, local edits and `.pc`/`.orig` normalization. Compiler-generated files must not appear in the prepared input. |
| re2c/buildconf/configure failure | Keep tool versions and full logs; use the documented isolated profile and dependencies. Never reinterpret a partial build as completed. |
| OpenSSL/systemd errors on modern Linux | The Xenial profile needs the legacy target environment. Use `portable` for isolated regression, not as a drop-in alternative. |
| FPM cannot start | Check private config/socket path, permissions and the test log; do not point the harness at a production configuration. |
| Serializer switch is rejected | This is intentional for different handlers. Select the codec in initial config and inspect effective state. |
| Native test fails | Preserve its JSON and failed check; verify binary hash, clean INI and compiled features. Successful process cleanup does not make the functional check pass. |
| Extension loads but application fails | Loading is not full ABI/behavior proof. Reproduce with minimal plain data, preserve the failure and evaluate the module separately. |

Report sanitized reproducible details using the issue template. For suspected vulnerabilities use the private route in [SECURITY.md](../SECURITY.md).
