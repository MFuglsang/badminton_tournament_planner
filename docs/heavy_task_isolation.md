# Heavy Task Isolation (Issue 04)

## Decision

Heavy work is **isolated**, rather than deferred to a task queue.  Nginx sends
every route classified as `heavy-compute` in
[`route_classification.md`](route_classification.md) to the `heavy` Compose
service.  That service has one Gunicorn worker and a 300-second timeout.  The
ordinary `web` service retains two separate workers for result entry and all
other admin-critical and public requests.

This keeps a long schedule calculation from occupying the workers serving
`match_record_result`.  One heavy worker also serializes heavy requests within
the deployed application, avoiding concurrent schedule generation.  The
existing nginx limit permits five heavy requests per minute per client with a
burst of three; excess requests receive HTTP 429 rather than queuing.

## Heavy paths and handling

| Path | Cost | Decision |
| --- | --- | --- |
| `division_generate_schedule` / `scheduler.py` | Round-robin generation grows quadratically with entrants; bracket/playoff generation writes many rows. | Isolate in `heavy`; one worker, 300 s timeout, rate limit. |
| `tournament_generate_time_schedule` / `schedule_planner.py` | Loads all tournament matches and runs the greedy scheduling pass. | Isolate in `heavy`; one worker, 300 s timeout, rate limit. |
| `schedule_suggestions` | Compares scheduled and unscheduled matches and player/court intervals. | Isolate in `heavy`; one worker, 300 s timeout, rate limit. |
| Import/export and print views | Bulk parsing/serialization or complete-program rendering. | Isolate in `heavy`; one worker, 300 s timeout, rate limit. |

No task queue is introduced now: schedule generation changes matches in a
single request transaction and needs immediate success/error feedback.  Moving
it to a queue requires durable job state, tournament-level locking,
deduplication, status polling, retries, and an operator-visible failure flow.
Those requirements are not present today, so a queue would reduce reliability
more than the dedicated process does.

## Operational fallback and review

If a heavy request exceeds 300 seconds or the `heavy` worker is unavailable,
the request fails without consuming an ordinary `web` worker.  The organizer
should retry after reducing tournament size or use the manual schedule editor;
the nginx 429 response should be retried later, not immediately.  Do not
increase `GUNICORN_WORKERS` for `heavy` without confirming database capacity
and result-entry latency under load.

Before production approval, run a representative maximum-size schedule
generation while repeatedly submitting a valid `match_record_result` request.
Confirm that result submissions continue through `web`, and monitor heavy
request duration, 429 responses, Gunicorn timeouts, and result-entry latency.
If the 300-second bound is routinely exceeded, implement the queued-job design
above before raising the timeout.

## Status

- [x] Heavy paths identified
- [x] Isolation decisions documented
- [ ] Reviewed
- [ ] Approved
