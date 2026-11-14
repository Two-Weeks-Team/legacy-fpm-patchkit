# Scheduled official-advisory collection

[한국어](ADVISORY_AUTOMATION.ko.md)

This optional service collects public PHP repository security advisories and produces implementation worklists. It does not implement PHP changes, build binaries, change servers or declare new issues fixed. The [reviewed coverage matrix](SECURITY_COVERAGE.md) remains a dated record; this feed tracks subsequent changes.

## Processing contract

1. Collect every page from the official [php/php-src advisory API](https://docs.github.com/en/rest/security-advisories/repository-advisories#list-repository-security-advisories), limited to published entries. No GitHub token is required.
2. Validate identifiers, official URLs and affected-package metadata; hash canonical metadata revisions. GHSA remains the primary identity because some entries have no CVE.
3. Track additions, revisions, withdrawals and entries missing from a complete listing. Never silently delete history.
4. Credit a human verdict only when upstream metadata and the exact candidate-source digest match the bundled review. New, changed, withdrawn or missing entries become **PLANNED**. Collection never grants a resolved/non-applicable verdict.
5. Atomically commit the complete snapshot, successful-run record and watermark in D1. Failed attempts retain the last successful result. A 120-second lease prevents overlapping publishers; expired owners cannot commit.
6. Export JSON and an escaped Markdown implementation worklist for separate source review, implementation and regression work.

The reviewed seed dated 2026-11-14 contains **66 advisories: 2 source implementations, 13 specific mechanisms absent and 51 planned protections**. These labels apply to the pinned source, not arbitrary PHP installations. Vendor-patch coverage is separately documented in the matrix. Raw advisory descriptions, exploit payloads and operational records are excluded.

### Shared GitHub quota and optional authentication

GitHub permits public advisory reads without authentication, but anonymous quota is shared by outgoing IP. A deployed Worker encountered a real **403 with remaining quota 0** on 2026-11-14; local API success did not establish cloud success. [GitHub's rate-limit guidance](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api) explains the distinction. Refusal reports include numeric limit/reset/Retry-After headers, never the response body. A recorded future reset suppresses further calls in that credential mode until it expires.

For reliable scheduled use, configure a **dedicated fine-grained token for public read access**, without private-repository or write permissions. The [endpoint's official permission contract](https://docs.github.com/en/rest/security-advisories/repository-advisories#list-repository-security-advisories) allows public-resource reads without additional repository permissions. Store it as the optional Worker secret `GITHUB_READ_TOKEN` (or the identically named local environment variable). Do not copy a broad personal CLI credential automatically. The collector sends it only to the validated official API origin/path and refuses redirects/foreign pagination.

```sh
npx wrangler secret put GITHUB_READ_TOKEN --config .work/wrangler.deploy.json
```

Enter the token only at Wrangler's secure prompt, never in chat or public files. If you later deploy with `--secrets-file`, preserve the already configured optional secret; do not replace it with a placeholder. Successful authentication is a normal access setup, not permission to ignore a further refusal. Investigate any subsequent 401/403 before retrying.

## Shared local batch

Node **24** is required. From `automation/advisory-sync`:

```sh
npm ci
npm run check
npm test
npm run batch -- sync
npm run batch -- export --kind status
npm run batch -- export --kind backlog --format markdown
npm run batch -- export --kind catalog
```

CLI and Worker call the same collector/planner/coordinator. Local state defaults to `.work/advisory-sync` relative to the current directory; select a dedicated location with `--state-dir DIR`. Sync creates an owned, initially empty directory and refuses unrelated nonempty directories or symlink targets. Export is read-only and can display the bundled seed without creating state. Sync exits 0 on success, 1 on failure and 2 when busy.

A terminated local process can leave `lock.json`. Confirm no process still owns that state directory before manually removing only that lock file. Never remove a running process's lock. D1 leases expire automatically. Last-good data is not necessarily fresh: inspect health and the watermark.

## Cloudflare deployment

Use a dedicated Worker and D1 database in an account you control. Your application domain need not be managed by that account: use `workers.dev` without attaching a production route.

```sh
cd automation/advisory-sync
npm ci
npx wrangler whoami
CLOUDFLARE_ACCOUNT_ID=YOUR_ACCOUNT_ID npx wrangler d1 create legacy-fpm-advisory-sync
```

Put the returned database UUID and your account ID into a local deployment copy of `wrangler.jsonc`. Its checked-in UUID is a placeholder. If the copy lives elsewhere, correct the relative `main` and `migrations_dir` paths or make them absolute. Keep this copy under ignored `.work/`. Select the account explicitly rather than changing a shared login.

Create ignored `.work/secrets.json` containing a random secret of at least 32 characters under the key `SYNC_TOKEN`, with owner-only file permissions. Never put credentials in public files, URLs, shell arguments or CI logs. Wrangler uploads this secret with the deployment atomically:

```sh
npx wrangler d1 migrations apply legacy-fpm-advisory-sync --remote --config .work/wrangler.deploy.json
npx wrangler deploy --config .work/wrangler.deploy.json --secrets-file .work/secrets.json
```

The template sets the D1 binding, required secret, disabled preview URLs, structured observability and **`0 * * * *`**. [Cron](https://developers.cloudflare.com/workers/configuration/cron-triggers/) uses UTC and can take up to 15 minutes to propagate. This expression runs every hour on the hour, including in KST. Check current [Workers limits](https://developers.cloudflare.com/workers/platform/limits/) and [D1 limits](https://developers.cloudflare.com/d1/platform/limits/); these scripts never upgrade billing plans.

After deployment, POST once to `/internal/sync` with a Bearer token read from local secret storage. Verify `state=HEALTHY`, `origin=collected`, a real `lastSuccessAt`, the catalog count and a successful recorded run. A manual success plus configured Cron is not proof of an actual scheduled run: after the next schedule, confirm `lastAttempt.trigger` is `cron:0 * * * *`.

## Public outputs

| GET endpoint | Meaning |
|---|---|
| `/status.json` | Latest attempt, last success, source/snapshot identities and counts; HTTP 503 unless healthy |
| `/catalog.json` | Retained normalized official catalog |
| `/coverage.json` | All assessments and reviewed/current identities |
| `/changes.json` | Changes from the last successful run, even if a later attempt failed |
| `/backlog.json` | PLANNED entries, advisory metadata and next action |
| `/backlog.md` | The same PLANNED work as escaped Markdown |

Public GET/HEAD never trigger collection. Authenticated POST `/internal/sync` returns 200 on success, 409 when busy, 502 on collection failure and 503 when storage/control is unavailable. Public reads permit cross-origin access. Structured run logs exclude the control token and upstream response bodies.

Cloudflare can reject a client's default library signature with **1010 before the Worker executes**. Its [official guidance](https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloudflare-1xxx-errors/error-1010/) recommends a descriptive User-Agent identifying the actual application. Do not impersonate a browser or disable protections to hide a failed test. A 1010 response is edge rejection, not the Worker's authentication result or a collection attempt; keep these outcomes separate. Newly registered `workers.dev` addresses may also need initial DNS/TLS propagation time.

Health is `NEVER_SYNCED` for seed-only data, `HEALTHY`, `STALE` after 150 minutes without success, or `FAILED` when the latest attempt failed. Catalog/backlog remain readable with explicit health metadata after collection failure. Storage corruption fails closed with HTTP 503 instead of silently presenting seed data as a live result.

## Reviewed updates and verification

After implementation or a source-based non-applicability decision, record evidence in the public coverage ledger, regenerate with `npm run seed`, review the diff, test and redeploy. Automatic collection cannot edit that ledger or mark work complete. Refreshing a timestamp does not renew evidence.

Tests cover complete pagination, bounded responses/deadlines, revision-bound verdicts, retained history, local directory ownership, actual Miniflare D1 transactions and the bundled Worker HTTP/scheduled handlers. Runtime tests use a simulated upstream; actual GitHub API and deployed-service receipts are separate evidence. CI checks generated seed/types, strict TypeScript, dependency advisories and these tests without deployment credentials.

This feed covers the public `php/php-src` advisory API, not all historical PHP, OS or library CVEs. It does not discover unreported vulnerabilities. History is append-only: observe D1 growth and quotas rather than silently deleting evidence. A failed collection does not establish that no new advisories exist.
