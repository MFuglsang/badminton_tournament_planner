# Route classification (Issue 01 output)

Classification of every route in [tournament_planner/urls.py](../tournament_planner/urls.py), [tournaments/urls.py](../tournaments/urls.py) and [players/urls.py](../players/urls.py), plus the static/media locations already handled by nginx.

Groups: **admin-critical** (protected, first priority) · **public-read** (degradable) · **public-read (authenticated)** (degradable/cacheable like public-read, but still requires login) · **static/media** (bypass Django) · **heavy-compute** (candidate for isolation/deferral, phase 4).

## `tournament_planner/urls.py`

| Route | Name | Group | Reason |
|---|---|---|---|
| `/i18n/setlang/` | (django built-in) | public-read | No DB write, sets a cookie; used by both admin and anonymous visitors, cheap |
| `/sw.js` | `service_worker` | static/media | Static PWA asset, cacheable, no per-request DB work |
| `/` | `home` | public-read | Alias for the public landing page |
| `/dashboard/` | `admin_home` | admin-critical | Authenticated dashboard, entry point to admin work |
| `/login/` | `login` | admin-critical | Gateway to all admin/write functionality |
| `/logout/` | `logout` | admin-critical | Session termination for admin users |
| `/<ADMIN_URL>/...` | Django admin site | admin-critical | Full write access to all models |
| `/players/...` | included | see players table below | |
| `/tournaments/...` | included | see tournaments table below | |
| `/public/` | `public_landing` | public-read | Anonymous club/tournament picker |
| `/public/tournament/<pk>/` | `public_tournament` | public-read | Anonymous standings/results view |
| `/public/tournament/<pk>/spilleplan/` | `public_schedule` | public-read | Anonymous read-only schedule view |
| `/media/...` (dev `static()` helper) | — | static/media | In production this is served directly by nginx, not Django |

## `players/urls.py` (mounted at `/players/`)

All views require `@login_required` and are owner-filtered — entirely admin-critical.

| Route | Name | Group | Reason |
|---|---|---|---|
| `/players/` | `player_list` | admin-critical | Roster management |
| `/players/add/` | `player_add` | admin-critical | Write |
| `/players/template/download/` | `player_template_download` | admin-critical | Auth-only file download |
| `/players/upload/` | `player_upload` | admin-critical | Bulk write (Excel import) |
| `/players/<pk>/edit/` | `player_edit` | admin-critical | Write |
| `/players/<pk>/delete/` | `player_delete` | admin-critical | Write |
| `/players/bulk-delete/` | `player_bulk_delete` | admin-critical | Write |
| `/players/<pk>/schedule/` | `player_schedule_print` | admin-critical | Auth-only printout |
| `/players/<pk>/clear-rest/` | `player_clear_rest` | admin-critical | Write |
| `/players/teams/` | `team_list` | admin-critical | Roster management |
| `/players/teams/add/` | `team_add` | admin-critical | Write |
| `/players/teams/<pk>/edit/` | `team_edit` | admin-critical | Write |
| `/players/teams/<pk>/delete/` | `team_delete` | admin-critical | Write |
| `/players/categories/` | `division_category_list` | admin-critical | Config management |
| `/players/categories/<pk>/delete/` | `division_category_delete` | admin-critical | Write |
| `/players/categories/seed-defaults/` | `division_category_seed_defaults` | admin-critical | Write |

## `tournaments/urls.py` (mounted at `/tournaments/`)

All views require `@login_required` and are owner-filtered.

