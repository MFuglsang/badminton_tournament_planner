# Design plan: admin-first request prioritization

## Summary

This project is a Django-based tournament management system with a public spectator flow and an authenticated admin/club-management flow. The right way to prioritize requests is not to add custom priority logic inside Django views, but to enforce traffic shaping in the edge layer (reverse proxy / load balancer / ingress) and to protect the public read path from overloading the admin path.

Important clarification for this project: tournament planning and generation are not done while the tournament is actively running. In practice, the realistic concurrency is administrative result entry and live public viewing at the same time, not simultaneous live planning while matches are being played. That means we do not need a full “all operations at once” scheduling model. We only need to ensure that writable admin flows are protected from public read traffic and that public spectators cannot overload the system.

The goal is:

- admin work always gets first access to capacity
- public viewing pages degrade gracefully under load
- public players and spectators cannot bring the whole system down
- heavy operations are not run synchronously in request threads when they can be deferred

---

## Current architecture and why this matters

The current architecture is a classic single-backend Django deployment behind nginx:

- nginx proxies all traffic to the Django `web` container in [nginx/nginx.conf](nginx/nginx.conf)
- authenticated and public routes are defined in [tournament_planner/urls.py](tournament_planner/urls.py)
- public read-only views are handled in [tournaments/public_views.py](tournaments/public_views.py)
- admin/editing and tournament logic live in [tournaments/views.py](tournaments/views.py)
- scheduling logic is in [tournaments/scheduler.py](tournaments/scheduler.py) and [tournaments/schedule_planner.py](tournaments/schedule_planner.py)

This means all traffic competes for the same Django workers unless something explicitly separates it. The correct place to prioritize is therefore not in the business logic but in the request pipeline before Django.

---

## Desired behavior

The result we want is:

1. When the system is under pressure, admin requests remain responsive.
2. Public result pages and schedule views are slower or served from cache, but do not block critical admin actions.
3. Public traffic is rate-limited and cache-friendly.
4. Heavy tournament generation/scheduling calculations are not performed in the live request path unless strictly necessary.

For this project, the main live scenario is: admin enters results while players/spectators read public results and schedules. We do not need to support a scenario where the tournament is being re-planned in the same moment as public pages are being served. This keeps the design simpler and more realistic.

This gives the desired behavior: admin first, public second, system remains available.

---

## Traffic classification

### A. Admin-critical traffic

These should be treated as high-priority and protected from public overload.

Typical examples:

- login and logout
- dashboard and club administration
- tournament create/edit/delete
- division create/edit/delete
- match result input
- schedule generation
- match locking/unlocking
- bracket or medal updates
- any non-public write operation

### B. Public read traffic

These should be treated as lower-priority and degradable.

Typical examples:

- public landing pages
- public tournament pages
- public schedule pages
- standings views
- public results pages
- competition pages for spectators

### C. Static and media traffic

These should be bypassed as much as possible:

- `/static/`
- `/media/`
- uploaded logos and other media files

This traffic should be served by nginx directly and browser-cached.

---

## Recommended solution

## Option 1: NGINX prioritization and rate limiting (recommended baseline)

This is the simplest and best fit for the current deployment model.

### Principles

- NGINX inspects the request path and applies different rules
- routes considered admin-critical are allowed through with high priority
- public routes are rate-limited and/or delayed under pressure
- public pages are cached where possible

### Example behavior

- `/login/`, `/dashboard/`, `/tournaments/`, `/players/` → high priority
- `/public/`, `/public/tournament/.../`, `/public/tournament/.../spilleplan/` → degraded under pressure
- `/static/`, `/media/` → served with caching and minimal app load

### Why this is the best fit

- matches the current single-Django-backend design
- easy to implement without altering business logic
- avoids making Django itself responsible for request scheduling
- keeps the app behavior predictable and easy to reason about

---

## Option 2: Separate admin and public upstreams

If traffic grows or you have a dedicated production environment, a stronger version is:

- one upstream for admin traffic
- one upstream for public traffic
- NGINX routes requests based on path and maybe authenticated state

This creates explicit separation of capacity:

- admin workers are reserved for admin work
- public workers are limited and can degrade without affecting admin

### Benefits

- more explicit and robust than a single pool
- easier to monitor and reason about
- easier to scale independently

### Tradeoff

- more infrastructure complexity
- needs proper monitoring and health checks

---

## Caching strategy for public pages

Public pages are ideal candidates for caching because they are mostly read-only and likely to be requested repeatedly by spectators and players.

### Recommended cache targets

- public landing pages
- public tournament overview
- public schedule
- standings pages
- result pages

### Recommended policy

- cache duration: 30–300 seconds depending on type and freshness requirement
- if a tournament is edited or a result is entered, invalidate or refresh the affected cache
- do not cache authenticated admin pages

### Important note

Public caching should not be implemented by simply caching entire HTML pages forever. It should be designed around freshness and invalidation when tournament data changes.

---

## Heavy tasks should not block admin work

The project contains scheduling and computation-heavy logic in:

