# Issue 04: Heavy task isolation and load protection

## Goal

Ensure that expensive calculations and schedule-generation work do not block admin result entry or public responsiveness.

## Why this matters

The system contains large scheduling and calculation logic in:

- [tournaments/scheduler.py](../../tournaments/scheduler.py)
- [tournaments/schedule_planner.py](../../tournaments/schedule_planner.py)
- [tournaments/views.py](../../tournaments/views.py)

Heavy operations are not a daily problem when the tournament is not being built live, but they still need to be isolated so they do not become the bottleneck under pressure.

## Scope

Review and reduce the chance that heavy tasks interfere with normal request processing.

## Requirements

- Identify heavy computational paths.
- Determine whether schedule generation can be deferred or moved to background processing.
- Keep admin result entry responsive even when heavy work is active.
- Ensure a plan exists if a heavy task cannot be deferred.

## Acceptance criteria

- Heavy operations are identified and documented.
- A decision is made for each heavy path: defer, isolate, or keep in request flow with explicit limits.
- Result entry remains responsive even if heavy work is triggered.
- This design is reviewed before moving to production monitoring.

## Review gate before next phase

This phase is complete only when the operational plan for heavy tasks is agreed and documented, including fallback behavior if the work cannot be deferred.

## Decision

The heavy-compute routes identified in [docs/route-classification.md](../route-classification.md) — `tournament_generate_time_schedule` (OR-Tools solver), `division_generate_schedule`, and `schedule_suggestions` — all belong to the planning stage (building divisions, generating the match programme and time schedule, locking it) which happens *before* the tournament day. They are never invoked concurrently with live result entry or public spectator traffic on the event day itself.

Because planning and live execution do not overlap in practice, no background job queue, deferral, or edge-level isolation is required for these routes. They stay synchronous in the request path as-is. This phase is resolved by decision rather than by implementation.

## Status

- [x] Not started
- [x] In progress
- [x] Reviewed
- [x] Approved

## Dependency on previous phases

This phase depends on the classification, shaping, and cache decisions already made in Issues 01–03.
