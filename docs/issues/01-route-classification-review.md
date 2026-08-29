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

## Review gate before next phase

This phase is complete only when all routes are reviewed and agreed. If a route is ambiguous, it must be explicitly discussed before moving to nginx traffic shaping.

## Status

- [ ] Not started
- [ ] In progress
- [ ] Reviewed
- [ ] Approved

## Notes

This phase is intentionally lightweight and should be treated as a decision-making checkpoint rather than a technical implementation sprint. It defines the rules for all following phases.
