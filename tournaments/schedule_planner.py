"""
Time-slot scheduling for tournaments.

Assigns scheduled_time and court to each match using a greedy algorithm:
  - Matches are processed in match_number order.
  - Each match is placed on the earliest available court.
  - A player's next match cannot start until their previous match has finished
    plus the tournament's player_break_time.
  - Bracket placeholder matches (where participants are still unknown) are
    scheduled based on when their feeder matches are estimated to finish.
"""

from datetime import datetime, timedelta
from django.utils import timezone


def generate_time_schedule(tournament):
    """
    Assign scheduled_time and court to all numbered matches in *tournament*.

    Requires tournament.start_time and tournament.date to be set.
    Returns the number of matches scheduled, or 0 if prerequisites are missing.
    """
    if not tournament.start_time:
        return 0

    from .models import Match

    # Include placeholder matches (team1=None) but exclude byes (team2=None, team1!=None)
    matches = list(
        Match.objects
        .filter(division__tournament=tournament)
        .exclude(match_number=None)
        .exclude(team1__isnull=False, team2__isnull=True)  # exclude byes
        .order_by('match_number')
        .select_related('division', 'team1__player1', 'team1__player2',
                        'team2__player1', 'team2__player2')
    )
    if not matches:
        return 0

    # Base start: combine tournament date + start time → timezone-aware datetime
    naive_start = datetime.combine(tournament.date, tournament.start_time)
    start_dt = timezone.make_aware(naive_start) if timezone.is_naive(naive_start) else naive_start

    # court_free[i] = earliest datetime court (i+1) is available
    court_free = [start_dt] * tournament.court_count

    # player_free[player_pk] = datetime when that player finishes their last match
    player_free = {}

    # bracket_slot_end[(division_pk, match_round, bracket_slot)] = estimated end time
    # Used so placeholder matches know their earliest possible start
    bracket_slot_end = {}

    break_td = timedelta(minutes=tournament.player_break_time)

    updated = []
    for match in matches:
        is_placeholder = (match.team1 is None)

        duration = (
            tournament.single_match_duration
            if match.division.discipline == 'single'
            else tournament.double_match_duration
        )

        if is_placeholder:
            # Determine earliest possible start from feeder matches
            r = match.match_round
            s = match.bracket_slot
            div_id = match.division_id
            feeder_end_1 = bracket_slot_end.get((div_id, r - 1, 2 * s - 1), start_dt)
            feeder_end_2 = bracket_slot_end.get((div_id, r - 1, 2 * s), start_dt)
            player_earliest = max(feeder_end_1, feeder_end_2) + break_td
        else:
            # Collect player PKs for both teams
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
                    (player_free.get(pk, start_dt) + break_td for pk in player_pks)
                )
            else:
                player_earliest = start_dt

        # Find court with the earliest slot that also satisfies player/feeder availability
        best_time = None
        best_court_idx = 0
        for idx, court_time in enumerate(court_free):
            slot = max(court_time, player_earliest)
            if best_time is None or slot < best_time:
                best_time = slot
                best_court_idx = idx

        match.scheduled_time = best_time
        match.court = str(best_court_idx + 1)
        updated.append(match)

        end_time = best_time + timedelta(minutes=duration)
        court_free[best_court_idx] = end_time

        if not is_placeholder:
            for pk in player_pks:
                player_free[pk] = end_time

        # Record this slot's end time for downstream bracket matches
        if match.bracket_slot is not None:
            bracket_slot_end[(match.division_id, match.match_round, match.bracket_slot)] = end_time

    for m in updated:
        m.save(update_fields=['scheduled_time', 'court'])

    return len(updated)
