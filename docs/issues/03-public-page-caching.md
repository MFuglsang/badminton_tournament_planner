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

- [x] Not started
- [x] In progress
- [x] Reviewed
- [x] Approved

## Implementation

Implemented with Django's per-view cache (`@cache_page`), not nginx `proxy_cache`:

- [tournaments/public_views.py](../../tournaments/public_views.py): `public_landing` (20s TTL), `public_tournament` (10s TTL), `public_schedule` (10s TTL). TTLs were deliberately kept low (well under the 30–300s range in [docs/priority_design_plan.md](../priority_design_plan.md)) per explicit request — results and player status update continuously during play, so caching must not be aggressive.
- [tournament_planner/settings.py](../../tournament_planner/settings.py): explicit `CACHES` setting (`LocMemCache`), so the policy is documented rather than relying on Django's implicit default. Under the test runner it swaps to `DummyCache` (reusing the existing `_is_testing` detection) so the process-global cache can't leak stale responses between test methods.
- Admin routes are untouched — no caching was added anywhere outside the three anonymous public views, so admin pages always reflect current data.
- Why not nginx `proxy_cache`: `tournament_bigscreen` is authenticated and owner-scoped, so URL-keyed edge caching there would risk leaking one club's data to another authenticated user (see Issue 01/02 decision). Keeping caching inside Django, scoped to the three views that are genuinely public (no owner filter, anyone can view any tournament by pk), avoids that risk entirely.

## Known limitation (accepted, not fixed)

`_activate_club_language()` in `public_views.py` can set the response language from a per-tournament-owner profile setting or a visitor's language cookie, but `cache_page`'s key only varies on `Accept-Language` (added automatically by `LocaleMiddleware`), not on that cookie. A visitor who just switched language via the cookie switcher could see a cached response in the previous language for up to the TTL window (10–20s). This is cosmetic only (no data leakage, self-corrects within the TTL) and was judged not worth the cache-fragmentation cost of varying on cookies.

## Verification

`docker compose exec web python -m pytest tournaments/tests.py -q` → 299 passed, 1 skipped, confirming the cache changes don't break existing public-view tests (thanks to the test-only `DummyCache` override).

## Dependency on previous phases

This phase depends on successful route classification and nginx shaping in Issues 01 and 02.
