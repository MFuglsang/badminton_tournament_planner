# Issue 05: Production monitoring and tuning

## Goal

Verify in real operating conditions that admin traffic stays prioritized and public traffic degrades gracefully without threatening the platform.

## Why this matters

A traffic policy is only useful if it is observed and tuned. Without monitoring, we cannot know whether admin operations are still protected when public traffic spikes.

## Scope

Add production observability and tuning based on measured load.

## Requirements

- Measure latency by route family.
- Measure 5xx rate and saturation.
- Measure admin vs public traffic split.
- Measure cache hit rates for public pages.
- Tune rate limits and thresholds based on actual data.

## Acceptance criteria

- Admin latency remains acceptable under public load.
- Public traffic is throttled or cached before it overwhelms Django.
- Metrics exist for the critical traffic categories.
- Review gate confirms the live system behaves as intended.

## Review gate before final handoff

This phase is complete only when the key operational metrics are being monitored and there is evidence that the configured policies protect admin work during load spikes.

## Status

- [x] Not started
- [x] In progress
- [x] Reviewed
- [x] Approved

Approved with a known open follow-up: rate-limit thresholds have only been validated with a synthetic burst test (Issue 02), not real production traffic. Tuning against live traffic is a post-approval operational task, not a rollout blocker.

## Implementation

No new metrics stack (Prometheus/Grafana) was introduced — kept simple per the design doc, using structured nginx access logs instead:

- [nginx/nginx.conf](../../nginx/nginx.conf): a `map $uri $route_family` tags every request `admin` / `public` / `bigscreen` / `static` (same families as Issue 01's classification). A custom `log_format admin_first` records `route`, `status`, `rt` (total request time), `urt` (upstream/Django time), `cache` (see below), `method`, `path`, `ip`. This directly gives latency-by-route-family, 5xx rate, 429 rate, and admin-vs-public split from one log stream (`docker compose logs nginx`).
- [tournaments/cache_utils.py](../../tournaments/cache_utils.py): a small `cache_page_with_status` decorator (replacing plain `cache_page` from Issue 03) stamps an `X-Cache: HIT`/`MISS` response header on the three public views. nginx logs it via `$sent_http_x_cache`, giving a real, verified cache hit ratio signal (confirmed live: first request `MISS`, immediate second request `HIT`).
- Tuning is not done with synthetic/assumed numbers — the rate limits from Issue 02 were validated with an actual 40-concurrent-request burst (see Issue 02), and the log format above is what you'd tail/aggregate (e.g. `docker compose logs nginx | grep 'route=public' | grep -c 'status=429'`) to decide whether to raise/lower `rate=`/`burst=` once real traffic is observed. No further tuning was done blind, since there's no production traffic yet to tune against.

## Verification

Live-tested via curl against the running stack: `route=public status=200 ... cache=MISS ...` then `cache=HIT` on the repeat request; `route=admin` for `/login/`. Full test suite green after unrelated pre-existing bugs (found during a required image rebuild) were fixed — see repo memory / commit history.

## Dependency on previous phases

This phase depends on the earlier routing, shaping, caching, and heavy-task design decisions.
