# Issue 01: Route classification and review

## Goal

Create a clear and reviewed classification of all application routes so that admin-critical traffic is separated from public read traffic, static/media traffic, and heavy-compute paths.

## Why this matters

The system currently has a single Django backend behind nginx. If all requests compete equally for the same worker pool, public traffic can overload the system and delay or block admin work. The first step is to get a correct map of what is actually critical to the tournament administration workflow.

## Scope

Review and classify all routes in:

- [tournament_planner/urls.py](../../tournament_planner/urls.py)
- [tournaments/urls.py](../../tournaments/urls.py)
- [players/urls.py](../../players/urls.py)

Classify each route into one of the following groups:

- admin-critical
- public-read
- static/media
- heavy-compute

## Required classification examples

Admin-critical should include:

- login/logout
- dashboard views
- tournament create/edit/delete
- division create/edit/delete
- match result entry
- schedule generation and administration
- bracket/legal updates
- any write operations

Public-read should include:

- public tournament overview
- public schedule
- standings
- public result pages
- spectator access views

Static/media should include:

- `/static/`
- `/media/`
- uploaded logos and print assets

## Acceptance criteria

- All routes are accounted for in a reviewable classification list.
- Admin routes are clearly separated from public route access.
- Result entry and schedule administration are defined as admin-critical.
- Public viewing is explicitly treated as non-critical read traffic.
- The classification is reviewed before moving to traffic shaping.

## Output expected

A short classification document or checklist with:

- route name
- route path
- route group
- reason for classification
- owner/reviewer notes

**Produced:** [docs/route-classification.md](../route-classification.md)

## Review gate before next phase

This phase is complete only when all routes are reviewed and agreed. If a route is ambiguous, it must be explicitly discussed before moving to nginx traffic shaping.

## Status

- [x] Not started
- [x] In progress
- [x] Reviewed
- [ ] Approved

## Notes

This phase is intentionally lightweight and should be treated as a decision-making checkpoint rather than a technical implementation sprint. It defines the rules for all following phases.

All routes in `tournament_planner/urls.py`, `tournaments/urls.py` and `players/urls.py` have been classified in [docs/route-classification.md](../route-classification.md).

Confirmed decision: the heavy-compute routes (`tournament_generate_time_schedule`, `division_generate_schedule`, `schedule_suggestions`) are planning-stage only and never run concurrently with live tournament execution, so they need no prioritization or isolation — see the resolved decision in [docs/issues/04-heavy-task-isolation.md](04-heavy-task-isolation.md).

Resolved: `tournament_bigscreen` is reclassified as **public-read (authenticated)** — it stays behind `@login_required` but is shaped/cached like public-read in Phase 2/3, since it never writes and auto-reloads every 60s ([bigscreen.html](../../tournaments/templates/tournaments/bigscreen.html)). See the note in [docs/route-classification.md](../route-classification.md).

Only `/i18n/setlang/` remains as a low-stakes note (shared admin/public route, cheap, classified public-read). No further discussion needed there before proceeding — mark this issue Reviewed/Approved and proceed to Issue 02.
