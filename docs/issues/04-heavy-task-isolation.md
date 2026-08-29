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

## Status

- [ ] Not started
- [ ] In progress
- [ ] Reviewed
- [ ] Approved

## Dependency on previous phases

This phase depends on the classification, shaping, and cache decisions already made in Issues 01–03.
