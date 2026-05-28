"""
Scheduling logic for generating match schedules based on tournament type.
- Round-robin: all teams play against each other (group tournaments)
- Bracket: single elimination bracket (tree tournaments)
- Playoff: group stage (round-robin per group) + single-elimination bracket
"""
import itertools
import math

from django.utils.translation import gettext_lazy as _


def _sort_teams_by_seed(division, teams):
    """
    Sort teams for bracket/playoff seeding:
    - Seeded teams (with a DivisionSeed entry) come first, in ascending seed number order.
    - Unseeded teams follow, sorted alphabetically by team name.
    """
    from .models import DivisionSeed
    seeds = {s.team_id: s.seed_number for s in DivisionSeed.objects.filter(division=division)}
    seeded = sorted([t for t in teams if t.pk in seeds], key=lambda t: seeds[t.pk])
    unseeded = sorted([t for t in teams if t.pk not in seeds], key=lambda t: t.name)
    return seeded + unseeded


# ---------------------------------------------------------------------------
# Round-robin
# ---------------------------------------------------------------------------

def _round_robin_rounds(teams):
    """
    Circle-method round-robin: returns a list of rounds, each round being a
    list of (team_a, team_b) pairs.  teams is assumed to already be sorted.
    If len(teams) is odd a dummy None is appended; pairs involving None are
    bye-matches and are excluded from each round's output.
    """
    if len(teams) % 2 == 1:
        teams = teams + [None]  # bye placeholder
    n = len(teams)
    rounds = []
    for _ in range(n - 1):
        pairs = []
        for i in range(n // 2):
            t1 = teams[i]
            t2 = teams[n - 1 - i]
            if t1 is not None and t2 is not None:
                pairs.append((t1, t2))
        rounds.append(pairs)
        # Rotate: keep teams[0] fixed, rotate the rest
        teams = [teams[0]] + [teams[-1]] + teams[1:-1]
    return rounds


def generate_round_robin(division):
    """
    Generate a full round-robin schedule using the circle method.
    Each round contains floor(n/2) simultaneous matches so that the
    time-slot scheduler can run them on parallel courts.
    """
    from .models import Match

    teams = list(division.teams.all())
    if len(teams) < 2:
        return []

    Match.objects.filter(division=division, status='pending').delete()

    teams = sorted(teams, key=lambda t: t.player1.name)
    rounds = _round_robin_rounds(teams)
    created = []
    for round_num, pairs in enumerate(rounds, start=1):
        for team1, team2 in pairs:
            match = Match.objects.create(
                division=division,
                team1=team1,
                team2=team2,
                match_round=round_num,
                status='pending',
            )
            created.append(match)
    return created


# ---------------------------------------------------------------------------
# Single-elimination bracket
# ---------------------------------------------------------------------------

def _seeding_order(n_slots):
    """
    Return the seed numbers placed in each bracket slot (standard seeding).
    Example: n_slots=4 → [1, 4, 2, 3] → pairs (1 vs 4) and (2 vs 3).
    """
    if n_slots == 1:
        return [1]
    half = n_slots // 2
    left = _seeding_order(half)
    right = [n_slots + 1 - s for s in left]
    result = []
    for l, r in zip(left, right):
        result.extend([l, r])
    return result


def get_round_label(round_num, total_rounds):
    """Return a translated label for the given bracket round."""
    from_end = total_rounds - round_num + 1
    labels = {
        1: _('Final'),
        2: _('Semifinal'),
        3: _('Quarterfinal'),
        4: _('Round of 16'),
    }
    if from_end in labels:
        return labels[from_end]
    return _('Round %(n)s') % {'n': round_num}


def _bracket_placeholder_label(round_num, total_rounds, n_slots, slot_num):
    """Human-readable label for a not-yet-determined bracket match.

    Stored in DB; rendered as-is in templates. Forced to English so the
    stored label matches the source language used in the .po file (existing
    Danish labels in legacy data continue to render unchanged).
    """
    from django.utils.translation import override
    with override('en'):
        name = str(get_round_label(round_num, total_rounds))
    return name if n_slots == 1 else f'{name} {slot_num}'


def generate_bracket(division):
    """
    Pre-create the ENTIRE single-elimination bracket structure:
      - Round 1: real matches (with teams) or bye (team2=None, auto-completed).
      - Round 2+: placeholder matches (team1=None, team2=None, bracket_label set).

    Byes are auto-advanced so the next-round placeholder immediately gets team1 filled.
    Returns all created Match objects ordered by (match_round, bracket_slot).
    """
    from .models import Match

    teams = list(division.teams.all())
    n = len(teams)
    if n < 2:
        return []

    teams = _sort_teams_by_seed(division, teams)

    total_rounds = math.ceil(math.log2(n))
    bracket_size = 2 ** total_rounds

    # Delete ALL existing matches for a clean regeneration
    Match.objects.filter(division=division).delete()

    seed_order = _seeding_order(bracket_size)
    slots = [teams[s - 1] if s <= n else None for s in seed_order]

    created = []

    # ── Round 1 ──────────────────────────────────────────────────────────
    for i in range(0, bracket_size, 2):
        slot_num = i // 2 + 1
        t1, t2 = slots[i], slots[i + 1]

        if t1 is None and t2 is None:
            continue
        if t1 is None:
            t1, t2 = t2, None  # normalise: real team in t1

        if t2 is None:
            match = Match.objects.create(
                division=division,
                team1=t1, team2=None,
                winner=t1, score='Bye',
                match_round=1, bracket_slot=slot_num,
                status='completed', walkover=True,
            )
        else:
            match = Match.objects.create(
                division=division,
                team1=t1, team2=t2,
                match_round=1, bracket_slot=slot_num,
                status='pending',
            )
        created.append(match)

    # ── Round 2+ placeholders ────────────────────────────────────────────
    for r in range(2, total_rounds + 1):
        n_slots = bracket_size // (2 ** r)
        for s in range(1, n_slots + 1):
            match = Match.objects.create(
                division=division,
                team1=None, team2=None,
                match_round=r, bracket_slot=s,
                bracket_label=_bracket_placeholder_label(r, total_rounds, n_slots, s),
                status='pending',
            )
            created.append(match)

    # ── Auto-advance byes ────────────────────────────────────────────────
    for match in [m for m in created if m.team2 is None and m.status == 'completed']:
        _advance_bracket_inline(match)

    return created


def _advance_bracket_inline(match):
    """
    Fill in a next-round placeholder after a bracket match completes.
    Used internally (during generation for byes, and after result recording).
    Works for both 'tree' and 'playoff' (bracket-phase) divisions.
    """
    from .models import Match

    division = match.division
    if division.tournament_type not in ('tree', 'playoff'):
        return
    # Group-phase matches in a playoff division are handled by
    # fill_playoff_bracket_from_group instead.
    if division.tournament_type == 'playoff' and match.phase == 'group':
        return
    if not match.winner or match.bracket_slot is None:
        return

    next_round = match.match_round + 1
    next_slot = math.ceil(match.bracket_slot / 2)
    is_odd = (match.bracket_slot % 2 == 1)

    qs = Match.objects.filter(
        division=division,
        match_round=next_round,
        bracket_slot=next_slot,
    )
    if division.tournament_type == 'playoff':
        qs = qs.filter(phase='playoff')

    placeholder = qs.first()

    if not placeholder:
        return  # No further rounds (match was the final)

    if is_odd:
        placeholder.team1 = match.winner
    else:
        placeholder.team2 = match.winner

    # If both teams are now known: clear placeholder label
    if placeholder.team1 and placeholder.team2:
        placeholder.bracket_label = None

    placeholder.save(update_fields=['team1', 'team2', 'bracket_label'])


def advance_bracket(match):
    """Public entry point – called after a match result is saved."""
    if match.division.tournament_type == 'double_elim':
        _advance_double_elim_inline(match)
    else:
        _advance_bracket_inline(match)


def fill_playoff_bracket_from_group(division, group_number):
    """
    Called after any group-stage match in a playoff division completes.
    If all matches in *group_number* are now done, resolves the group
    standings and fills the corresponding playoff-bracket slots with the
    actual teams.  Also handles bye slots: sets winner and advances them.
    """
    from .models import Match
    from .standings import compute_group_standings

    if group_number is None:
        return

    # Only proceed if every group match is completed
    pending = (
        division.matches
        .filter(phase='group', group_number=group_number)
        .exclude(status='completed')
        .count()
    )
    if pending > 0:
        return

    # Build {label → team} for this group
    position_to_team = {}
    for gnum, rows in compute_group_standings(division):
        if gnum == group_number:
            for pos, row in enumerate(rows, start=1):
                position_to_team[f'Nr.{pos} gr.{group_number}'] = row['team']
            break

    if not position_to_team:
        return

    # Find playoff bracket matches that reference this group in their label
    bracket_matches = list(
        division.matches
        .filter(phase='playoff', bracket_label__icontains=f'gr.{group_number}')
        .select_related('team1', 'team2')
    )

    for match in bracket_matches:
        label = match.bracket_label or ''

        if '(fri)' in label:
            # Bye slot: "Nr.X gr.Y (fri)"
            seed_label = label.replace(' (fri)', '').strip()
            team = position_to_team.get(seed_label)
            if team and match.team1 is None:
                match.team1 = team
                match.winner = team
                match.save(update_fields=['team1', 'winner'])
                _advance_bracket_inline(match)
        else:
            # Regular slot: "Nr.X gr.Y vs Nr.A gr.B"
            parts = label.split(' vs ', 1)
            if len(parts) != 2:
                continue
            t1_label, t2_label = parts[0].strip(), parts[1].strip()
            update_fields = []
            if match.team1 is None and t1_label in position_to_team:
                match.team1 = position_to_team[t1_label]
                update_fields.append('team1')
            if match.team2 is None and t2_label in position_to_team:
                match.team2 = position_to_team[t2_label]
                update_fields.append('team2')
            if update_fields:
                if match.team1 and match.team2:
                    match.bracket_label = None
                    update_fields.append('bracket_label')
                match.save(update_fields=update_fields)


def get_bracket_data(division):
    """
    Build the bracket visualisation data for a tree or playoff division.
    Returns {'rounds': [...], 'total_rounds': int} or None.
    """
    if division.tournament_type == 'playoff':
        matches = list(
            division.matches
            .filter(phase='playoff')
            .select_related('team1', 'team2', 'winner')
            .order_by('match_round', 'bracket_slot')
        )
    else:
        matches = list(
            division.matches
            .select_related('team1', 'team2', 'winner')
            .order_by('match_round', 'bracket_slot')
        )

    if not matches:
        return None

    round1 = [m for m in matches if m.match_round == min(m.match_round for m in matches)]
    if not round1:
        return None

    bracket_size = len(round1) * 2
    total_rounds = int(math.log2(bracket_size)) if bracket_size > 1 else 1
    min_round = min(m.match_round for m in matches)

    # Key by (round, bracket_slot)
    lookup = {(m.match_round, m.bracket_slot): m for m in matches}

    BASE_HEIGHT = 80  # px per round-1 slot

    rounds = []
    for r_offset in range(total_rounds):
        r = min_round + r_offset
        n_slots = bracket_size // (2 ** (r_offset + 1))
        slot_height = BASE_HEIGHT * (2 ** r_offset)
        slots = [
            {
                'slot': s,
                'match': lookup.get((r, s)),
                'is_odd': s % 2 == 1,
            }
            for s in range(1, n_slots + 1)
        ]
        rounds.append({
            'label': get_round_label(r_offset + 1, total_rounds),
            'round': r,
            'is_last': r_offset == total_rounds - 1,
            'slot_height': slot_height,
            'slots': slots,
        })

    return {'rounds': rounds, 'total_rounds': total_rounds}


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------
# Playoff (group stage + bracket)
# ---------------------------------------------------------------------------

def generate_playoff(division):
    """
    Generate a playoff schedule:
    1. Divide teams into groups and generate round-robin within each group.
    2. Create a single-elimination bracket for the advancing teams,
       with byes if the total is not a power of 2.

    Groups are filled snake-style: A,B,C,D,D,C,B,A,A,...
    so teams are spread evenly when listed alphabetically.
    """
    from .models import Match

    teams = list(division.teams.all().order_by('name'))
    teams = _sort_teams_by_seed(division, teams)
    n = len(teams)
    group_count = max(1, division.group_count)
    advance_count = max(1, division.advance_count)

    if n < group_count * 2:
        return []  # Not enough teams

    # Delete existing matches cleanly
    Match.objects.filter(division=division).delete()

    # ── Divide teams into groups (snake order) ────────────────────────
    groups = [[] for _ in range(group_count)]
    for i, team in enumerate(teams):
        cycle = i // group_count
        pos = i % group_count
        group_idx = pos if cycle % 2 == 0 else (group_count - 1 - pos)
        groups[group_idx].append(team)

    created = []

    # ── Group stage: round-robin per group (circle method) ───────────
    for g_idx, group_teams in enumerate(groups):
        group_num = g_idx + 1
        rounds = _round_robin_rounds(list(group_teams))
        for round_num, pairs in enumerate(rounds, start=1):
            for team1, team2 in pairs:
                match = Match.objects.create(
                    division=division,
                    team1=team1,
                    team2=team2,
                    match_round=round_num,
                    group_number=group_num,
                    phase='group',
                    status='pending',
                )
                created.append(match)

    # ── Playoff bracket ───────────────────────────────────────────────
    total_advancing = group_count * advance_count
    total_rounds = math.ceil(math.log2(total_advancing)) if total_advancing > 1 else 1
    bracket_size = 2 ** total_rounds
    byes_needed = bracket_size - total_advancing

    # Bracket round numbering starts after group rounds
    max_group_round = max((m.match_round for m in created), default=0)
    bracket_base_round = max_group_round + 1

    seed_order = _seeding_order(bracket_size)

    # Slot → label: "V1G1" means "winner X of group 1"
    # Pattern: advance_count winners from G1, then G2, etc.
    advancing_seeds = []
    for advance_pos in range(1, advance_count + 1):
        for g_num in range(1, group_count + 1):
            advancing_seeds.append(f'Nr.{advance_pos} gr.{g_num}')

    slots = []
    for s in seed_order:
        if s <= total_advancing:
            slots.append(advancing_seeds[s - 1])
        else:
            slots.append(None)  # bye

    # Round 1 of bracket
    n_r1_slots = bracket_size // 2
    for i in range(n_r1_slots):
        slot_num = i + 1
        t1_label = slots[i * 2]
        t2_label = slots[i * 2 + 1]

        if t1_label is None and t2_label is None:
            continue

        if t2_label is None:
            # bye – auto-completed placeholder
            match = Match.objects.create(
                division=division,
                team1=None, team2=None,
                winner=None, score='Bye',
                match_round=bracket_base_round,
                bracket_slot=slot_num,
                bracket_label=f'{t1_label} (fri)',
                phase='playoff',
                status='completed',
                walkover=True,
            )
        elif t1_label is None:
            match = Match.objects.create(
                division=division,
                team1=None, team2=None,
                winner=None, score='Bye',
                match_round=bracket_base_round,
                bracket_slot=slot_num,
                bracket_label=f'{t2_label} (fri)',
                phase='playoff',
                status='completed',
                walkover=True,
            )
        else:
            match = Match.objects.create(
                division=division,
                team1=None, team2=None,
                match_round=bracket_base_round,
                bracket_slot=slot_num,
                bracket_label=f'{t1_label} vs {t2_label}',
                phase='playoff',
                status='pending',
            )
        created.append(match)

    # Remaining bracket rounds (placeholders)
    for r_offset in range(1, total_rounds):
        r = bracket_base_round + r_offset
        n_slots = bracket_size // (2 ** (r_offset + 1))
        for s in range(1, n_slots + 1):
            match = Match.objects.create(
                division=division,
                team1=None, team2=None,
                match_round=r,
                bracket_slot=s,
                bracket_label=_bracket_placeholder_label(r_offset + 1, total_rounds, n_slots, s),
                phase='playoff',
                status='pending',
            )
            created.append(match)

    return created


# ---------------------------------------------------------------------------

def generate_schedule(division):
    """Generate schedule based on the division's own tournament_type."""
    if division.tournament_type == 'tree':
        return generate_bracket(division)
    if division.tournament_type == 'playoff':
        return generate_playoff(division)
    if division.tournament_type == 'double_elim':
        return generate_double_elim_bracket(division)
    return generate_round_robin(division)


def regenerate_playoff_with_groups(division, groups):
    """
    Regenerate a playoff division's group-stage matches using explicit group
    assignments instead of the automatic snake-sort.

    ``groups`` is a list of lists of Team objects (or PKs resolved to teams),
    ordered groups[0] = group 1, groups[1] = group 2, etc.

    Returns the same structure as generate_playoff – all created Match objects.
    """
    from .models import Match

    n = sum(len(g) for g in groups)
    group_count = len(groups)
    advance_count = max(1, division.advance_count)

    if n < group_count * 2:
        return []

    # Delete ALL existing matches (group + playoff placeholders)
    Match.objects.filter(division=division).delete()

    created = []

    # ── Group stage: round-robin per group (circle method) ──────────────
    for g_idx, group_teams in enumerate(groups):
        group_num = g_idx + 1
        rounds = _round_robin_rounds(list(group_teams))
        for round_num, pairs in enumerate(rounds, start=1):
            for team1, team2 in pairs:
                match = Match.objects.create(
                    division=division,
                    team1=team1,
                    team2=team2,
                    match_round=round_num,
                    group_number=group_num,
                    phase='group',
                    status='pending',
                )
                created.append(match)

    # ── Re-use the playoff bracket generation from generate_playoff ──────
    #    Re-call it but skip the group stage since we already created it.
    #    To avoid code duplication we just inline the bracket part.
    total_advancing = group_count * advance_count
    total_rounds = math.ceil(math.log2(total_advancing)) if total_advancing > 1 else 1
    bracket_size = 2 ** total_rounds

    max_group_round = max((m.match_round for m in created), default=0)
    bracket_base_round = max_group_round + 1

    seed_order = _seeding_order(bracket_size)

    advancing_seeds = []
    for advance_pos in range(1, advance_count + 1):
        for g_num in range(1, group_count + 1):
            advancing_seeds.append(f'Nr.{advance_pos} gr.{g_num}')

    slots = []
    for s in seed_order:
        if s <= total_advancing:
            slots.append(advancing_seeds[s - 1])
        else:
            slots.append(None)

    n_r1_slots = bracket_size // 2
    for i in range(n_r1_slots):
        slot_num = i + 1
        t1_label = slots[i * 2]
        t2_label = slots[i * 2 + 1]

        if t1_label is None and t2_label is None:
            continue

        if t2_label is None:
            match = Match.objects.create(
                division=division, team1=None, team2=None,
                winner=None, score='Bye',
                match_round=bracket_base_round, bracket_slot=slot_num,
                bracket_label=f'{t1_label} (fri)', phase='playoff',
                status='completed', walkover=True,
            )
        elif t1_label is None:
            match = Match.objects.create(
                division=division, team1=None, team2=None,
                winner=None, score='Bye',
                match_round=bracket_base_round, bracket_slot=slot_num,
                bracket_label=f'{t2_label} (fri)', phase='playoff',
                status='completed', walkover=True,
            )
        else:
            match = Match.objects.create(
                division=division, team1=None, team2=None,
                match_round=bracket_base_round, bracket_slot=slot_num,
                bracket_label=f'{t1_label} vs {t2_label}',
                phase='playoff', status='pending',
            )
        created.append(match)

    for r_offset in range(1, total_rounds):
        r = bracket_base_round + r_offset
        n_slots = bracket_size // (2 ** (r_offset + 1))
        for s in range(1, n_slots + 1):
            match = Match.objects.create(
                division=division, team1=None, team2=None,
                match_round=r, bracket_slot=s,
                bracket_label=_bracket_placeholder_label(r_offset + 1, total_rounds, n_slots, s),
                phase='playoff', status='pending',
            )
            created.append(match)

    return created


# ---------------------------------------------------------------------------
# Double elimination bracket
# ---------------------------------------------------------------------------

def _lb_round_label(round_from_start, total_lb_rounds):
    """Translated label for a losers bracket round."""
    if round_from_start == total_lb_rounds:
        return _('LB Final')
    return _('LB Round %(n)s') % {'n': round_from_start}


def _lb_bracket_placeholder_label(round_num, lb_total, n_slots, slot_num):
    """Human-readable (English) label for a not-yet-determined LB match."""
    from django.utils.translation import override
    with override('en'):
        name = str(_lb_round_label(round_num, lb_total))
    return name if n_slots == 1 else f'{name} {slot_num}'


def _cascade_delete_lb_slot(division, lb_round, lb_slot):
    """
    Delete a void LB slot.  If its sibling at the same round is also gone,
    the parent slot (round+1) can likewise never be reached, so delete that too.
    """
    from .models import Match

    Match.objects.filter(
        division=division, phase='loser',
        match_round=lb_round, bracket_slot=lb_slot,
    ).delete()

    parent_slot = math.ceil(lb_slot / 2)
    sibling_slot = lb_slot + 1 if lb_slot % 2 == 1 else lb_slot - 1

    parent = Match.objects.filter(
        division=division, phase='loser',
        match_round=lb_round + 1, bracket_slot=parent_slot,
    ).first()
    if parent is None:
        return  # No higher round exists

    sibling_exists = Match.objects.filter(
        division=division, phase='loser',
        match_round=lb_round, bracket_slot=sibling_slot,
    ).exists()
    if not sibling_exists:
        # Both inputs to parent are gone → parent is void too
        _cascade_delete_lb_slot(division, lb_round + 1, parent_slot)


def _remove_void_lb_slots(division, lb_r1_slots, wb_r1_matches):
    """
    After generating LB placeholders, delete every LB R1 slot whose two WB R1
    source slots are both byes.  Cascades upward through the LB tree.
    """
    wb_bye_slots = {
        m.bracket_slot
        for m in wb_r1_matches
        if m.walkover and m.team2 is None
    }
    for s in range(1, lb_r1_slots + 1):
        if (2 * s - 1) in wb_bye_slots and (2 * s) in wb_bye_slots:
            _cascade_delete_lb_slot(division, 1, s)


def generate_double_elim_bracket(division):
    """
    Pre-create all matches for a double-elimination bracket:
      - Winners Bracket (WB): seeded single-elim, phase='winner', round 1..wb_total
      - Losers Bracket (LB): WB R1 losers get a second chance, phase='loser', round 1..lb_total
      - Grand Final (GF): WB winner vs LB winner, phase='winner', round wb_total+1

    Only WB R1 losers drop into LB (simplified double-elimination).
    """
    from .models import Match

    teams = list(division.teams.all())
    n = len(teams)
    if n < 2:
        return []

    teams = _sort_teams_by_seed(division, teams)

    wb_total = math.ceil(math.log2(n))
    wb_bracket_size = 2 ** wb_total
    # Each LB R1 match receives 2 WB R1 losers
    lb_r1_slots = wb_bracket_size // 4
    lb_total = max(1, wb_total - 1) if lb_r1_slots >= 1 else 0

    Match.objects.filter(division=division).delete()

    seed_order = _seeding_order(wb_bracket_size)
    wb_teams = [teams[s - 1] if s <= n else None for s in seed_order]

    created = []
    wb_r1_matches = []

    # ── Winners Bracket Round 1 ───────────────────────────────────────────
    for i in range(0, wb_bracket_size, 2):
        slot_num = i // 2 + 1
        t1, t2 = wb_teams[i], wb_teams[i + 1]

        if t1 is None and t2 is None:
            continue
        if t1 is None:
            t1, t2 = t2, None  # normalise: real team in t1

        if t2 is None:
            match = Match.objects.create(
                division=division,
                team1=t1, team2=None,
                winner=t1, score='Bye',
                match_round=1, bracket_slot=slot_num,
                phase='winner',
                status='completed', walkover=True,
            )
        else:
            match = Match.objects.create(
                division=division,
                team1=t1, team2=t2,
                match_round=1, bracket_slot=slot_num,
                phase='winner',
                status='pending',
            )
        created.append(match)
        wb_r1_matches.append(match)

    # ── Winners Bracket Round 2+ placeholders ─────────────────────────────
    for r in range(2, wb_total + 1):
        n_slots = wb_bracket_size // (2 ** r)
        for s in range(1, n_slots + 1):
            match = Match.objects.create(
                division=division,
                team1=None, team2=None,
                match_round=r, bracket_slot=s,
                bracket_label=_bracket_placeholder_label(r, wb_total, n_slots, s),
                phase='winner',
                status='pending',
            )
            created.append(match)

    # ── Losers Bracket placeholders ───────────────────────────────────────
    lb_r1_matches = []
    if lb_total >= 1:
        for r in range(1, lb_total + 1):
            n_lb = lb_r1_slots // (2 ** (r - 1))
            for s in range(1, n_lb + 1):
                if r == 1:
                    wb_a = 2 * s - 1
                    wb_b = 2 * s
                    lb_label = f"Taber kamp {wb_a} mod kamp {wb_b}"
                else:
                    lb_label = _lb_bracket_placeholder_label(r, lb_total, n_lb, s)
                match = Match.objects.create(
                    division=division,
                    team1=None, team2=None,
                    match_round=r, bracket_slot=s,
                    bracket_label=lb_label,
                    phase='loser',
                    status='pending',
                )
                created.append(match)
                if r == 1:
                    lb_r1_matches.append(match)

    # ── Remove LB R1 slots where both WB R1 sources are byes (cascade upward) ─
    if lb_total >= 1:
        _remove_void_lb_slots(division, lb_r1_slots, wb_r1_matches)
        # Reload: _remove_void_lb_slots may have deleted some LB R1 matches
        from .models import Match as _Match
        lb_r1_matches = list(
            _Match.objects.filter(division=division, phase='loser', match_round=1)
            .order_by('bracket_slot')
        )

    # ── Auto-advance WB R1 byes (winner → WB R2; no LB loser for byes) ───
    for match in wb_r1_matches:
        if match.status == 'completed':
            _advance_double_elim_inline(match)

    # ── Auto-advance LB R1 matches that only have one team (LB bye) ───────
    for lb_match in lb_r1_matches:
        lb_match.refresh_from_db()
        if lb_match.team2 and not lb_match.team1:
            lb_match.team1, lb_match.team2 = lb_match.team2, None
            lb_match.save(update_fields=['team1', 'team2'])
        if lb_match.team1 and not lb_match.team2:
            lb_match.winner = lb_match.team1
            lb_match.score = 'Bye'
            lb_match.status = 'completed'
            lb_match.walkover = True
            lb_match.save(update_fields=['winner', 'score', 'status', 'walkover'])
            _advance_double_elim_inline(lb_match)

    # Return only matches that still exist in DB
    # (_remove_void_lb_slots may have deleted some entries from `created`)
    surviving_pks = set(
        Match.objects.filter(pk__in=[m.pk for m in created])
        .values_list('pk', flat=True)
    )
    return [m for m in created if m.pk in surviving_pks]


def _advance_double_elim_inline(match):
    """
    Advance a completed match in a double-elimination bracket.

    - WB (phase='winner'): winner → next WB round or GF (team1);
      R1 loser → LB R1.
    - LB (phase='loser'): winner → next LB round or GF (team2).
    - GF (round wb_total+1): nothing further to advance.
    """
    from .models import Match

    division = match.division
    if division.tournament_type != 'double_elim':
        return
    if not match.winner or match.bracket_slot is None:
        return

    n = division.teams.count()
    if n < 2:
        return
    wb_total = math.ceil(math.log2(n))

    next_slot = math.ceil(match.bracket_slot / 2)
    is_odd = (match.bracket_slot % 2 == 1)

    if match.phase == 'winner':
        # Normal WB advance: winner → next round
        wb_next = Match.objects.filter(
            division=division, phase='winner',
            match_round=match.match_round + 1, bracket_slot=next_slot,
        ).first()
        if wb_next:
            if is_odd:
                wb_next.team1 = match.winner
            else:
                wb_next.team2 = match.winner
            if wb_next.team1 and wb_next.team2:
                wb_next.bracket_label = None
            wb_next.save(update_fields=['team1', 'team2', 'bracket_label'])

        # WB R1 loser drops into LB R1
        if match.match_round == 1:
            loser = (
                match.team2 if match.winner_id == match.team1_id else match.team1
            )
            if loser:
                lb_slot = math.ceil(match.bracket_slot / 2)
                lb_is_odd = (match.bracket_slot % 2 == 1)
                lb_r1 = Match.objects.filter(
                    division=division, phase='loser',
                    match_round=1, bracket_slot=lb_slot,
                ).first()
                if lb_r1:
                    if lb_is_odd:
                        lb_r1.team1 = loser
                    else:
                        lb_r1.team2 = loser
                    # Update bracket_label to reflect which WB slot still needs to resolve
                    if lb_r1.team1 and lb_r1.team2:
                        lb_r1.bracket_label = None
                    elif lb_r1.team1 and not lb_r1.team2:
                        lb_r1.bracket_label = f"Taber kamp {lb_slot * 2}"
                    elif lb_r1.team2 and not lb_r1.team1:
                        lb_r1.bracket_label = f"Taber kamp {lb_slot * 2 - 1}"
                    lb_r1.save(update_fields=['team1', 'team2', 'bracket_label'])

                    # If the companion WB R1 slot was a bye, auto-advance LB R1 now
                    if lb_r1.team1 and not lb_r1.team2:
                        # Companion is the even WB slot
                        if Match.objects.filter(
                            division=division, phase='winner',
                            match_round=1, bracket_slot=lb_slot * 2,
                            walkover=True, team2__isnull=True,
                        ).exists():
                            lb_r1.winner = lb_r1.team1
                            lb_r1.score = 'Bye'
                            lb_r1.status = 'completed'
                            lb_r1.walkover = True
                            lb_r1.bracket_label = None
                            lb_r1.save(update_fields=[
                                'winner', 'score', 'status', 'walkover', 'bracket_label',
                            ])
                            _advance_double_elim_inline(lb_r1)
                    elif lb_r1.team2 and not lb_r1.team1:
                        # Companion is the odd WB slot
                        if Match.objects.filter(
                            division=division, phase='winner',
                            match_round=1, bracket_slot=lb_slot * 2 - 1,
                            walkover=True, team2__isnull=True,
                        ).exists():
                            lb_r1.team1, lb_r1.team2 = lb_r1.team2, None
                            lb_r1.winner = lb_r1.team1
                            lb_r1.score = 'Bye'
                            lb_r1.status = 'completed'
                            lb_r1.walkover = True
                            lb_r1.bracket_label = None
                            lb_r1.save(update_fields=[
                                'team1', 'team2', 'winner', 'score',
                                'status', 'walkover', 'bracket_label',
                            ])
                            _advance_double_elim_inline(lb_r1)

    elif match.phase == 'loser':
        lb_total = max(1, wb_total - 1)

        if match.match_round == lb_total:
            # LB Final – no Grand Final, LB winner simply wins the LB
            return
        else:
            lb_next = Match.objects.filter(
                division=division, phase='loser',
                match_round=match.match_round + 1, bracket_slot=next_slot,
            ).first()
            if lb_next:
                if is_odd:
                    lb_next.team1 = match.winner
                else:
                    lb_next.team2 = match.winner
                if lb_next.team1 and lb_next.team2:
                    lb_next.bracket_label = None
                lb_next.save(update_fields=['team1', 'team2', 'bracket_label'])

                # If the sibling LB match was deleted (void), auto-advance lb_next now
                sibling_slot = match.bracket_slot + 1 if is_odd else match.bracket_slot - 1
                if not Match.objects.filter(
                    division=division, phase='loser',
                    match_round=match.match_round, bracket_slot=sibling_slot,
                ).exists():
                    if lb_next.team1 and not lb_next.team2:
                        lb_next.winner = lb_next.team1
                        lb_next.score = 'Bye'
                        lb_next.status = 'completed'
                        lb_next.walkover = True
                        lb_next.bracket_label = None
                        lb_next.save(update_fields=[
                            'winner', 'score', 'status', 'walkover', 'bracket_label',
                        ])
                        _advance_double_elim_inline(lb_next)
                    elif lb_next.team2 and not lb_next.team1:
                        lb_next.team1, lb_next.team2 = lb_next.team2, None
                        lb_next.winner = lb_next.team1
                        lb_next.score = 'Bye'
                        lb_next.status = 'completed'
                        lb_next.walkover = True
                        lb_next.bracket_label = None
                        lb_next.save(update_fields=[
                            'team1', 'team2', 'winner', 'score',
                            'status', 'walkover', 'bracket_label',
                        ])
                        _advance_double_elim_inline(lb_next)


def get_double_elim_data(division):
    """
    Build bracket visualisation data for a double-elimination division.
    Returns {'wb': ..., 'lb': ...} or None.
    """
    from .models import Match

    if division.tournament_type != 'double_elim':
        return None

    n = division.teams.count()
    if n < 2:
        return None

    wb_total = math.ceil(math.log2(n))
    lb_total = max(1, wb_total - 1)

    wb_matches = list(
        division.matches
        .filter(phase='winner')
        .select_related('team1', 'team2', 'winner')
        .order_by('match_round', 'bracket_slot')
    )
    lb_matches = list(
        division.matches
        .filter(phase='loser')
        .select_related('team1', 'team2', 'winner')
        .order_by('match_round', 'bracket_slot')
    )

    def _build(matches, total_rounds, label_fn, team_labels_fn=None):
        if not matches:
            return None
        min_r = min(m.match_round for m in matches)
        # Use 2**total_rounds so bracket_size reflects the original (pre-deletion)
        # number of slots — deleted double-bye slots must still count as "columns".
        bracket_size = 2 ** total_rounds
        lookup = {(m.match_round, m.bracket_slot): m for m in matches}
        BASE_HEIGHT = 80
        rounds = []
        for r_offset in range(total_rounds):
            r = min_r + r_offset
            n_slots = bracket_size // (2 ** (r_offset + 1))
            slot_height = BASE_HEIGHT * (2 ** r_offset)
            slots = []
            for s in range(1, n_slots + 1):
                m = lookup.get((r, s))
                entry = {'slot': s, 'match': m, 'is_odd': s % 2 == 1, 'is_void': m is None}
                if team_labels_fn:
                    t1, t2 = team_labels_fn(r_offset, s)
                    entry['t1_label'] = t1
                    entry['t2_label'] = t2
                slots.append(entry)
            rounds.append({
                'label': label_fn(r_offset + 1, total_rounds),
                'round': r,
                'is_last': r_offset == total_rounds - 1,
                'slot_height': slot_height,
                'slots': slots,
            })
        return {'rounds': rounds, 'total_rounds': total_rounds}

    # Lookups for computing LB team labels using actual match numbers
    wb_min_r = min(m.match_round for m in wb_matches)
    wb_r1_by_slot = {m.bracket_slot: m for m in wb_matches if m.match_round == wb_min_r}
    lb_by_round_slot = {(m.match_round, m.bracket_slot): m for m in lb_matches}
    lb_min_r = min((m.match_round for m in lb_matches), default=1)

    def _lb_team_labels(r_offset, s):
        if r_offset == 0:  # LB R1 — sources are WB R1 bracket slots
            def _wb_lbl(wb_slot):
                m = wb_r1_by_slot.get(wb_slot)
                if m is None or (m.walkover and m.team2 is None):
                    return None  # bye WB match — no loser ever
                return f"Taber #{m.match_number}" if m.match_number else f"Taber kamp {wb_slot}"

            t1, t2 = _wb_lbl(2 * s - 1), _wb_lbl(2 * s)
            # When only one source is real, shift it to t1 (matches auto-advance swap)
            if t1 is None and t2 is not None:
                return (t2, None)
            return (t1, t2)
        else:
            # LB R2+ — sources are previous LB round winners
            prev_r = lb_min_r + r_offset - 1

            def _lb_lbl(lb_slot):
                m = lb_by_round_slot.get((prev_r, lb_slot))
                if m is None:
                    return None  # void LB slot
                return f"Vinder #{m.match_number}" if m.match_number else f"Vinder taber-kamp {lb_slot}"

            t1, t2 = _lb_lbl(2 * s - 1), _lb_lbl(2 * s)
            if t1 is None and t2 is not None:
                return (t2, None)
            return (t1, t2)

    wb_data = _build(wb_matches, wb_total, get_round_label)
    lb_data = _build(lb_matches, lb_total, _lb_round_label, _lb_team_labels)

    return {'wb': wb_data, 'lb': lb_data}
