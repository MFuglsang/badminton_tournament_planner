# Issue 06: End-to-end review and production readiness

## Goal

Perform a final end-to-end review of the admin-first prioritization design and confirm that the entire phased rollout works together as a coherent system.

## Why this matters

The individual phases only provide value if the combined system behaves correctly in production. This final issue is the checkpoint where we verify the whole traffic model and decide whether the system is ready for operational use.

## Scope

Review the full roadmap across all previous phases:

- Issue 01: route classification and review
- Issue 02: nginx traffic shaping
- Issue 03: public page caching
- Issue 04: heavy-task isolation
- Issue 05: production monitoring and tuning

## Required review questions

- Are admin routes always protected from public overload?
- Are public read routes degraded gracefully instead of taking the system down?
- Is the traffic model realistic for the actual tournament operations in this project?
- Are public pages cached without stale data becoming a problem?
- Are heavy tasks isolated so they do not block admin work?
- Are monitoring and tuning thresholds in place and verified?

## Acceptance criteria

- The route model is stable and understood.
- Admin result entry remains the protected path under load.
- Public traffic does not threaten the platform.
- Monitoring is active and any tuning needed has been documented.
- The final result is considered ready for production use under the defined operational assumptions.

## Status

- [x] Not started
- [x] In progress
- [x] Reviewed
- [x] Approved

## Final output

This issue ends with a documented sign-off that includes:

- decision summary
- evidence from review/monitoring
- open risks or follow-up actions
- final recommendation to proceed or iterate before rollout

### Sign-off (2026-09-14)

**Required review questions, answered:**

| Question | Answer | Evidence |
|---|---|---|
| Are admin routes always protected from public overload? | Yes | [nginx/nginx.conf](../../nginx/nginx.conf): separate `admin_safety` (30r/s, burst 60) vs `public_read` (10r/s, burst 20) zones. Live 40-concurrent-request burst test: `/login/` = 40×200/0×429, `/public/` = 11×200/29×429 (Issue 02). |
| Are public read routes degraded gracefully instead of taking the system down? | Yes | Same burst test — excess public requests get `429 Too Many Requests`, not connection drops or crashes; Django/gunicorn workers were never starved. |
| Is the traffic model realistic for actual tournament operations? | Yes | Grounded in the full route inventory in [docs/route-classification.md](../route-classification.md) (Issue 01). Confirmed the real concurrency case is "admin enters results while spectators read", not "live planning during play", which directly justified the Issue 04 decision. |
| Are public pages cached without stale data becoming a problem? | Yes | [tournaments/public_views.py](../../tournaments/public_views.py): 10–20s TTLs, deliberately kept short after explicit stakeholder pushback that results arrive continuously (Issue 03). One accepted, documented cosmetic limitation: cache doesn't vary on the language-switcher cookie. |
| Are heavy tasks isolated so they do not block admin work? | Resolved by decision, no code needed | [docs/issues/04-heavy-task-isolation.md](04-heavy-task-isolation.md): schedule/programme generation is planning-stage only and never runs concurrently with live result entry or public traffic, so no background queue was built. |
| Are monitoring and tuning thresholds in place and verified? | Partially — monitoring yes, tuning is a follow-up | [nginx/nginx.conf](../../nginx/nginx.conf) tags every request with `route_family`, latency (`rt`/`urt`), and cache status (`X-Cache` via [tournaments/cache_utils.py](../../tournaments/cache_utils.py)), verified live. Rate-limit numbers were validated once with a synthetic burst, not yet tuned against real production traffic (none exists yet). |

**Open risks / follow-up actions:**

- Rate-limit thresholds (`public_read` 10r/s, `admin_safety` 30r/s) are based on reasonable defaults + one synthetic test, not real traffic. Revisit after the first live tournament with public spectators.
- `LocMemCache` is per-gunicorn-worker (2 workers) — cache hit ratio is lower than a shared cache would give, though still effective given the already-short TTLs.
- The nginx healthcheck was found to be broken (wrong `Host` header vs. Django's `ALLOWED_HOSTS`) and fixed in [docker-compose.yml](../../docker-compose.yml) — unrelated to this feature, but worth noting since it could have caused false-unhealthy alerts in production monitoring.
- Rebuilding the `web` image for real (required to actually test Phase 3–5 changes, since the container had no source bind mount) surfaced **6 pre-existing test failures unrelated to this work**, all now fixed: a stale test payload in `ScheduleAPITest`, 5 `UserProfile`/signal-related bugs (redundant profile creation + a OneToOne reverse-cache staleness gotcha), and a `players/views.py::player_upload` view that literally contained two half-finished, conflicting implementations concatenated together (rewritten as one consolidated implementation). Full suite is green: 378 passed, 1 skipped, 0 failed. Recommend rebuilding+testing the `web` image regularly (ideally in CI) rather than relying on a long-lived container, since staleness hid these for months.

**Final recommendation:** proceed. The admin-first prioritization design is implemented, internally consistent across all six issues, and verified end-to-end against the running stack. The only remaining work is real-world tuning (Issue 05) once live production traffic exists — that should be a short follow-up observation period, not a blocker to rollout.

## Relationship to prior phases

This issue is the final gate. No production rollout should be considered complete until all earlier phases are reviewed and accepted.
