# NGINX Traffic Shaping (Issue 02)

## Goal

This document describes the traffic-shaping layer implemented in
`nginx/nginx.conf` as the output of Issue 02.  It depends on the route
classification produced in Issue 01 (`docs/route_classification.md`).

## Design principles

1. **Admin operations must never be starved by public traffic.**  The
   tournament organiser's ability to enter results, control matches, and
   manage the schedule is more important than spectator read throughput.
2. **Rate limiting happens at the edge (nginx), not in Django.**  This
   protects Django worker capacity before a request ever reaches the
   application layer.
3. **Static and media files are served entirely by nginx**, bypassing Django
   workers.
4. **Heavy-compute admin routes get a dedicated zone** so a burst of
   expensive jobs (PDF rendering, schedule generation) cannot consume all
   worker capacity for lighter admin write operations.

## Rate-limit zones

| Zone | Shared memory | Rate | Applies to |
|------|--------------|------|------------|
| `public_read` | 10 MB | 30 r/min per IP | Anonymous / spectator read endpoints |
| `heavy_compute` | 10 MB | 5 r/min per IP | CPU/IO-intensive admin endpoints |

Both zones use `burst=10` / `burst=3` with `nodelay` respectively, so short
spikes are absorbed without artificial queueing delay, but sustained overload
is rejected with **HTTP 429 Too Many Requests** (more specific than 503).

Admin-critical routes (`/dashboard/`, `/login/`, `/logout/`, `/tournaments/`,
`/players/`, `/admin/`, etc.) fall through to the catch-all `location /` block
which carries **no rate limit**, ensuring organiser requests are never throttled
regardless of public load.

## Location block priority (top-to-bottom)

1. `/static/` — served from disk, long-lived cache, no Django.
2. `/media/` — served from disk, forced download, strict CSP, no Django.
3. `= /` (exact home) — `public_read` zone.
4. `^~ /public/` — `public_read` zone.
5. `~ bigscreen` — `public_read` zone (spectator display at venue).
6. `~ heavy-compute tournament routes` — `heavy_compute` zone (export, print,
   schedule generation, scoresheet/wallchart, etc.).
7. `~ heavy-compute player routes` — `heavy_compute` zone (upload, per-player
   print schedule).
8. `location /` (catch-all) — **no rate limit** — admin-critical and all other
   authenticated routes.

Nginx evaluates location blocks in prefix/exact → regex order, so more-specific
blocks above win over the catch-all below.

## Proxy timeouts

| Route group | `proxy_read_timeout` | Reason |
|-------------|----------------------|--------|
| Admin-critical catch-all | 120 s | Standard; admin views are fast. |
| Public-read | 120 s | Read views are fast; timeout still prevents hung workers. |
| Heavy-compute | 300 s | Schedule generation / PDF rendering can legitimately take longer. |

## Accepted trade-offs

- Public-read routes are throttled at **30 r/min per IP**.  Legitimate
  spectators on the same NAT (e.g. venue WiFi sharing one public IP) may see
  429s under heavy simultaneous load.  This is an acceptable trade-off given
  the tournament context; a future phase can add a cache layer (e.g.
  `proxy_cache`) to reduce back-end load for public pages instead.
- The `heavy_compute` zone applies to admin IPs too (they are single organiser
  machines so 5 r/min is not a practical constraint).
- `limit_req_status 429` is set globally so all zones return the same status.

## Relation to route classification

All route groups described in `docs/route_classification.md` are covered:

| Classification | nginx treatment |
|----------------|----------------|
| static/media | Served from disk, no Django involvement. |
| public-read | `public_read` zone (30 r/min, burst 10). |
| heavy-compute | `heavy_compute` zone (5 r/min, burst 3, 300 s timeout). |
| admin-critical | No rate limit; falls through to catch-all `location /`. |

## Review gate

This phase is considered complete when:

- [x] nginx.conf contains separate location blocks for each route group.
- [x] public-read endpoints are rate-limited.
- [x] admin-critical routes are not rate-limited.
- [x] static/media is served outside Django.
- [x] traffic policy is documented and reviewable.
- [ ] Synthetic load test or documented review confirms admin routes remain
      responsive while public traffic is throttled under load.

## Status

- [x] Not started
- [x] In progress
- [ ] Reviewed
- [ ] Approved
