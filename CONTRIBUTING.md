# Contributing

Useful contributions include reproducible source/build fixes, narrowly scoped regression cases, accurate translations, documentation improvements and independently measured compatibility reports.

1. Read [SUPPORT.md](SUPPORT.md) and [SECURITY.md](SECURITY.md).
2. Use a new local branch and a disposable Linux environment for native work.
3. Run `python3 -m unittest discover -v` and `python3 -m patchkit verify`.
4. For preparation changes, reconstruct from the pinned public archives and show normalized before/after tree hashes.
5. For runtime changes, include a failing regression and fresh native results. A source-only check or a mock is not a runtime pass.
6. Submit a focused PR explaining the trigger, resulting behavior, validation and remaining limits.

Do not reformat the frozen upstream-derived patch incidentally. A new patch requires new source identities, attribution, regression evidence and release notes. Do not mix unrelated changes in one commit.

Use synthetic fixtures and scrub private paths, hosts, accounts, cookies and logs from reports. Keep intentional upstream author credits and license notices. Do not copy private development or operational history into this public repository.
