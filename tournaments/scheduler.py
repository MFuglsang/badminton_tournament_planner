"""
Scheduling logic for generating match schedules based on tournament type.
- Round-robin: all teams play against each other (group tournaments)
- Bracket: single elimination bracket (tree tournaments)
"""
import itertools
import math


# ---------------------------------------------------------------------------
# Round-robin
# ---------------------------------------------------------------------------

def generate_round_robin(division):
    """Generate a full round-robin schedule. Every team plays every other once."""
    from .models import Match

    teams = list(division.teams.all())
    if len(teams) < 2:
        return []

    Match.objects.filter(division=division, status='pending').delete()

    pairs = list(itertools.combinations(teams, 2))
    created = []
    for round_num, (team1, team2) in enumerate(pairs, start=1):
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
    """Return a Danish label for the given bracket round."""
    from_end = total_rounds - round_num + 1
    labels = {1: 'Finale', 2: 'Semifinale', 3: 'Kvartfinale', 4: 'Ottendedelsfinale'}
    return labels.get(from_end, f'Runde {round_num}')


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

    teams.sort(key=lambda t: t.player1.ranking + (t.player2.ranking if t.player2 else 0))

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
                bracket_label=f'R{r-1}S{2*s-1}vsR{r-1}S{2*s}',  # temp, updated in views
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
    """
    from .models import Match

    division = match.division
    if division.tournament_type != 'tree':
        return
    if not match.winner or match.bracket_slot is None:
        return

    next_round = match.match_round + 1
    next_slot = math.ceil(match.bracket_slot / 2)
    is_odd = (match.bracket_slot % 2 == 1)

    placeholder = Match.objects.filter(
        division=division,
        match_round=next_round,
        bracket_slot=next_slot,
    ).first()

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
    _advance_bracket_inline(match)


def get_bracket_data(division):
    """
    Build the bracket visualisation data for a tree division.
    Returns {'rounds': [...], 'total_rounds': int} or None.
    """
    matches = list(
        division.matches
        .select_related('team1', 'team2', 'winner')
        .order_by('match_round', 'bracket_slot')
    )
    if not matches:
        return None

    round1 = [m for m in matches if m.match_round == 1]
    if not round1:
        return None

    bracket_size = len(round1) * 2
    total_rounds = int(math.log2(bracket_size))

    # Key by (round, bracket_slot)
    lookup = {(m.match_round, m.bracket_slot): m for m in matches}

    BASE_HEIGHT = 80  # px per round-1 slot

    rounds = []
    for r in range(1, total_rounds + 1):
        n_slots = bracket_size // (2 ** r)
        slot_height = BASE_HEIGHT * (2 ** (r - 1))
        slots = [
            {
                'slot': s,
                'match': lookup.get((r, s)),
                'is_odd': s % 2 == 1,
            }
            for s in range(1, n_slots + 1)
        ]
        rounds.append({
            'label': get_round_label(r, total_rounds),
            'round': r,
            'is_last': r == total_rounds,
            'slot_height': slot_height,
            'slots': slots,
        })

    return {'rounds': rounds, 'total_rounds': total_rounds}


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

def generate_schedule(division):
    """Generate schedule based on the division's own tournament_type."""
    if division.tournament_type == 'tree':
        return generate_bracket(division)
    return generate_round_robin(division)
