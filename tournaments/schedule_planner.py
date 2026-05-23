"""
Time-slot scheduling for tournaments.

Assigns scheduled_time and court to each match using a greedy algorithm.

  Constraints honoured:
    * At most court_count matches run simultaneously.
    * A player's matches cannot overlap; consecutive matches must be
      separated by at least player_break_time minutes.
    * Playoff-phase matches cannot start before all group-phase matches
      in the same division have finished (+ one break period).
    * Bracket placeholder matches cannot start before both their feeder
      matches have finished (+ one break period).
    * Higher-priority divisions are scheduled before lower-priority ones.
"""

from datetime import datetime, timedelta
from django.utils import timezone

# Granularity of the time grid in minutes.
# All durations are rounded up to the nearest multiple of this value.
_SLOT_MINUTES = 5


def _to_slots(minutes):
    """Convert a duration in minutes to discrete time slots (ceiling division)."""
    return (int(minutes) + _SLOT_MINUTES - 1) // _SLOT_MINUTES


def generate_time_schedule(tournament):
    """
    Assign scheduled_time and court to all numbered matches in *tournament*.

    Requires tournament.start_time and tournament.date to be set.
    Returns the number of matches scheduled, or 0 if prerequisites are missing.
    """
    if not tournament.days.exists():
        return 0

    from .models import Match

    matches = list(
        Match.objects
        .filter(division__tournament=tournament)
        .exclude(match_number=None)
        .exclude(walkover=True)  # exclude auto-bye matches (team1=X, team2=None, walkover=True)
        .order_by('division__schedule_priority', 'match_round', 'division', 'match_number')
        .select_related('division', 'team1__player1', 'team1__player2',
                        'team2__player1', 'team2__player2')
    )
    if not matches:
        return 0

    return _schedule_greedy(tournament, matches)


# ---------------------------------------------------------------------------
# Greedy scheduler
# ---------------------------------------------------------------------------

def _schedule_greedy(tournament, matches):
    """
    Greedy time-slot scheduler.
    Assigns each match the earliest available court slot that respects player
    break times, playoff barriers, and priority ordering.
    """
    first_day = tournament.days.order_by('date', 'start_time').first()
    naive_start = datetime.combine(first_day.date, first_day.start_time)
    start_dt = timezone.make_aware(naive_start) if timezone.is_naive(naive_start) else naive_start
    court_count = first_day.court_count

    court_free = [start_dt] * court_count
    player_free = {}
    bracket_slot_end = {}
    playoff_group_end = {}
    break_td = timedelta(minutes=tournament.player_break_time)

    # Priority ordering: track the minimum end time of each priority group
    # so that the next (lower) priority group cannot start before the first
    # match of the previous group has finished.
    current_priority_group = None
    current_group_ends = []
    priority_floor = start_dt

    updated = []
    for match in matches:
        # When priority group changes, update the floor for the new group
        p = match.division.schedule_priority
        if p != current_priority_group:
            if current_group_ends:
                priority_floor = max(priority_floor, min(current_group_ends))
            current_priority_group = p
            current_group_ends = []

        is_placeholder = (match.team1 is None)
        duration = (
            tournament.single_match_duration
            if match.division.discipline == 'single'
            else tournament.double_match_duration
        )

        if is_placeholder:
            r = match.match_round
            s = match.bracket_slot
            div_id = match.division_id
            feeder_end_1 = bracket_slot_end.get((div_id, r - 1, 2 * s - 1), start_dt)
            feeder_end_2 = bracket_slot_end.get((div_id, r - 1, 2 * s), start_dt)
            player_earliest = max(feeder_end_1, feeder_end_2) + break_td
        else:
            player_pks = [
                pk for pk in [
                    match.team1.player1_id,
                    getattr(match.team1, 'player2_id', None),
                    match.team2.player1_id if match.team2 else None,
                    getattr(match.team2, 'player2_id', None) if match.team2 else None,
                ]
                if pk
            ]
            if player_pks:
                player_earliest = max(
                    (player_free.get(pk, start_dt - break_td) + break_td for pk in player_pks)
                )
            else:
                player_earliest = start_dt

        if getattr(match, 'phase', 'group') == 'playoff':
            group_done = playoff_group_end.get(match.division_id, start_dt)
            player_earliest = max(player_earliest, group_done + break_td)

        # Enforce priority floor: lower-priority matches wait for the first
        # match of all higher-priority groups to have finished.
        player_earliest = max(player_earliest, priority_floor)

        best_time = None
        best_court_free = None
        best_court_idx = 0
        for idx, court_time in enumerate(court_free):
            slot = max(court_time, player_earliest)
            if (
                best_time is None
                or slot < best_time
                or (slot == best_time and court_time > best_court_free)
            ):
                best_time = slot
                best_court_free = court_time
                best_court_idx = idx

        match.scheduled_time = best_time
        match.court = str(best_court_idx + 1)
        updated.append(match)

        end_time = best_time + timedelta(minutes=duration)
        court_free[best_court_idx] = end_time

        if not is_placeholder:
            for pk in player_pks:
                player_free[pk] = end_time

        if getattr(match, 'phase', 'group') == 'group':
            prev = playoff_group_end.get(match.division_id, start_dt)
            if end_time > prev:
                playoff_group_end[match.division_id] = end_time

        if match.bracket_slot is not None:
            bracket_slot_end[(match.division_id, match.match_round, match.bracket_slot)] = end_time

        current_group_ends.append(end_time)

    for m in updated:
        m.save(update_fields=['scheduled_time', 'court'])

    return len(updated)
