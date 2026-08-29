# Route Classification (Issue 01)

## Goal

This document is the reviewable output of Issue 01: a classification of every
route served by the application into one of four traffic groups, so that a
later phase can shape nginx/worker traffic without guessing which paths are
critical to the tournament-administration workflow.

## Groups

| Group | Meaning |
|-------|---------|
| **admin-critical** | Authenticated, write-capable or operational paths that tournament organizers rely on during a live event (result entry, schedule generation/admin, dashboard, auth). Must never be starved or rate-limited by public traffic. |
| **public-read** | Anonymous, read-only pages for spectators/players (public overview, schedule, results). High volume, safe to throttle/cache separately from admin traffic. |
| **static/media** | Files served directly (or servable) by nginx: CSS/JS/images, and uploaded media (logos, print assets). No Django worker involvement beyond initial serving config. |
| **heavy-compute** | Routes that do non-trivial CPU/IO work per request (schedule generation algorithms, PDF/print rendering, bulk import/export). Candidates for stricter concurrency limits/timeouts regardless of who calls them. |

## `tournament_planner/urls.py`

| Route name | Path | Group | Reason | Owner/reviewer notes |
|---|---|---|---|---|
| `service_worker` | `/sw.js` | static/media | PWA service worker file, served like a static asset. | |
| `home` (public landing) | `/` | public-read | Anonymous landing page. | |
| `admin_home` | `/dashboard/` | admin-critical | Authenticated organizer dashboard (`@login_required`), entry point to admin workflow. | |
| `login` | `/login/` | admin-critical | Auth endpoint; must stay responsive even under public load. | |
| `logout` | `/logout/` | admin-critical | Auth endpoint. | |
| Django admin site | `/<ADMIN_URL>/` (default `/admin/`) | admin-critical | Full Django admin, write-capable, staff-only. | |
| `players/*` | `/players/` | see `players/urls.py` | Delegated. | |
| `tournaments/*` | `/tournaments/` | see `tournaments/urls.py` | Delegated. | |
| `public_landing` | `/public/` | public-read | Explicit public/anonymous viewer entry point. | |
| `public_tournament` | `/public/tournament/<pk>/` | public-read | Public tournament overview for spectators. | |
| `public_schedule` | `/public/tournament/<pk>/spilleplan/` | public-read | Public schedule/spectator view. | |
| Media files | `/media/...` (via `static()` helper) | static/media | Uploaded logos and print assets served from `MEDIA_ROOT`; nginx already serves `/media/` directly (see `nginx/nginx.conf`). | |
| `i18n` | `/i18n/` | admin-critical | Only used by the language-switch form on authenticated/admin pages today; low traffic, treat as admin-critical rather than public to keep it out of the public-throttled path. | Confirm during review if also used on public pages. |

## `tournaments/urls.py` (mounted at `/tournaments/`)

| Route name | Path | Group | Reason | Owner/reviewer notes |
|---|---|---|---|---|
| `tournament_list` | `/` | admin-critical | Organizer's own tournament list (owner-scoped), requires login. | |
| `tournament_create` | `create/` | admin-critical | Write operation. | |
| `tournament_detail` | `<pk>/` | admin-critical | Organizer detail/management view. | |
| `tournament_edit` | `<pk>/edit/` | admin-critical | Write operation. | |
| `tournament_delete` | `<pk>/delete/` | admin-critical | Write operation. | |
| `tournament_export` | `<pk>/export/` | heavy-compute | Serializes full tournament data to a file; admin-only but CPU/IO heavy. | Also admin-critical from an access-control standpoint; classify primarily by cost. |
| `tournament_import` | `import/` | heavy-compute | Bulk parse/create of tournament data from an uploaded file. | |
| `division_create` | `<tournament_pk>/division/create/` | admin-critical | Write operation. | |
| `division_update_teams` | `division/<pk>/teams/` | admin-critical | Write operation. | |
| `division_update_seeds` | `division/<pk>/seeds/` | admin-critical | Write operation. | |
| `division_update_days` | `division/<pk>/days/` | admin-critical | Write operation. | |
| `division_delete` | `division/<pk>/delete/` | admin-critical | Write operation. | |
| `division_set_priority` | `division/<pk>/priority/` | admin-critical | Write operation. | |
| `division_generate_schedule` | `division/<pk>/generate/` | heavy-compute | Runs the scheduling algorithm (round-robin/bracket generation); also admin-only. | Explicitly required by issue: "schedule generation ... admin-critical" — treat as both; give it admin-tier priority AND heavy-compute resource limits. |
| `division_reassign_groups` | `division/<pk>/reassign-groups/` | admin-critical | Write operation. | |
| `match_record_result` | `match/<pk>/result/` | admin-critical | Explicitly called out in the issue as admin-critical (result entry). | |
| `match_start` | `match/<pk>/start/` | admin-critical | Write operation, live match control. | |
| `match_postpone` | `match/<pk>/postpone/` | admin-critical | Write operation. | |
| `match_walkover` | `match/<pk>/walkover/` | admin-critical | Write operation. | |
| `match_bracket_override` | `match/<pk>/bracket-override/` | admin-critical | Explicitly called out in the issue ("bracket/legal updates"). | |
| `tournament_scoresheet` | `<pk>/scoresheet/` | heavy-compute | Generates a printable scoresheet document for a whole tournament. | Admin-only access. |
| `tournament_wallchart` | `<pk>/wallchart/` | heavy-compute | Renders full bracket wallchart for printing. | Admin-only access. |
| `tournament_court_signs` | `<pk>/court-signs/` | heavy-compute | Generates printable court signage for all courts. | Admin-only access. |
| `tournament_program_print` | `<pk>/program/print/` | heavy-compute | Full-program print rendering. | Admin-only access. |
| `division_scoresheet` | `division/<pk>/scoresheet/` | heavy-compute | Per-division printable scoresheet generation. | Admin-only access. |
| `division_medals` | `division/<pk>/medals/` | admin-critical | Organizer medal ceremony view. | |
| `division_medals_edit` | `division/<pk>/medals/edit/` | admin-critical | Write operation. | |
| `division_medals_reset` | `division/<pk>/medals/reset/` | admin-critical | Write operation. | |
| `tournament_schedule` | `<pk>/schedule/` | admin-critical | Organizer schedule administration view (not the public one). | |
| `tournament_schedule_print` | `<pk>/schedule/print/` | heavy-compute | Print rendering of the full schedule. | Admin-only access. |
| `tournament_generate_time_schedule` | `<pk>/schedule/generate/` | heavy-compute | Time-schedule generation algorithm; explicitly admin-critical per issue as well. | Same dual classification as `division_generate_schedule`. |
| `tournament_toggle_lock` | `<pk>/schedule/lock/` | admin-critical | Write operation, schedule administration. | |
| `tournament_reset_schedule` | `<pk>/schedule/reset/` | admin-critical | Write operation, schedule administration. | |
| `schedule_editor` | `<pk>/schedule/editor/` | admin-critical | Interactive schedule administration UI. | |
| `schedule_suggestions` | `<pk>/schedule/suggestions/` | heavy-compute | Computes scheduling suggestions on demand. | Also admin-critical by access; dual classification. |
| `schedule_assign` | `<pk>/schedule/assign/` | admin-critical | Write operation, schedule administration. | |
| `schedule_unassign` | `<pk>/schedule/unassign/` | admin-critical | Write operation, schedule administration. | |
| `schedule_clear` | `<pk>/schedule/clear/` | admin-critical | Write operation, schedule administration. | |
| `tournament_renumber_matches` | `<pk>/renumber/` | admin-critical | Write operation. | |
| `tournament_renumber_by_schedule` | `<pk>/renumber-by-schedule/` | admin-critical | Write operation. | |
| `tournament_rebuild_playoff_labels` | `<pk>/rebuild-playoff-labels/` | admin-critical | Write/recompute operation, admin-only. | |
| `tournament_bigscreen` | `<pk>/bigscreen/` | public-read | Spectator-facing "big screen" display, no auth required for viewing at the venue. | Confirm auth requirement during review — if it requires login, reclassify as admin-critical. |
| `tournament_run` | `<pk>/run/` | admin-critical | Live event "run" control view for organizers. | |

