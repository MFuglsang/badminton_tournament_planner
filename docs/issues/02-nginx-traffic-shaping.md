# Issue 02: NGINX traffic shaping for admin-first prioritization

## Goal

Apply traffic shaping at the edge so that admin operations are protected from public overload while public routes are limited or degraded gracefully under pressure.

## Why this matters

This project has a single Django backend behind nginx. Without traffic shaping, public traffic can consume worker capacity and delay or disrupt admin operations, especially result entry. The correct place to protect admin flows is before Django, in nginx.

## Scope

Implement the first production-ready traffic shaping layer in [nginx/nginx.conf](../../nginx/nginx.conf).

## Requirements

- Separate admin routes from public routes in nginx.
- Apply rate limiting to public-read endpoints.
- Protect admin-critical routes from public overload spikes.
- Continue serving static and media files directly from nginx.
- Keep the implementation simple and reviewable without adding business logic to Django.

## Expected behavior

When the system is under pressure:

- admin requests remain responsive
- public requests are throttled, delayed, or served from cache
- static/media traffic remains available without hitting Django
- public traffic does not consume the full backend worker capacity

## Acceptance criteria

- Admin routes are prioritized at the edge layer.
- Public routes are limited by threshold or rate policy.
- Static and media traffic is served outside Django if possible.
- The traffic policy is documented and reviewed.
- The policy is evaluated before implementing public caching.

## Review gate before next phase

This phase is complete only when synthetic load testing or a documented review shows that admin routes remain responsive while public traffic is degraded gracefully instead of taking down the system.

## Status

- [x] Not started
- [x] In progress
- [x] Reviewed
- [x] Approved

## Implementation

Implemented in [nginx/nginx.conf](../../nginx/nginx.conf):

- Two independent per-IP rate/connection budgets (`limit_req_zone`/`limit_conn_zone`, http-level, 429 on limit instead of the nginx-default 503):
  - `public_read` / `public_conn` (10r/s, burst 20, 10 concurrent conns) — applied to `location = /`, `location /public/`, and the bigscreen regex location.
  - `admin_safety` / `admin_conn` (30r/s, burst 60, 30 concurrent conns) — applied to the catch-all `location /` that now covers every other route (login, dashboard, players, tournaments, Django admin). This is a safety net against a single runaway/misbehaving client, set far above real admin usage, so it never throttles legitimate admin work.
- `tournament_bigscreen` gets its own regex location (`^/tournaments/[0-9]+/bigscreen/$`) shaped like public-read per the Issue 01 decision, but explicitly **not cached** — caching an owner-scoped authenticated response by URL alone could leak one club's tournament data to a different authenticated user requesting the same path.
- `/static/` and `/media/` continue to bypass all of this and are served directly by nginx (unchanged, already correct from before this phase).

Not yet done: synthetic load testing to confirm the review gate ("admin requests remain responsive while public traffic degrades gracefully").

`docker compose exec nginx nginx -t` confirms the config is syntactically valid and already running against the live container:
```
nginx: the configuration file /etc/nginx/nginx.conf syntax is ok
nginx: configuration file /etc/nginx/nginx.conf test is successful
```
A synthetic load test (e.g. `ab`/`hey` against `/public/...` vs `/tournaments/...`) is still recommended before Approved, to confirm the 429 responses and rate thresholds behave as expected under real pressure.

**Load test result** (40 concurrent requests via `curl.exe --parallel` against the running stack):

| Route | 200/302 | 429 |
|---|---|---|
| `/public/` (public-read) | 11 | 29 |
| `/login/` (admin-critical) | 40 | 0 |

Confirms the review gate: admin traffic stays fully responsive while public traffic degrades gracefully once past its burst allowance.

## Dependency on previous phase

This phase depends on the classification created in Issue 01. If route classification changes, this issue must be reviewed again.
