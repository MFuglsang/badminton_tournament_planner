# Issue 05: Production monitoring and tuning

## Goal

Verify in real operating conditions that admin traffic stays prioritized and public traffic degrades gracefully without threatening the platform.

## Why this matters

A traffic policy is only useful if it is observed and tuned. Without monitoring, we cannot know whether admin operations are still protected when public traffic spikes.

## Scope

Add production observability and tuning based on measured load.

## Requirements

- Measure latency by route family.
- Measure 5xx rate and saturation.
- Measure admin vs public traffic split.
- Measure cache hit rates for public pages.
- Tune rate limits and thresholds based on actual data.

## Acceptance criteria

- Admin latency remains acceptable under public load.
- Public traffic is throttled or cached before it overwhelms Django.
- Metrics exist for the critical traffic categories.
- Review gate confirms the live system behaves as intended.

## Review gate before final handoff

This phase is complete only when the key operational metrics are being monitored and there is evidence that the configured policies protect admin work during load spikes.

## Status

- [ ] Not started
- [ ] In progress
- [ ] Reviewed
- [ ] Approved

## Dependency on previous phases

This phase depends on the earlier routing, shaping, caching, and heavy-task design decisions.
