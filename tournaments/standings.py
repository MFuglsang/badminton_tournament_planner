"""
Standings computation for divisions.

Configuration (not exposed in the GUI):
  win_points    – competition points awarded for a match victory (default: 2)
  loss_points   – competition points awarded for a match loss   (default: 0)
  tiebreakers   – ordered list of methods applied when teams are level on points:
                    'head_to_head'   first tiebreaker: points in matches among
                                     the tied teams only (mini-league table)
                    'points_scored'  second tiebreaker: net individual points
                                     (points won minus points conceded across
                                     all sets in all matches)
"""

import re

STANDINGS_CONFIG = {
    'win_points': 2,
    'loss_points': 0,
    'tiebreakers': ['head_to_head', 'points_scored'],
}


# ---------------------------------------------------------------------------
# Score parsing
# ---------------------------------------------------------------------------

def _parse_score(score_str):
    """
    Parse a score string such as "21-15, 18-21, 21-18".
    Returns (team1_total, team2_total) summed over all sets.
    Unparseable parts are silently ignored; missing score returns (0, 0).
    """
    if not score_str:
        return 0, 0
    t1_total = t2_total = 0
    for m in re.finditer(r'(\d+)\s*-\s*(\d+)', score_str):
        t1_total += int(m.group(1))
        t2_total += int(m.group(2))
    return t1_total, t2_total


# ---------------------------------------------------------------------------
# Core standings computation
# ---------------------------------------------------------------------------

def compute_standings(division):
    """
    Return a sorted list of row-dicts for *division*.

    Each row contains:
        team, played, won, lost, points, score_for, score_against
    """
    cfg = STANDINGS_CONFIG

    completed = list(
        division.matches
        .filter(status='completed')
        .select_related('team1', 'team2', 'winner')
    )

    rows = {
        t.pk: {
            'team': t,
            'played': 0,
            'won': 0,
            'lost': 0,
            'points': 0,
            'score_for': 0,
            'score_against': 0,
        }
        for t in division.teams.all()
    }

    # Canonical match lookup: (pk_a, pk_b) with a < b → winner_pk or None
    h2h = {}

    for match in completed:
        t1, t2 = match.team1_id, match.team2_id
        if t2 is None:
            continue  # bye match – skip for standings
        sf1, sf2 = _parse_score(match.score)

        for pk, sf, sa in ((t1, sf1, sf2), (t2, sf2, sf1)):
            if pk in rows:
                rows[pk]['played'] += 1
                rows[pk]['score_for'] += sf
                rows[pk]['score_against'] += sa

        if match.winner_id in rows:
            rows[match.winner_id]['won'] += 1
            rows[match.winner_id]['points'] += cfg['win_points']
            loser_id = t2 if match.winner_id == t1 else t1
            if loser_id in rows:
                rows[loser_id]['lost'] += 1
                rows[loser_id]['points'] += cfg['loss_points']

        key = (min(t1, t2), max(t1, t2))
        h2h[key] = match.winner_id

    sorted_rows = sorted(rows.values(), key=lambda r: -r['points'])
    return _apply_tiebreakers(sorted_rows, h2h)


def compute_group_standings(division):
    """
    For playoff divisions: return an ordered list of (group_number, standings_rows)
    where each standings_rows is the result of compute_standings for that group's matches.
    """
    from django.db.models import Q

    # Find all group numbers in use
    group_numbers = sorted(
        division.matches.filter(phase='group')
        .values_list('group_number', flat=True)
        .distinct()
    )

    cfg = STANDINGS_CONFIG
    result = []
    for g_num in group_numbers:
        group_matches = list(
            division.matches
            .filter(phase='group', group_number=g_num, status='completed')
            .select_related('team1', 'team2', 'winner')
        )
        # Collect all teams in this group from matches
        team_pks = set()
        for m in division.matches.filter(phase='group', group_number=g_num).select_related('team1', 'team2'):
            if m.team1_id:
                team_pks.add(m.team1_id)
            if m.team2_id:
                team_pks.add(m.team2_id)

        from players.models import Team
        teams_qs = Team.objects.filter(pk__in=team_pks)

        rows = {
            t.pk: {
                'team': t,
                'played': 0,
                'won': 0,
                'lost': 0,
                'points': 0,
                'score_for': 0,
                'score_against': 0,
            }
            for t in teams_qs
        }

        h2h = {}
        for match in group_matches:
            t1, t2 = match.team1_id, match.team2_id
            if t2 is None:
                continue
            sf1, sf2 = _parse_score(match.score)
            for pk, sf, sa in ((t1, sf1, sf2), (t2, sf2, sf1)):
                if pk in rows:
                    rows[pk]['played'] += 1
                    rows[pk]['score_for'] += sf
                    rows[pk]['score_against'] += sa
            if match.winner_id in rows:
                rows[match.winner_id]['won'] += 1
                rows[match.winner_id]['points'] += cfg['win_points']
                loser_id = t2 if match.winner_id == t1 else t1
                if loser_id in rows:
                    rows[loser_id]['lost'] += 1
                    rows[loser_id]['points'] += cfg['loss_points']
            key = (min(t1, t2), max(t1, t2))
            h2h[key] = match.winner_id

        sorted_rows = sorted(rows.values(), key=lambda r: -r['points'])
        sorted_rows = _apply_tiebreakers(sorted_rows, h2h)
        result.append((g_num, sorted_rows))

    return result


# ---------------------------------------------------------------------------
# Tiebreaker engine
# ---------------------------------------------------------------------------

def _h2h_points(team_pk, group_pks, h2h):
    """Competition points earned in matches against other teams in *group_pks*."""
    cfg = STANDINGS_CONFIG
    total = 0
    for other_pk in group_pks:
        if other_pk == team_pk:
            continue
        key = (min(team_pk, other_pk), max(team_pk, other_pk))
        winner = h2h.get(key)
        if winner == team_pk:
            total += cfg['win_points']
    return total


def _score_diff(row):
    return row['score_for'] - row['score_against']


def _apply_tiebreakers(rows, h2h):
    """
    Walk through groups of rows tied on competition points and apply
    the tiebreakers from STANDINGS_CONFIG in order.
    """
    tiebreakers = STANDINGS_CONFIG['tiebreakers']
    result = []

    # Split into equal-points groups
    groups = _group_by(rows, key=lambda r: r['points'])

    for group in groups:
        if len(group) == 1:
            result.extend(group)
            continue

        group_pks = {r['team'].pk for r in group}

        # Build the composite sort key for each row in this group
        def sort_key(row):
            key = []
            for tb in tiebreakers:
                if tb == 'head_to_head':
                    key.append(-_h2h_points(row['team'].pk, group_pks, h2h))
                elif tb == 'points_scored':
                    key.append(-_score_diff(row))
            return key

        result.extend(sorted(group, key=sort_key))

    return result


def _group_by(rows, key):
    """Split *rows* into consecutive groups with the same key value."""
    if not rows:
        return []
    groups = []
    current = [rows[0]]
    for row in rows[1:]:
        if key(row) == key(current[0]):
            current.append(row)
        else:
            groups.append(current)
            current = [row]
    groups.append(current)
    return groups
