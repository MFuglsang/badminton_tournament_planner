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

- [ ] Not started
- [ ] In progress
- [ ] Reviewed
- [ ] Approved

## Dependency on previous phase

This phase depends on the classification created in Issue 01. If route classification changes, this issue must be reviewed again.