- [tournaments/scheduler.py](tournaments/scheduler.py)
- [tournaments/schedule_planner.py](tournaments/schedule_planner.py)
- [tournaments/views.py](tournaments/views.py)

These operations can become expensive during tournament generation and schedule updates.

### Recommended pattern

- if scheduling is heavy, generate in a background job or queued task
- return a quick “accepted / working” response to the user
- let admin poll or refresh when complete

This prevents a very large schedule calculation from squeezing out all other requests.

---

## Operational safeguards

### Rate limiting

Apply rate limits and burst limits for public routes to prevent spikes from overwhelming the app.

### Timeouts

At edge level, public traffic can have shorter timeouts than admin traffic.

### Keepalive and worker limits

Limit the number of concurrent public requests and set a higher ceiling for admin traffic if using separate upstreams.

### Monitoring

Track at minimum:

- request latency by route family
- 5xx error rate
- queue/backlog metrics
- public vs admin traffic split
- cache hit ratio for public pages

---

## Decision summary

The correct design is:

- admin requests are protected and prioritized at the edge
- public requests are throttled and cache-friendly
- heavy compute is offloaded out of the request path when practical
- Django remains focused on domain logic, not request scheduling

This is the right approach for this codebase because the project already sits behind nginx and its public/admin separation is already evident in the URL structure.

---

## Phased implementation plan

This is intentionally implemented as a phased roadmap instead of a single all-at-once rollout. Each phase is reviewable and can be accepted independently before moving on.

### Phase 1: route classification and review

Goal: understand exactly which requests are admin-critical and which are public-read traffic.

Tasks:

- map all routes in [tournament_planner/urls.py](tournament_planner/urls.py) and [tournaments/urls.py](tournaments/urls.py)
- classify routes into:
  - admin-critical
  - public-read
  - static/media
  - heavy-compute
- review whether any routes are wrongly classified
- confirm that result entry and schedule administration are clearly treated as admin-critical

Review checkpoint:

- confirm that admin writes are identified and separate from public reads
- confirm that public pages are not considered critical operational paths

### Phase 2: nginx traffic shaping

Goal: ensure that admin requests are not starved by public traffic.

Tasks:

- add nginx rules for admin vs public path separation
- apply rate limiting to public read routes
- ensure static and media traffic is served directly and cached by nginx
- keep admin routes protected from overload spikes

Review checkpoint:

- under synthetic load, admin requests remain responsive while public requests become slower or are rejected gracefully
- no public read path consumes the full Django worker capacity

### Phase 3: public page caching

Goal: reduce read pressure on Django without compromising freshness.

Tasks:

- cache public tournament overview pages
- cache public schedule pages
- cache standings / result pages where appropriate
- implement invalidation when a result, score, or schedule changes
- ensure admin pages are never cached in the same way

Review checkpoint:

- public pages render from cache under load without a large increase in backend load
- result updates invalidate the correct public caches

### Phase 4: heavy-task isolation

Goal: keep expensive operations away from the request path when possible.

Tasks:

- identify heavy computations in [tournaments/scheduler.py](tournaments/scheduler.py) and [tournaments/schedule_planner.py](tournaments/schedule_planner.py)
- evaluate whether schedule generation or other large calculations can be deferred to background jobs
- if not possible, make the operation take a limited and explicit path with fallback behavior

Review checkpoint:

- no heavy work blocks admin result entry under normal load
- if heavy work is unavoidable, it is isolated and documented

### Phase 5: production monitoring and tuning

Goal: verify in operational conditions that the policy works.

Tasks:

- measure latency by route family
- measure 5xx rate and saturation
- observe admin vs public traffic split
- confirm cache hit rate and invalidation behavior
- tune rate limits and thresholds based on real traffic

Review checkpoint:

- admin latency remains acceptable under public load
- public traffic degrades gracefully without putting the system down

### Phase 6: final review and operational handoff

Goal: confirm system health before declaring production readiness.

Tasks:

- review all phases together
- confirm route classification is still valid
- confirm nginx and caching rules are documented
- confirm monitoring and operational playbook are in place

Review checkpoint:

- the system is performing as intended under realistic pressure
- admin work remains prioritized
- public traffic is bounded and does not threaten the platform

---

## Decision summary

The chosen approach is Option 1, but implemented in phases. This gives us the benefits of a clear, robust design without forcing a risky all-at-once deployment.

The important point is that we are not trying to solve a hypothetical case where live planning and public viewing happen at the exact same moment. The realistic pressure case in this app is:

- admin enters results
- public players/spectators read results and schedules
- public traffic must never be allowed to overwhelm admin work

That fits a phased rollout very well.

---

## Conclusion

Yes, it is absolutely possible to ensure admin traffic is prioritized and public traffic does not take down the system.

The recommended solution for this project is not a custom Django priority mechanism, but a reverse-proxy and operational design where:

- admin traffic is protected first,
- public traffic is degraded gracefully,
- public pages are cached,
- heavy tasks are isolated from the critical request path.

That gives the desired result: the system remains usable for the club admin even under heavy public load.
