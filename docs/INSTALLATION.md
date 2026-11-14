# Target acceptance, installation and rollback

This is an operator checklist, not an unattended deployment script. The public kit has no remote credentials, site-specific approval controller, container commands or service-manager integration.

## Before changing a live service

1. Record the current FPM executable hash, package revision, CPU architecture, NTS/debug/API settings, configure options, active configuration and exact extension/library inventory. Keep secrets private.
2. Reconstruct the pinned source, build on an equivalent isolated host and keep its fresh `build.json`, checksums and native results. The `portable` binary is not a distribution replacement.
3. Check required symbols, dynamic libraries, actual extension loading and your application's ordinary routes, authentication, session persistence and upload/delete flows. A different runtime serializer switch is intentionally rejected.
4. Run the candidate's configuration syntax check against a **safe copied test configuration** and run native checks in isolation. A syntax pass does not prove application behavior.
5. Create an external backup of the exact current executable. Verify its checksum and record owner, group, mode and any security labels/capabilities. Preserve the configuration separately.
6. Rehearse restoring the backup and activating the old executable through your existing service procedure. Ensure an independent administrative recovery path is available.
7. Decide whether the exact candidate/environment and remaining limitations are acceptable. This project's test results cannot make that decision for another site.

## What the included recovery tool proves

```sh
python3 -m patchkit rehearse \
  --candidate .work/build/php-fpm --output .work/recovery-drill
```

It creates a **new** directory with a synthetic original, copies/verifies a backup, stages the candidate, atomically replaces the synthetic target and restores the original. It refuses an existing directory and never touches a service. This checks file-handling mechanics, not your real service's rollback.

## Service transition

During an appropriate maintenance window, stage the approved candidate on the target filesystem outside the live path and verify its hash. Preserve the original file and metadata. Replace only the intended executable using your reviewed, platform-appropriate file transition procedure; then perform the existing FPM service's supported graceful activation.

Do not recreate a container or change images, mounts, environment, networking or unrelated application files as an incidental part of a binary replacement. If your operational contract uses an approval controller, use it; this kit does not override that contract.

Verify the **running workers**, not only the disk file: old workers may still execute the old image after a copy. Confirm service identity, required module loading, normal site responses, sessions, representative uploads and worker recovery. Observe bounded error/resource indicators against a pre-change baseline. Preserve failures as failures.

## Rollback

If acceptance fails, stop the rollout. Verify the exact external backup, restore the executable and metadata through the established file-only procedure, activate the old FPM through the same supported service process and repeat the normal-site checks. Record disk and running-worker identity. A restored checksum without a healthy running service is not completed rollback.

Keep the failed candidate and sanitized logs for diagnosis. Do not raise thresholds or change test expectations solely to declare success. No public command here authorizes changes to an existing production system.