## `players/urls.py` (mounted at `/players/`)

| Route name | Path | Group | Reason | Owner/reviewer notes |
|---|---|---|---|---|
| `player_list` | `/` | admin-critical | Organizer-only player management list. | |
| `player_add` | `add/` | admin-critical | Write operation. | |
| `player_template_download` | `template/download/` | static/media | Serves a static import-template file for download. | |
| `player_upload` | `upload/` | heavy-compute | Bulk parse/create of players from an uploaded file. | |
| `player_edit` | `<pk>/edit/` | admin-critical | Write operation. | |
| `player_delete` | `<pk>/delete/` | admin-critical | Write operation. | |
| `player_bulk_delete` | `bulk-delete/` | admin-critical | Write operation. | |
| `player_schedule_print` | `<pk>/schedule/` | heavy-compute | Per-player printable schedule rendering. | Admin-only access. |
| `player_clear_rest` | `<pk>/clear-rest/` | admin-critical | Write operation. | |
| `team_list` | `teams/` | admin-critical | Organizer-only team management list. | |
| `team_add` | `teams/add/` | admin-critical | Write operation. | |
| `team_edit` | `teams/<pk>/edit/` | admin-critical | Write operation. | |
| `team_delete` | `teams/<pk>/delete/` | admin-critical | Write operation. | |
| `division_category_list` | `categories/` | admin-critical | Organizer-only category management. | |
| `division_category_delete` | `categories/<pk>/delete/` | admin-critical | Write operation. | |
| `division_category_seed_defaults` | `categories/seed-defaults/` | admin-critical | Write operation. | |

## Static/media locations already handled at the nginx layer

These are not Django `urlpatterns` entries but are served directly by nginx
(`nginx/nginx.conf`) and are included here for completeness of the
classification:

| Path | Group | Reason |
|---|---|---|
| `/static/` | static/media | Served via `alias /static/;` with long cache lifetime. |
| `/media/` | static/media | Served via `alias /media/;`, includes uploaded logos and print assets; forced download + strict CSP as defence-in-depth. |

## Ambiguous routes flagged for discussion

- `i18n/` — currently defaults to admin-critical bucket; confirm it is not
  exercised from public-facing pages before final sign-off.
- `tournament_bigscreen` — classified as public-read (venue display), but
  should be confirmed against its actual `login_required`/permission checks.
- Routes with dual admin-critical/heavy-compute nature (`division_generate_schedule`,
  `tournament_generate_time_schedule`, `schedule_suggestions`, and all
  print/export/scoresheet/wallchart routes): these are admin-only by access
  control but expensive by CPU/IO cost. For traffic shaping they should be
  treated as **admin-critical priority** with **heavy-compute resource limits**
  (e.g. separate worker pool/timeout, not a lower priority queue).

## Status

- [x] Not started
- [x] In progress
- [x] Reviewed
- [ ] Approved

This classification is the required input for the next phase (nginx traffic
shaping) and should not be changed without updating the traffic-shaping rules
that depend on it.