| Route | Name | Group | Reason |
|---|---|---|---|
| `/tournaments/` | `tournament_list` | admin-critical | Core admin listing |
| `/tournaments/create/` | `tournament_create` | admin-critical | Write |
| `/tournaments/<pk>/` | `tournament_detail` | admin-critical | Central admin page |
| `/tournaments/<pk>/edit/` | `tournament_edit` | admin-critical | Write |
| `/tournaments/<pk>/delete/` | `tournament_delete` | admin-critical | Write |
| `/tournaments/<pk>/export/` | `tournament_export` | admin-critical | Auth-only JSON export |
| `/tournaments/import/` | `tournament_import` | admin-critical | Write, recreates a tournament |
| `/tournaments/<pk>/division/create/` | `division_create` | admin-critical | Write |
| `/tournaments/division/<pk>/teams/` | `division_update_teams` | admin-critical | Write |
| `/tournaments/division/<pk>/seeds/` | `division_update_seeds` | admin-critical | Write |
| `/tournaments/division/<pk>/days/` | `division_update_days` | admin-critical | Write |
| `/tournaments/division/<pk>/delete/` | `division_delete` | admin-critical | Write |
| `/tournaments/division/<pk>/priority/` | `division_set_priority` | admin-critical | Write |
| `/tournaments/division/<pk>/generate/` | `division_generate_schedule` | **heavy-compute** | Calls `scheduler.generate_schedule` (round-robin/bracket/playoff generation) synchronously in the request; also a write |
| `/tournaments/division/<pk>/reassign-groups/` | `division_reassign_groups` | admin-critical | Write, bounded computation |
| `/tournaments/match/<pk>/result/` | `match_record_result` | admin-critical | **Highest priority** — core result entry |
| `/tournaments/match/<pk>/start/` | `match_start` | admin-critical | Write |
| `/tournaments/match/<pk>/postpone/` | `match_postpone` | admin-critical | Write |
| `/tournaments/match/<pk>/walkover/` | `match_walkover` | admin-critical | Write |
| `/tournaments/match/<pk>/bracket-override/` | `match_bracket_override` | admin-critical | Write |
| `/tournaments/<pk>/scoresheet/` | `tournament_scoresheet` | admin-critical | Auth-only printout |
| `/tournaments/<pk>/wallchart/` | `tournament_wallchart` | admin-critical | Auth-only printout |
| `/tournaments/<pk>/court-signs/` | `tournament_court_signs` | admin-critical | Auth-only printout |
| `/tournaments/<pk>/program/print/` | `tournament_program_print` | admin-critical | Auth-only printout |
| `/tournaments/division/<pk>/scoresheet/` | `division_scoresheet` | admin-critical | Auth-only printout |
| `/tournaments/division/<pk>/medals/` | `division_medals` | admin-critical | Read |
| `/tournaments/division/<pk>/medals/edit/` | `division_medals_edit` | admin-critical | Write |
| `/tournaments/division/<pk>/medals/reset/` | `division_medals_reset` | admin-critical | Write |
| `/tournaments/<pk>/schedule/` | `tournament_schedule` | admin-critical | Core admin page |
| `/tournaments/<pk>/schedule/print/` | `tournament_schedule_print` | admin-critical | Auth-only printout |
| `/tournaments/<pk>/schedule/generate/` | `tournament_generate_time_schedule` | **heavy-compute** | Runs the OR-Tools CP-SAT solver (`schedule_planner.py`) synchronously; the single most expensive request in the app |
| `/tournaments/<pk>/schedule/lock/` | `tournament_toggle_lock` | admin-critical | Write |
| `/tournaments/<pk>/schedule/reset/` | `tournament_reset_schedule` | admin-critical | Write |
| `/tournaments/<pk>/schedule/editor/` | `schedule_editor` | admin-critical | Core admin page |
| `/tournaments/<pk>/schedule/suggestions/` | `schedule_suggestions` | **heavy-compute** *(no isolation needed, see note)* | JSON endpoint polled repeatedly from the schedule editor UI; O(n²)-ish conflict scan over all matches per call |
| `/tournaments/<pk>/schedule/assign/` | `schedule_assign` | admin-critical | Write |
| `/tournaments/<pk>/schedule/unassign/` | `schedule_unassign` | admin-critical | Write |
| `/tournaments/<pk>/schedule/clear/` | `schedule_clear` | admin-critical | Write |
| `/tournaments/<pk>/renumber/` | `tournament_renumber_matches` | admin-critical | Write |
| `/tournaments/<pk>/renumber-by-schedule/` | `tournament_renumber_by_schedule` | admin-critical | Write |
| `/tournaments/<pk>/rebuild-playoff-labels/` | `tournament_rebuild_playoff_labels` | admin-critical | Write |
| `/tournaments/<pk>/bigscreen/` | `tournament_bigscreen` | **public-read (authenticated)** *(resolved, see note)* | Requires login, but the template does a full `location.reload()` every 60s ([bigscreen.html](../tournaments/templates/tournaments/bigscreen.html)) and performs no writes — a passive display left open all match day |
| `/tournaments/<pk>/run/` | `tournament_run` | admin-critical | Live operational console used during the tournament |

