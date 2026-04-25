"""
Time-slot scheduling for tournaments using Google OR-Tools CP-SAT.

Assigns scheduled_time and court to each match by solving a constraint
satisfaction / optimisation problem:

  Objective: minimise total tournament duration (makespan).

  Hard constraints:
    * At most court_count matches run simultaneously.
    * A player's matches cannot overlap; consecutive matches must be
      separated by at least player_break_time minutes.
    * Playoff-phase matches cannot start before all group-phase matches
      in the same division have finished (+ one break period).
    * Bracket placeholder matches cannot start before both their feeder
      matches have finished (+ one break period).

  Falls back to a greedy algorithm if OR-Tools is unavailable or the
  solver does not find a feasible solution within the time limit.
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
    if not tournament.start_time:
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

    try:
        from ortools.sat.python import cp_model  # noqa: F401 – verify import works
        return _schedule_ortools(tournament, matches)
    except Exception:
        # Fall back to greedy if OR-Tools is unavailable or the solve fails.
        return _schedule_greedy(tournament, matches)


# ---------------------------------------------------------------------------
# OR-Tools CP-SAT solver
# ---------------------------------------------------------------------------

def _schedule_ortools(tournament, matches):
    from ortools.sat.python import cp_model

    SLOT = _SLOT_MINUTES
    break_slots = _to_slots(tournament.player_break_time)
    n_courts = tournament.court_count

    # Generous upper bound: 16 hours in slots
    horizon = _to_slots(16 * 60)

    model = cp_model.CpModel()

    # ── Per-match variables ────────────────────────────────────────────────
    start_vars = {}   # match.id → IntVar (slot index)
    end_vars = {}     # match.id → IntVar (slot index)
    dur_slots = {}    # match.id → int (constant duration in slots)
    court_lits = {}   # match.id → list[BoolVar] (one per court, exactly-one)

    # Optional intervals grouped by court, for AddNoOverlap per court
    court_intervals = {c: [] for c in range(n_courts)}

    for m in matches:
        duration_min = (
            tournament.single_match_duration
            if m.division.discipline == 'single'
            else tournament.double_match_duration
        )
        d = _to_slots(duration_min)
        dur_slots[m.id] = d

        s = model.new_int_var(0, horizon - d, f's_{m.id}')
        e = model.new_int_var(d, horizon, f'e_{m.id}')
        model.add(e == s + d)
        start_vars[m.id] = s
        end_vars[m.id] = e

        # Boolean variable per court (exactly one will be true)
        lits = [model.new_bool_var(f'c_{m.id}_{c}') for c in range(n_courts)]
        model.add_exactly_one(lits)
        court_lits[m.id] = lits

        # Optional interval for each court
        for c, lit in enumerate(lits):
            opt_iv = model.new_optional_interval_var(s, d, e, lit, f'iv_{m.id}_{c}')
            court_intervals[c].append(opt_iv)

    # ── Court capacity: no two matches on the same court may overlap ───────
    for c in range(n_courts):
        model.add_no_overlap(court_intervals[c])

    # ── Player constraints ─────────────────────────────────────────────────
    # Build player → matches map
    player_to_matches = {}
    for m in matches:
        pks = [
            pk for pk in [
                m.team1.player1_id if m.team1 else None,
                m.team1.player2_id if m.team1 else None,
                m.team2.player1_id if m.team2 else None,
                m.team2.player2_id if m.team2 else None,
            ]
            if pk
        ]
        for pk in pks:
            player_to_matches.setdefault(pk, []).append(m)

    # For each player, create padded intervals (duration + break) and enforce
    # no-overlap so that consecutive matches are separated by at least break_slots.
    for pk, pmatches in player_to_matches.items():
        if len(pmatches) < 2:
            continue
        padded_ivs = []
        for m in pmatches:
            d = dur_slots[m.id]
            padded_d = d + break_slots
            s = start_vars[m.id]
            e_pad = model.new_int_var(padded_d, horizon + break_slots, f'ep_{m.id}_{pk}')
            model.add(e_pad == s + padded_d)
            iv = model.new_interval_var(s, padded_d, e_pad, f'piv_{m.id}_{pk}')
            padded_ivs.append(iv)
        model.add_no_overlap(padded_ivs)

    # ── Playoff barrier ────────────────────────────────────────────────────
    # Collect group-phase end variables per division
    div_group_ends = {}
    for m in matches:
        if getattr(m, 'phase', 'group') == 'group':
            div_group_ends.setdefault(m.division_id, []).append(end_vars[m.id])

    # Each playoff match must start after ALL group matches in its division + break
    for m in matches:
        if getattr(m, 'phase', 'group') == 'playoff' and m.division_id in div_group_ends:
            group_end_max = model.new_int_var(0, horizon, f'ge_{m.id}')
            model.add_max_equality(group_end_max, div_group_ends[m.division_id])
            model.add(start_vars[m.id] >= group_end_max + break_slots)

    # ── Bracket placeholder ordering ───────────────────────────────────────
    # Placeholder matches (team1=None) must start after both feeder matches end
    slot_to_match = {}
    for m in matches:
        if m.bracket_slot is not None:
            slot_to_match[(m.division_id, m.match_round, m.bracket_slot)] = m

    for m in matches:
        if m.team1 is None and m.bracket_slot is not None:
            r, s = m.match_round, m.bracket_slot
            for feeder in [
                slot_to_match.get((m.division_id, r - 1, 2 * s - 1)),
                slot_to_match.get((m.division_id, r - 1, 2 * s)),
            ]:
                if feeder and feeder.id in end_vars:
                    model.add(start_vars[m.id] >= end_vars[feeder.id] + break_slots)

    # ── Priority ordering (hard constraint) ─────────────────────────────
    # A match in a lower-priority division (higher schedule_priority number)
    # cannot start before the earliest-finishing match from any higher-priority
    # division has ended.  This prevents free courts being filled by
    # low-priority matches while the high-priority first wave is still running.
    priority_groups = {}
    for m in matches:
        priority_groups.setdefault(m.division.schedule_priority, []).append(m)
    sorted_priorities = sorted(priority_groups.keys())

    for i, p_low in enumerate(sorted_priorities[1:], 1):
        higher_end_vars = [
            end_vars[m.id]
            for q in sorted_priorities[:i]
            for m in priority_groups[q]
        ]
        if higher_end_vars:
            min_end_higher = model.new_int_var(0, horizon, f'min_end_higher_{p_low}')
            model.add_min_equality(min_end_higher, higher_end_vars)
            for m in priority_groups[p_low]:
                model.add(start_vars[m.id] >= min_end_higher)

    # ── Objective: minimise makespan + weighted division completion ────────
    # For each division, compute div_end = max(end_vars of its matches).
    # Weight scaling: priority=1 → weight=1000 (same order as makespan),
    # priority=10 → weight=10.  Without this, makespan at weight=1000 was
    # 100× stronger than div_end at weight=10, so the solver barely cared
    # when individual divisions finished — high-priority divisions spread
    # across the whole day.
    makespan = model.new_int_var(0, horizon, 'makespan')
    model.add_max_equality(makespan, list(end_vars.values()))

    div_end_vars = {}
    div_priority = {}
    for m in matches:
        div_priority[m.division_id] = m.division.schedule_priority
        div_end_vars.setdefault(m.division_id, []).append(end_vars[m.id])

    objective_terms = [1000 * makespan]
    for div_id, ends in div_end_vars.items():
        priority = div_priority[div_id]
        # priority=1 → weight=1000  (finish as early as total makespan matters)
        # priority=10 → weight=100  (still meaningful)
        weight = (11 - priority) * 100
        div_end = model.new_int_var(0, horizon, f'div_end_{div_id}')
        model.add_max_equality(div_end, ends)
        objective_terms.append(weight * div_end)

    # ── Compactness: priority-weighted early-start pull ────────────────────
    # Each match is penalised for starting late, proportional to its division
    # priority.  Priority-1 matches are pulled toward time 0 ten times harder
    # than priority-10 matches, clustering high-priority rounds at the front.
    for m in matches:
        compactness_weight = (11 - m.division.schedule_priority)  # 1→10, 10→1
        objective_terms.append(compactness_weight * start_vars[m.id])

    model.minimize(sum(objective_terms))

    # ── Solve ──────────────────────────────────────────────────────────────
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 120.0
    solver.parameters.num_workers = 8
    status = solver.solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise RuntimeError(f'OR-Tools returned status {solver.status_name(status)}')

    # ── Extract solution and save ──────────────────────────────────────────
    naive_start = datetime.combine(tournament.date, tournament.start_time)
    start_dt = timezone.make_aware(naive_start) if timezone.is_naive(naive_start) else naive_start

    updated = []
    for m in matches:
        start_slot = solver.value(start_vars[m.id])
        m.scheduled_time = start_dt + timedelta(minutes=start_slot * SLOT)

        for c, lit in enumerate(court_lits[m.id]):
            if solver.value(lit):
                m.court = str(c + 1)
                break

        updated.append(m)

    for m in updated:
        m.save(update_fields=['scheduled_time', 'court'])

    return len(updated)


# ---------------------------------------------------------------------------
# Greedy fallback
# ---------------------------------------------------------------------------

def _schedule_greedy(tournament, matches):
    """
    Original greedy scheduler — used as fallback when OR-Tools is unavailable
    or fails to find a feasible solution within the time limit.
    """
    naive_start = datetime.combine(tournament.date, tournament.start_time)
    start_dt = timezone.make_aware(naive_start) if timezone.is_naive(naive_start) else naive_start

    court_free = [start_dt] * tournament.court_count
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
