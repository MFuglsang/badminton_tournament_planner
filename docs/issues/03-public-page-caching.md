# Issue 03: Public page caching and freshness policy

## Goal

Reduce backend pressure from repeated public read requests by caching public pages while preserving data freshness for tournament updates.

## Why this matters

Public traffic is read-heavy and often repeated by spectators, players, and viewers. Caching the public tournament and result pages reduces load on Django and helps admin operations remain responsive.

## Scope

Review and implement caching for those public pages that are safe to cache, especially:

- public landing pages
- public tournament overview pages
- public schedule pages
- standings pages
- public results view pages

## Requirements

- Cache public pages with a short, explicit TTL.
- Define invalidation rules when a result, score, or schedule changes.
- Ensure admin pages are never cached with the same policy.
- Keep cache freshness explicit and reviewable.

## Acceptance criteria

- Public pages are cached with a defined TTL.
- Cache invalidation is triggered when tournament data changes.
- Results and schedules remain fresh enough for spectators without becoming stale for long periods.
- Cached public pages reduce pressure on Django under read-heavy load.
- Admin pages remain uncached and always reflect current data.

## Review gate before next phase

This phase is complete only when cache behavior is reviewed with freshness and invalidation in mind, and the team agrees that public caching does not risk showing stale data longer than acceptable.

## Status

- [ ] Not started
- [ ] In progress
- [ ] Reviewed
- [ ] Approved

## Dependency on previous phases

This phase depends on successful route classification and nginx shaping in Issues 01 and 02.