## Static/media (handled in nginx, not Django routing)

| Path | Group | Reason |
|---|---|---|
| `/static/` | static/media | Already served directly by nginx (`nginx/nginx.conf`), cached 30d |
| `/media/` | static/media | Already served directly by nginx, forced download for uploaded files |

## Note: heavy-compute routes do not need isolation/deferral

All three heavy-compute routes (`tournament_generate_time_schedule`, `division_generate_schedule`, `schedule_suggestions`) belong to the **planning** stage: a club builds divisions, generates the match programme and time schedule, and locks it — all *before* the tournament day. They are not invoked while the tournament is running and public/spectator traffic is live. Since planning and live execution never overlap in practice, these routes do not need background jobs, queuing, or edge-level protection. They can stay synchronous in the request path. This removes the need for most of Phase 4 (heavy-task isolation) — see the updated decision in [docs/issues/04-heavy-task-isolation.md](issues/04-heavy-task-isolation.md).

## Note: `tournament_bigscreen` is authenticated but shaped like public-read

Unlike every other route under `/tournaments/`, `tournament_bigscreen` never writes anything and is designed to be left open unattended on a venue screen — the page itself calls `location.reload()` every 60 seconds. Because it runs *during* live execution (unlike the heavy-compute planning routes above) and is polled automatically without a human driving it, it should not compete for the same priority budget as result entry and other admin writes.

**Decision:** in Phase 2/3, match `/tournaments/*/bigscreen/` as its own nginx location — apply the same rate-limiting/short-TTL-caching treatment as public-read routes (a ~30–45s cache is safe given the 60s client reload), while leaving `@login_required` on the Django side completely unchanged. This keeps the admin-critical bucket reserved for routes that actually need first access to capacity.

## Remaining note

- **`/i18n/setlang/`** — shared by both admin and public UI language switchers. Cheap enough that its classification doesn't matter much for shaping, but noting it as public-read so it isn't accidentally rate-limited alongside heavier admin writes.

## Summary

- **Admin-critical:** all of `players/*`, all of `tournaments/*` except `tournament_bigscreen` and the three heavy-compute routes below, `/dashboard/`, `/login/`, `/logout/`, the Django admin site.
- **Public-read:** `/`, `/public/`, `/public/tournament/<pk>/`, `/public/tournament/<pk>/spilleplan/`, `/i18n/setlang/`.
- **Public-read (authenticated):** `/tournaments/<pk>/bigscreen/` — kept behind login, but shaped/cached like public-read since it is a passive, auto-reloading, read-only display used during live execution.
- **Static/media:** `/static/`, `/media/`, `/sw.js`.
- **Heavy-compute (planning-time only, no isolation needed):** `tournament_generate_time_schedule` (OR-Tools solver — highest impact), `division_generate_schedule` (round-robin/bracket generation), `schedule_suggestions` (frequent conflict-scan polling). These never run concurrently with live tournament execution, so edge shaping and background-job work in later phases should focus on the write-heavy admin routes used *during* the event (result entry, match start/postpone/walkover) instead.

This matches the assumption in [docs/priority_design_plan.md](priority_design_plan.md): result entry and schedule administration are confirmed admin-critical, and public viewing is confirmed non-critical read traffic. It also confirms explicitly that planning-stage heavy compute does not need prioritization, because it is never concurrent with live event traffic.
