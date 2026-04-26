import json
from datetime import datetime, timedelta

from django.db.models import Max, Q
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST
from .models import Tournament, Division, Match, DivisionSeed
from .forms import MatchResultForm, DivisionForm, TournamentForm, get_participants_form, WalkoverForm
from .standings import compute_standings, compute_group_standings
from players.models import Team
from .scheduler import generate_schedule, advance_bracket, get_bracket_data, regenerate_playoff_with_groups
from .schedule_planner import generate_time_schedule
from .player_status import (
    get_busy_info, apply_status_to_matches, set_player_rest,
    check_match_startable, player_status as _player_status, team_status as _team_status,
)


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------

def _build_seed_lookup(tournament):
    """Return {(division_pk, team_pk): seed_number} for every seed in the tournament."""
    return {
        (s.division_id, s.team_id): s.seed_number
        for s in DivisionSeed.objects.filter(division__tournament=tournament)
    }


def _apply_seed_labels(matches, seed_lookup):
    """Annotate match objects with .t1_seed / .t2_seed display strings, e.g. ' (1)'."""
    for match in matches:
        s1 = seed_lookup.get((match.division_id, match.team1_id))
        s2 = seed_lookup.get((match.division_id, match.team2_id))
        match.t1_seed = f' ({s1})' if s1 else ''
        match.t2_seed = f' ({s2})' if s2 else ''


def _seeds_dict_for_division(division, seed_lookup):
    """Return {team_pk: ' (N)'} for use in standings / player-list templates."""
    return {
        team_pk: f' ({seed_num})'
        for (div_pk, team_pk), seed_num in seed_lookup.items()
        if div_pk == division.pk
    }


@login_required
def tournament_list(request):
    tournaments = Tournament.objects.filter(owner=request.user).prefetch_related('divisions').order_by('-date')
    return render(request, 'tournaments/tournament_list.html', {'tournaments': tournaments})


@login_required
def tournament_create(request):
    if request.method == 'POST':
        form = TournamentForm(request.POST, request.FILES)
        if form.is_valid():
            tournament = form.save(commit=False)
            tournament.owner = request.user
            tournament.save()
            messages.success(request, f'Turnering "{tournament.name}" er oprettet.')
            return redirect('tournament_detail', pk=tournament.pk)
    else:
        form = TournamentForm()
    return render(request, 'tournaments/tournament_form.html', {'form': form})


@login_required
def tournament_edit(request, pk):
    tournament = get_object_or_404(Tournament, pk=pk, owner=request.user)
    if request.method == 'POST':
        form = TournamentForm(request.POST, request.FILES, instance=tournament)
        if form.is_valid():
            form.save()
            messages.success(request, f'Turnering "{tournament.name}" er opdateret.')
            return redirect('tournament_detail', pk=tournament.pk)
    else:
        form = TournamentForm(instance=tournament)
    return render(request, 'tournaments/tournament_form.html', {'form': form, 'tournament': tournament})


@login_required
def tournament_delete(request, pk):
    tournament = get_object_or_404(Tournament, pk=pk, owner=request.user)
    if request.method == 'POST':
        if request.POST.get('confirm', '').strip() != 'SLET TURNERING':
            messages.error(request, 'Du skal skrive SLET TURNERING for at bekræfte.')
            return render(request, 'tournaments/tournament_confirm_delete.html', {'tournament': tournament})
        name = tournament.name
        tournament.delete()
        messages.success(request, f'Turnering "{name}" er slettet.')
        return redirect('tournament_list')
    return render(request, 'tournaments/tournament_confirm_delete.html', {'tournament': tournament})


@login_required
def tournament_export(request, pk):
    """Download a full JSON backup of a tournament."""
    from players.models import Player, Team as PlayerTeam
    tournament = get_object_or_404(Tournament, pk=pk, owner=request.user)

    division_qs = list(tournament.divisions.prefetch_related('teams__player1', 'teams__player2', 'seeds'))

    player_ids = set()
    team_ids = set()
    for division in division_qs:
        for team in division.teams.all():
            team_ids.add(team.pk)
            player_ids.add(team.player1_id)
            if team.player2_id:
                player_ids.add(team.player2_id)

    players = {p.pk: p for p in Player.objects.filter(pk__in=player_ids)}
    teams = {t.pk: t for t in PlayerTeam.objects.filter(pk__in=team_ids).select_related('player1', 'player2')}

    matches = list(
        Match.objects
        .filter(division__tournament=tournament)
        .select_related('division', 'team1', 'team2', 'winner')
        .order_by('match_number')
    )
    seeds = list(DivisionSeed.objects.filter(division__tournament=tournament))

    data = {
        "version": 1,
        "exported_at": datetime.utcnow().isoformat() + "Z",
        "tournament": {
            "name": tournament.name,
            "date": str(tournament.date),
            "division_model": tournament.division_model,
            "scoring_model": tournament.scoring_model,
            "single_match_duration": tournament.single_match_duration,
            "double_match_duration": tournament.double_match_duration,
            "player_break_time": tournament.player_break_time,
            "court_count": tournament.court_count,
            "start_time": str(tournament.start_time) if tournament.start_time else None,
            "schedule_locked": tournament.schedule_locked,
        },
        "players": [
            {
                "_id": p.pk,
                "name": p.name,
                "age": p.age,
                "division": p.division,
                "gender": p.gender,
            }
            for p in players.values()
        ],
        "teams": [
            {
                "_id": t.pk,
                "player1_id": t.player1_id,
                "player2_id": t.player2_id,
                "pair_type": t.pair_type,
                "division": t.division,
                "name": t.name,
            }
            for t in teams.values()
        ],
        "divisions": [
            {
                "_id": d.pk,
                "name": d.name,
                "discipline": d.discipline,
                "tournament_type": d.tournament_type,
                "group_count": d.group_count,
                "advance_count": d.advance_count,
                "schedule_priority": d.schedule_priority,
                "team_ids": list(d.teams.values_list('pk', flat=True)),
            }
            for d in division_qs
        ],
        "matches": [
            {
                "division_id": m.division_id,
                "team1_id": m.team1_id,
                "team2_id": m.team2_id,
                "winner_id": m.winner_id,
                "score": m.score,
                "match_round": m.match_round,
                "match_number": m.match_number,
                "bracket_slot": m.bracket_slot,
                "bracket_label": m.bracket_label,
                "status": m.status,
                "walkover": m.walkover,
                "scheduled_time": m.scheduled_time.isoformat() if m.scheduled_time else None,
                "court": m.court,
                "group_number": m.group_number,
                "phase": m.phase,
            }
            for m in matches
        ],
        "seeds": [
            {
                "division_id": s.division_id,
                "team_id": s.team_id,
                "seed_number": s.seed_number,
            }
            for s in seeds
        ],
    }

    filename = f"turnering_{tournament.pk}_{tournament.date}.json"
    response = HttpResponse(
        json.dumps(data, ensure_ascii=False, indent=2),
        content_type="application/json; charset=utf-8",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@login_required
def tournament_import(request):
    """Upload a JSON backup and recreate the tournament under the current user."""
    from players.models import Player, Team as PlayerTeam
    from django.utils.dateparse import parse_datetime, parse_time, parse_date

    if request.method != 'POST':
        return render(request, 'tournaments/tournament_import.html')

    upload = request.FILES.get('backup_file')
    if not upload:
        messages.error(request, 'Ingen fil valgt.')
        return render(request, 'tournaments/tournament_import.html')

    try:
        raw = upload.read().decode('utf-8-sig')  # handles BOM if present
        data = json.loads(raw)
    except Exception:
        messages.error(request, 'Filen kunne ikke læses som JSON.')
        return render(request, 'tournaments/tournament_import.html')

    if data.get('version') != 1:
        messages.error(request, 'Ukendt backup-format (version mangler eller er forkert).')
        return render(request, 'tournaments/tournament_import.html')

    td = data['tournament']
    tournament = Tournament.objects.create(
        owner=request.user,
        name=td['name'] + ' (gendannet)',
        date=parse_date(td['date']),
        division_model=td['division_model'],
        scoring_model=td['scoring_model'],
        single_match_duration=td['single_match_duration'],
        double_match_duration=td['double_match_duration'],
        player_break_time=td['player_break_time'],
        court_count=td['court_count'],
        start_time=parse_time(td['start_time']) if td.get('start_time') else None,
        schedule_locked=td.get('schedule_locked', False),
    )

    # Players: dedup by (name, gender, division) for this owner
    player_map = {}  # old_id → Player instance
    for pd in data.get('players', []):
        player, _ = Player.objects.get_or_create(
            owner=request.user,
            name=pd['name'],
            gender=pd['gender'],
            division=pd['division'],
            defaults={'age': pd.get('age', 0)},
        )
        player_map[pd['_id']] = player

    # Teams: dedup by (player1, player2)
    team_map = {}  # old_id → Team instance
    for ti in data.get('teams', []):
        p1 = player_map.get(ti['player1_id'])
        p2 = player_map.get(ti['player2_id']) if ti.get('player2_id') else None
        if not p1:
            continue
        if p2:
            team, _ = PlayerTeam.objects.get_or_create(
                player1=p1, player2=p2,
                defaults={
                    'pair_type': ti.get('pair_type'),
                    'division': ti.get('division'),
                    'name': ti.get('name'),
                },
            )
        else:
            team, _ = PlayerTeam.objects.get_or_create(
                player1=p1, player2=None,
                defaults={'name': p1.name},
            )
        team_map[ti['_id']] = team

    # Divisions
    division_map = {}  # old_id → Division instance
    for dd in data.get('divisions', []):
        division = Division.objects.create(
            tournament=tournament,
            name=dd['name'],
            discipline=dd['discipline'],
            tournament_type=dd['tournament_type'],
            group_count=dd.get('group_count', 2),
            advance_count=dd.get('advance_count', 2),
            schedule_priority=dd.get('schedule_priority', 5),
        )
        teams_for_div = [team_map[tid] for tid in dd.get('team_ids', []) if tid in team_map]
        division.teams.set(teams_for_div)
        division_map[dd['_id']] = division

    # Matches
    for md in data.get('matches', []):
        div = division_map.get(md['division_id'])
        if not div:
            continue
        scheduled_time = parse_datetime(md['scheduled_time']) if md.get('scheduled_time') else None
        Match.objects.create(
            division=div,
            team1=team_map.get(md['team1_id']) if md.get('team1_id') else None,
            team2=team_map.get(md['team2_id']) if md.get('team2_id') else None,
            winner=team_map.get(md['winner_id']) if md.get('winner_id') else None,
            score=md.get('score'),
            match_round=md.get('match_round', 1),
            match_number=md.get('match_number'),
            bracket_slot=md.get('bracket_slot'),
            bracket_label=md.get('bracket_label'),
            status=md.get('status', 'pending'),
            walkover=md.get('walkover', False),
            scheduled_time=scheduled_time,
            court=md.get('court'),
            group_number=md.get('group_number'),
            phase=md.get('phase', 'group'),
        )

    # Seeds
    for sd in data.get('seeds', []):
        div = division_map.get(sd['division_id'])
        team = team_map.get(sd['team_id'])
        if div and team:
            DivisionSeed.objects.get_or_create(
                division=div, team=team,
                defaults={'seed_number': sd['seed_number']},
            )

    messages.success(request, f'Turnering "{tournament.name}" er gendannet med {len(division_map)} rækker og {len(data.get("matches", []))} kampe.')
    return redirect('tournament_detail', pk=tournament.pk)


@login_required
def tournament_detail(request, pk):
    tournament = get_object_or_404(Tournament, pk=pk, owner=request.user)
    divisions = tournament.divisions.prefetch_related('teams', 'matches__team1', 'matches__team2', 'matches__winner', 'seeds')

    seed_lookup = _build_seed_lookup(tournament)

    def _seed_list(d):
        seeds_lkp = {team_pk: num for (div_pk, team_pk), num in seed_lookup.items() if div_pk == d.pk}
        return [(team, seeds_lkp.get(team.pk, '')) for team in d.teams.all().order_by('name')]

    def _group_teams(d):
        """Return {group_number: [team, ...]} from existing group-stage matches."""
        if d.tournament_type != 'playoff':
            return {}
        result = {}
        seen = {}  # group_num -> set of team pks already added
        for m in d.matches.filter(phase='group').select_related('team1', 'team2').order_by('group_number', 'match_round'):
            for team in (m.team1, m.team2):
                if team is None:
                    continue
                g = m.group_number or 1
                if g not in result:
                    result[g] = []
                    seen[g] = set()
                if team.pk not in seen[g]:
                    result[g].append(team)
                    seen[g].add(team.pk)
        return result

    def _player_items(d):
        """List of {player, checked} for single-discipline divisions."""
        if d.discipline != 'single':
            return []
        from players.models import Player as _P
        qs = _P.objects.order_by('name')
        if request.user:
            qs = qs.filter(owner=request.user)
        checked_pks = set(
            d.teams.filter(player2__isnull=True).values_list('player1_id', flat=True)
        )
        return [{'player': p, 'checked': p.pk in checked_pks} for p in qs]

    division_data = [
        {
            'division': d,
            'standings': compute_standings(d) if d.tournament_type == 'group' else [],
            'group_standings': compute_group_standings(d) if d.tournament_type == 'playoff' else [],
            'participants_form': get_participants_form(d, owner=request.user),
            'player_items': _player_items(d),
            'match_count': d.matches.count(),
            'pending_count': d.matches.filter(status='pending').count(),
            'completed_count': d.matches.filter(status='completed').count(),
            'bracket_data': get_bracket_data(d) if d.tournament_type in ('tree', 'playoff') else None,
            'seed_list': _seed_list(d),
            'seeds_dict': _seeds_dict_for_division(d, seed_lookup),
            'group_teams': _group_teams(d),
        }
        for d in divisions
    ]

    # Annotate prefetched match objects with seed display strings
    for dd in division_data:
        _apply_seed_labels(dd['division'].matches.all(), seed_lookup)

    # Annotate match objects with player status
    playing_pks, resting = get_busy_info()
    for dd in division_data:
        apply_status_to_matches(dd['division'].matches.all(), playing_pks, resting)
        # Also annotate standings rows with team status
        for row in dd['standings']:
            s, ru = _team_status(row['team'], playing_pks, resting)
            row['status'] = s
            row['rest_until'] = ru
        for _gnum, g_rows in dd['group_standings']:
            for row in g_rows:
                s, ru = _team_status(row['team'], playing_pks, resting)
                row['status'] = s
                row['rest_until'] = ru

    division_form = DivisionForm()
    from players.models import DivisionCategory
    player_division_choices = [
        (c, c) for c in
        DivisionCategory.objects.filter(owner=request.user).values_list('name', flat=True)
    ]

    total_matches    = sum(dd['match_count']     for dd in division_data)
    completed_matches = sum(dd['completed_count'] for dd in division_data)
    pending_matches  = sum(dd['pending_count']    for dd in division_data)

    return render(request, 'tournaments/tournament_detail.html', {
        'tournament': tournament,
        'division_data': division_data,
        'division_form': division_form,
        'player_division_choices': player_division_choices,
        'total_matches': total_matches,
        'completed_matches': completed_matches,
        'pending_matches': pending_matches,
    })


@login_required
def division_create(request, tournament_pk):
    tournament = get_object_or_404(Tournament, pk=tournament_pk, owner=request.user)
    if request.method == 'POST':
        form = DivisionForm(request.POST)
        if form.is_valid():
            division = form.save(commit=False)
            division.tournament = tournament
            division.save()
            messages.success(request, f'Division "{division.name}" er oprettet.')
    return redirect('tournament_detail', pk=tournament_pk)


@login_required
def division_update_teams(request, pk):
    division = get_object_or_404(Division, pk=pk, tournament__owner=request.user)
    if request.method == 'POST':
        form = get_participants_form(division, request.POST, owner=request.user)
        if form.is_valid():
            if division.discipline == 'single':
                teams = []
                for player in form.cleaned_data['players']:
                    team, _ = Team.objects.get_or_create(
                        player1=player, player2=None,
                        defaults={'name': player.name},
                    )
                    teams.append(team)
                division.teams.set(teams)
                messages.success(request, f'Spillere i "{division.name}" er opdateret.')
            else:
                division.teams.set(form.cleaned_data['pairs'])
                messages.success(request, f'Par i "{division.name}" er opdateret.')
    return redirect('tournament_detail', pk=division.tournament.pk)


@login_required
def division_update_seeds(request, pk):
    division = get_object_or_404(Division, pk=pk, tournament__owner=request.user)
    if request.method == 'POST':
        DivisionSeed.objects.filter(division=division).delete()
        seen = set()
        for team in division.teams.all():
            raw = request.POST.get(f'seed_{team.pk}', '').strip()
            if raw:
                try:
                    seed_num = int(raw)
                    if seed_num > 0 and seed_num not in seen:
                        DivisionSeed.objects.create(division=division, team=team, seed_number=seed_num)
                        seen.add(seed_num)
                except ValueError:
                    pass
        messages.success(request, f'Seedning for "{division.name}" er gemt.')
    return redirect('tournament_detail', pk=division.tournament.pk)


@login_required
def division_reassign_groups(request, pk):
    """
    Accept a JSON payload with the new group membership and regenerate
    all group-stage (and playoff bracket) matches.
    Only allowed before any result has been recorded.
    """
    import json
    division = get_object_or_404(Division, pk=pk, tournament__owner=request.user)

    if request.method != 'POST':
        return redirect('tournament_detail', pk=division.tournament.pk)

    if division.tournament_type != 'playoff':
        messages.error(request, 'Gruppeomfordeling er kun mulig for divisioner med gruppespil og slutspil.')
        return redirect('tournament_detail', pk=division.tournament.pk)

    if division.tournament.schedule_locked:
        messages.error(request, 'Spilleplanen er låst og kan ikke ændres.')
        return redirect('tournament_detail', pk=division.tournament.pk)

    if division.matches.filter(status='completed').exists():
        messages.error(request, 'Kan ikke omfordele grupper – der er allerede registrerede resultater.')
        return redirect('tournament_detail', pk=division.tournament.pk)

    try:
        raw = json.loads(request.POST.get('groups', '{}'))
        # raw = {"1": [pk, pk, ...], "2": [pk, pk, ...], ...}
        groups_by_num = {int(k): [int(x) for x in v] for k, v in raw.items()}
    except (ValueError, TypeError, AttributeError):
        messages.error(request, 'Ugyldig data.')
        return redirect('tournament_detail', pk=division.tournament.pk)

    # Validate: every division team appears in exactly one group
    division_team_pks = set(division.teams.values_list('pk', flat=True))
    submitted_pks = {pk for pks in groups_by_num.values() for pk in pks}
    if submitted_pks != division_team_pks:
        messages.error(request, 'Grupper indeholder ikke præcis de rigtige hold.')
        return redirect('tournament_detail', pk=division.tournament.pk)

    # Build ordered list of Team objects per group
    team_map = {t.pk: t for t in division.teams.all()}
    groups = [
        [team_map[pk] for pk in groups_by_num[gnum]]
        for gnum in sorted(groups_by_num.keys())
    ]

    matches = regenerate_playoff_with_groups(division, groups)

    if matches:
        tournament_matches = Match.objects.filter(division__tournament=division.tournament)
        current_max = tournament_matches.exclude(
            pk__in=[m.pk for m in matches]
        ).aggregate(Max('match_number'))['match_number__max'] or 0
        for i, match in enumerate(matches, start=current_max + 1):
            match.match_number = i
            match.save(update_fields=['match_number'])
        messages.success(request, f'Gruppefordeling i "{division.name}" er gemt og kampprogram er regenereret.')
    else:
        messages.warning(request, 'Ingen kampe genereret.')

    return redirect('tournament_detail', pk=division.tournament.pk)


@login_required
def division_delete(request, pk):
    division = get_object_or_404(Division, pk=pk, tournament__owner=request.user)
    tournament_pk = division.tournament.pk
    if request.method == 'POST':
        name = division.name
        division.delete()
        messages.success(request, f'Række "{name}" er slettet.')
        return redirect('tournament_detail', pk=tournament_pk)
    return render(request, 'players/player_confirm_delete.html', {
        'object': division.name,
        'type': 'række',
    })


@login_required
def division_set_priority(request, pk):
    """POST: update schedule_priority for a division."""
    division = get_object_or_404(Division, pk=pk, tournament__owner=request.user)
    if request.method == 'POST':
        try:
            priority = max(1, min(10, int(request.POST.get('schedule_priority', 5))))
            division.schedule_priority = priority
            division.save(update_fields=['schedule_priority'])
        except (ValueError, TypeError):
            pass
    return redirect('tournament_detail', pk=division.tournament.pk)


@login_required
def division_generate_schedule(request, pk):
    division = get_object_or_404(Division, pk=pk, tournament__owner=request.user)
    if request.method == 'POST':
        if division.tournament.schedule_locked:
            messages.error(request, 'Spilleplanen er låst og kan ikke ændres.')
            return redirect('tournament_detail', pk=division.tournament.pk)
        matches = generate_schedule(division)
        if matches:
            # Assign sequential match numbers to ALL matches immediately
            # (playoff bracket matches are visible in programs but scheduled after group stage)
            tournament_matches = Match.objects.filter(division__tournament=division.tournament)
            current_max = tournament_matches.exclude(
                pk__in=[m.pk for m in matches]
            ).aggregate(Max('match_number'))['match_number__max'] or 0
            for i, match in enumerate(matches, start=current_max + 1):
                match.match_number = i
                match.save(update_fields=['match_number'])

            # For bracket divisions: update placeholder labels to use actual match numbers
            if division.tournament_type == 'tree':
                slot_to_num = {
                    (m.match_round, m.bracket_slot): m.match_number
                    for m in matches if m.bracket_slot is not None
                }
                for match in matches:
                    if match.bracket_label is not None:
                        r = match.match_round
                        s = match.bracket_slot
                        t1_label = (
                            match.team1.name if match.team1
                            else f"V-kamp #{slot_to_num.get((r-1, 2*s-1), '?')}"
                        )
                        t2_label = (
                            match.team2.name if match.team2
                            else f"V-kamp #{slot_to_num.get((r-1, 2*s), '?')}"
                        )
                        match.bracket_label = f"{t1_label} vs {t2_label}"
                        match.save(update_fields=['bracket_label'])

        group_count = sum(1 for m in matches if getattr(m, 'phase', 'group') == 'group')
        playoff_count = sum(1 for m in matches if getattr(m, 'phase', 'group') == 'playoff' and not (m.team1 is None and m.team2 is None and m.score == 'Bye'))
        placeholder_count = sum(1 for m in matches if m.team1 is None and m.phase != 'playoff')
        if division.tournament_type == 'playoff':
            messages.success(
                request,
                f'Kampprogram genereret: {group_count} gruppekampe fordelt i {division.group_count} grupper, '
                f'+ {playoff_count} slutspilskampe (planlægges efter gruppespillet i spilleplanen).'
            )
        elif placeholder_count:
            messages.success(
                request,
                f'Kampprogram genereret med {len(matches) - placeholder_count} kampe '
                f'(+ {placeholder_count} finalekampe reserveret til bracket).'
            )
        else:
            messages.success(request, f'Kampprogram genereret med {len(matches)} kampe.')
    return redirect('tournament_detail', pk=division.tournament.pk)


@login_required
def match_record_result(request, pk):
    match = get_object_or_404(Match, pk=pk, division__tournament__owner=request.user)
    next_url = request.GET.get('next') or request.POST.get('next') or ''
    if request.method == 'POST':
        form = MatchResultForm(request.POST, instance=match)
        if form.is_valid():
            form.save()
            match.refresh_from_db()
            if match.status == 'completed':
                set_player_rest(match)
            advance_bracket(match)
            messages.success(request, 'Resultat er gemt.')
            if next_url:
                return redirect(next_url)
            return redirect('tournament_detail', pk=match.division.tournament.pk)
    else:
        form = MatchResultForm(instance=match)
    return render(request, 'tournaments/match_result_form.html', {'form': form, 'match': match, 'next_url': next_url})


WALKOVER_SCORE = '21-0, 21-0'


@login_required
def match_start(request, pk):
    match = get_object_or_404(Match, pk=pk, division__tournament__owner=request.user)
    next_url = request.POST.get('next') or ''
    if request.method == 'POST' and match.status == 'pending':
        errors = check_match_startable(match)
        if errors:
            messages.error(request, 'Kan ikke starte kamp: ' + ' · '.join(errors))
        else:
            match.status = 'in_progress'
            match.save(update_fields=['status'])
            messages.success(request, f'Kamp #{match.match_number or match.pk} er nu i gang.')
    if next_url:
        return redirect(next_url)
    return redirect('tournament_detail', pk=match.division.tournament.pk)


@login_required
def match_walkover(request, pk):
    match = get_object_or_404(Match, pk=pk, division__tournament__owner=request.user)
    next_url = request.GET.get('next') or request.POST.get('next') or ''
    if request.method == 'POST':
        form = WalkoverForm(request.POST, match=match)
        if form.is_valid():
            match.winner = form.cleaned_data['winner']
            match.score = WALKOVER_SCORE
            match.status = 'completed'
            match.walkover = True
            match.save()
            set_player_rest(match)
            advance_bracket(match)
            messages.success(request, f'Walk-over registreret – {match.winner} vinder.')
            if next_url:
                return redirect(next_url)
            return redirect('tournament_detail', pk=match.division.tournament.pk)
    else:
        form = WalkoverForm(match=match)
    return render(request, 'tournaments/match_walkover_form.html', {'form': form, 'match': match, 'next_url': next_url})


@login_required
def tournament_scoresheet(request, pk):
    tournament = get_object_or_404(Tournament, pk=pk, owner=request.user)
    matches = (
        Match.objects
        .filter(division__tournament=tournament)
        .exclude(match_number=None)
        .exclude(walkover=True)
        .select_related('team1', 'team2', 'division')
        .order_by('match_number')
    )
    return render(request, 'tournaments/scoresheet.html', {
        'tournament': tournament,
        'matches': matches,
        'title_suffix': None,
    })


@login_required
def tournament_wallchart(request, pk):
    """Printable wall-chart: one section per division, matches listed with blank result boxes."""
    tournament = get_object_or_404(Tournament, pk=pk, owner=request.user)

    divisions = list(tournament.divisions.prefetch_related('teams', 'seeds').order_by('schedule_priority', 'name'))
    seed_lookup = _build_seed_lookup(tournament)

    wallchart_data = []
    for div in divisions:
        matches = list(
            Match.objects
            .filter(division=div)
            .exclude(match_number=None)
            .exclude(walkover=True)
            .select_related('team1', 'team2')
            .order_by('scheduled_time', 'match_number')
        )
        _apply_seed_labels(matches, seed_lookup)
        slot_to_num = {
            (m.match_round, m.bracket_slot): m.match_number
            for m in matches
            if m.bracket_slot is not None
        }
        for m in matches:
            if m.team1 is None and m.bracket_slot is not None:
                r, s = m.match_round, m.bracket_slot
                m.feeder1_num = slot_to_num.get((r - 1, 2 * s - 1))
                m.feeder2_num = slot_to_num.get((r - 1, 2 * s))
            else:
                m.feeder1_num = m.feeder2_num = None
        wallchart_data.append({
            'division': div,
            'matches': matches,
            'seeds_dict': _seeds_dict_for_division(div, seed_lookup),
        })

    return render(request, 'tournaments/tournament_wallchart_print.html', {
        'tournament': tournament,
        'wallchart_data': wallchart_data,
    })


@login_required
def tournament_court_signs(request, pk):
    """Printable A3 court-number signs — one page per court."""
    tournament = get_object_or_404(Tournament, pk=pk, owner=request.user)
    courts = list(range(1, tournament.court_count + 1))
    return render(request, 'tournaments/tournament_court_signs_print.html', {
        'tournament': tournament,
        'courts': courts,
    })


@login_required
def tournament_schedule_print(request, pk):
    """Print-venlig tidssorteret spilleplan for hele turneringen (én A4-tabel pr. bane/tidspunkt)."""
    tournament = get_object_or_404(Tournament, pk=pk, owner=request.user)
    matches = list(
        Match.objects
        .filter(division__tournament=tournament, scheduled_time__isnull=False)
        .exclude(match_number=None)
        .select_related('division', 'team1', 'team2', 'winner')
        .order_by('scheduled_time', 'court', 'match_number')
    )
    seed_lookup = _build_seed_lookup(tournament)
    _apply_seed_labels(matches, seed_lookup)

    # Build per-division lookup: (division_id, round, bracket_slot) → match_number
    # so placeholder matches can show "Vinder kamp X vs vinder kamp Y"
    all_div_matches = list(
        Match.objects
        .filter(division__tournament=tournament)
        .exclude(match_number=None)
        .values('id', 'division_id', 'match_round', 'bracket_slot', 'match_number')
    )
    slot_to_num = {
        (m['division_id'], m['match_round'], m['bracket_slot']): m['match_number']
        for m in all_div_matches
        if m['bracket_slot'] is not None and m['match_number'] is not None
    }
    for m in matches:
        if m.team1 is None and m.bracket_slot is not None:
            prev_round = m.match_round - 1
            m.feeder1_num = slot_to_num.get((m.division_id, prev_round, 2 * m.bracket_slot - 1))
            m.feeder2_num = slot_to_num.get((m.division_id, prev_round, 2 * m.bracket_slot))
        else:
            m.feeder1_num = None
            m.feeder2_num = None

    return render(request, 'tournaments/tournament_schedule_print.html', {
        'tournament': tournament,
        'matches': matches,
    })


@login_required
def tournament_program_print(request, pk):
    """Print-venligt samlet kampprogram for hele turneringen, division for division."""
    tournament = get_object_or_404(Tournament, pk=pk, owner=request.user)
    divisions = tournament.divisions.prefetch_related(
        'teams', 'teams__player1', 'teams__player2',
        'matches__team1', 'matches__team2',
    ).order_by('name')

    seed_lookup = _build_seed_lookup(tournament)

    division_data = []
    for division in divisions:
        teams = list(division.teams.select_related('player1', 'player2').order_by('name'))
        matches = list(
            division.matches
            .exclude(match_number=None)
            .filter(
                Q(team1__isnull=False, team2__isnull=False) |
                Q(bracket_label__isnull=False)
            )
            .select_related('team1', 'team2')
            .order_by('scheduled_time', 'match_number')
        )
        _apply_seed_labels(matches, seed_lookup)

        # Build lookup: (round, bracket_slot) → match_number for feeder annotations
        slot_to_num = {
            (m.match_round, m.bracket_slot): m.match_number
            for m in matches
            if m.bracket_slot is not None and m.match_number is not None
        }
        for m in matches:
            if m.team1 is None and m.bracket_slot is not None:
                prev_round = m.match_round - 1
                feeder1 = slot_to_num.get((prev_round, 2 * m.bracket_slot - 1))
                feeder2 = slot_to_num.get((prev_round, 2 * m.bracket_slot))
                m.feeder1_num = feeder1
                m.feeder2_num = feeder2
            else:
                m.feeder1_num = None
                m.feeder2_num = None

        # Build groups for playoff type (teams + matches per group)
        groups = []
        if division.tournament_type == 'playoff':
            group_teams_dict = {}
            seen = {}
            for m in division.matches.filter(phase='group').select_related('team1', 'team2').order_by('group_number', 'match_round'):
                for team in (m.team1, m.team2):
                    if team is None:
                        continue
                    g = m.group_number or 1
                    if g not in group_teams_dict:
                        group_teams_dict[g] = []
                        seen[g] = set()
                    if team.pk not in seen[g]:
                        group_teams_dict[g].append(team)
                        seen[g].add(team.pk)
            group_matches_dict = {}
            for m in matches:
                if m.phase != 'group':
                    continue
                g = m.group_number or 1
                if g not in group_matches_dict:
                    group_matches_dict[g] = []
                group_matches_dict[g].append(m)
            for g_num in sorted(group_teams_dict.keys()):
                groups.append({
                    'number': g_num,
                    'teams': group_teams_dict[g_num],
                    'matches': group_matches_dict.get(g_num, []),
                })

        # Bracket data for tree / playoff types
        bracket_data = get_bracket_data(division) if division.tournament_type in ('tree', 'playoff') else None

        # Playoff bracket-phase matches (same objects from matches list, already annotated)
        playoff_matches = [m for m in matches if m.phase == 'playoff'] if division.tournament_type == 'playoff' else []

        division_data.append({
            'division': division,
            'teams': teams,
            'matches': matches,
            'seeds_dict': _seeds_dict_for_division(division, seed_lookup),
            'groups': groups,
            'bracket_data': bracket_data,
            'playoff_matches': playoff_matches,
        })
    return render(request, 'tournaments/tournament_program_print.html', {
        'tournament': tournament,
        'division_data': division_data,
    })


@login_required
def division_scoresheet(request, pk):
    division = get_object_or_404(Division, pk=pk, tournament__owner=request.user)
    matches = (
        Match.objects
        .filter(division=division)
        .exclude(match_number=None)
        .exclude(walkover=True)
        .select_related('team1', 'team2', 'division')
        .order_by('match_number')
    )
    return render(request, 'tournaments/scoresheet.html', {
        'tournament': division.tournament,
        'matches': matches,
        'title_suffix': division.name,
    })


@login_required
def tournament_bigscreen(request, pk):
    """Storskærmsvisning – viser de 5 næste ikke-startede kampe."""
    tournament = get_object_or_404(Tournament, pk=pk, owner=request.user)
    matches = list(
        Match.objects
        .filter(division__tournament=tournament, scheduled_time__isnull=False, status='pending')
        .exclude(team1__isnull=True, team2__isnull=True, bracket_label__isnull=False)
        .select_related('division', 'team1', 'team2')
        .order_by('scheduled_time', 'court')
    )[:5]
    seed_lookup = _build_seed_lookup(tournament)
    _apply_seed_labels(matches, seed_lookup)
    playing_pks, resting = get_busy_info()
    apply_status_to_matches(matches, playing_pks, resting)
    return render(request, 'tournaments/bigscreen.html', {
        'tournament': tournament,
        'matches': matches,
    })


@login_required
def tournament_run(request, pk):
    """Afviklingsside – fokuseret visning til turneringsdagen."""
    tournament = get_object_or_404(Tournament, pk=pk, owner=request.user)

    divisions = tournament.divisions.prefetch_related(
        'teams', 'matches__team1', 'matches__team2', 'matches__winner', 'seeds',
    ).order_by('schedule_priority', 'name')

    seed_lookup = _build_seed_lookup(tournament)
    playing_pks, resting = get_busy_info()

    division_data = []
    for division in divisions:
        # Standings
        if division.tournament_type == 'group':
            standings = compute_standings(division)
            group_standings = []
        elif division.tournament_type == 'playoff':
            standings = []
            group_standings = compute_group_standings(division)
        else:
            standings = []
            group_standings = []

        # Annotate standings rows with team status
        for row in standings:
            s, ru = _team_status(row['team'], playing_pks, resting)
            row['status'] = s
            row['rest_until'] = ru
        for _gnum, g_rows in group_standings:
            for row in g_rows:
                s, ru = _team_status(row['team'], playing_pks, resting)
                row['status'] = s
                row['rest_until'] = ru

        # All division matches (with time/number ordering); exclude auto-completed byes
        all_matches = list(
            division.matches
            .exclude(match_number=None)
            .exclude(team2__isnull=True, score='Bye')
            .select_related('team1', 'team2', 'winner')
            .order_by('scheduled_time', 'match_number')
        )
        _apply_seed_labels(all_matches, seed_lookup)
        apply_status_to_matches(all_matches, playing_pks, resting)

        # Bracket data for tree/playoff
        bracket_data = get_bracket_data(division) if division.tournament_type in ('tree', 'playoff') else None

        division_data.append({
            'division': division,
            'standings': standings,
            'group_standings': group_standings,
            'bracket_data': bracket_data,
            'seeds_dict': _seeds_dict_for_division(division, seed_lookup),
            'matches': all_matches,
            'match_count': len(all_matches),
            'pending_count': sum(1 for m in all_matches if m.status == 'pending'),
            'in_progress_count': sum(1 for m in all_matches if m.status == 'in_progress'),
            'completed_count': sum(1 for m in all_matches if m.status == 'completed'),
        })

    # Next 5 matches (same logic as bigscreen)
    next_matches = list(
        Match.objects
        .filter(division__tournament=tournament, scheduled_time__isnull=False, status='pending')
        .exclude(team1__isnull=True, team2__isnull=True, bracket_label__isnull=False)
        .select_related('division', 'team1', 'team2')
        .order_by('scheduled_time', 'court')
    )[:5]
    _apply_seed_labels(next_matches, seed_lookup)
    apply_status_to_matches(next_matches, playing_pks, resting)

    # Matches currently in progress
    active_matches = list(
        Match.objects
        .filter(division__tournament=tournament, status='in_progress')
        .select_related('division', 'team1', 'team2')
        .order_by('scheduled_time', 'match_number')
    )
    _apply_seed_labels(active_matches, seed_lookup)

    # Summary counts
    total_matches = sum(dd['match_count'] for dd in division_data)
    completed_matches = sum(dd['completed_count'] for dd in division_data)
    in_progress_matches = sum(dd['in_progress_count'] for dd in division_data)

    return render(request, 'tournaments/tournament_run.html', {
        'tournament': tournament,
        'division_data': division_data,
        'next_matches': next_matches,
        'active_matches': active_matches,
        'total_matches': total_matches,
        'completed_matches': completed_matches,
        'in_progress_matches': in_progress_matches,
    })


@login_required
def tournament_schedule(request, pk):
    from django.utils import timezone
    tournament = get_object_or_404(Tournament, pk=pk, owner=request.user)
    matches = list(
        Match.objects
        .filter(division__tournament=tournament, scheduled_time__isnull=False)
        .select_related('division', 'team1', 'team2', 'winner')
        .order_by('scheduled_time', 'court')
    )
    seed_lookup = _build_seed_lookup(tournament)
    _apply_seed_labels(matches, seed_lookup)
    playing_pks, resting = get_busy_info()
    apply_status_to_matches(matches, playing_pks, resting)
    has_unscheduled = (
        Match.objects
        .filter(division__tournament=tournament, scheduled_time__isnull=True)
        .exclude(match_number=None)
        .exists()
    )
    now = timezone.now()
    return render(request, 'tournaments/schedule.html', {
        'tournament': tournament,
        'matches': matches,
        'now': now,
        'has_unscheduled': has_unscheduled,
    })


@login_required
def tournament_generate_time_schedule(request, pk):
    tournament = get_object_or_404(Tournament, pk=pk, owner=request.user)
    if request.method == 'POST':
        if tournament.schedule_locked:
            messages.error(request, 'Spilleplanen er låst og kan ikke ændres.')
        elif not tournament.start_time:
            messages.error(request, 'Sæt et starttidspunkt på turneringen før du genererer spilleplanen.')
        else:
            count = generate_time_schedule(tournament)
            if count:
                messages.success(request, f'Spilleplan genereret for {count} kampe.')
            else:
                messages.warning(request, 'Ingen kampe at planlægge. Generer kampprogram for divisionerne først.')
    return redirect('tournament_schedule', pk=pk)


@login_required
def tournament_toggle_lock(request, pk):
    tournament = get_object_or_404(Tournament, pk=pk, owner=request.user)
    if request.method == 'POST':
        tournament.schedule_locked = not tournament.schedule_locked
        tournament.save(update_fields=['schedule_locked'])
        if tournament.schedule_locked:
            messages.success(request, 'Spilleplanen er nu låst.')
        else:
            messages.success(request, 'Spilleplanen er nu låst op.')
    return redirect('tournament_schedule', pk=pk)


@login_required
def tournament_reset_schedule(request, pk):
    """GET: confirmation page. POST: delete all matches if confirmed."""
    tournament = get_object_or_404(Tournament, pk=pk, owner=request.user)
    if request.method == 'POST':
        if request.POST.get('confirm', '').strip() != 'NULSTIL KAMPPROGRAM':
            messages.error(request, 'Du skal skrive NULSTIL KAMPPROGRAM for at bekræfte.')
            return render(request, 'tournaments/tournament_confirm_reset.html', {'tournament': tournament})
        Match.objects.filter(division__tournament=tournament).delete()
        if tournament.schedule_locked:
            tournament.schedule_locked = False
            tournament.save(update_fields=['schedule_locked'])
        messages.success(request, 'Alle kampe er slettet og kampnummer-tæller er nulstillet.')
        return redirect('tournament_detail', pk=pk)
    return render(request, 'tournaments/tournament_confirm_reset.html', {'tournament': tournament})


# ---------------------------------------------------------------------------
# Manual schedule editor
# ---------------------------------------------------------------------------

def _match_duration_td(match, tournament):
    minutes = (
        tournament.single_match_duration
        if match.division.discipline == 'single'
        else tournament.double_match_duration
    )
    return timedelta(minutes=minutes)


@login_required
def schedule_editor(request, pk):
    """Render the manual schedule editor grid."""
    tournament = get_object_or_404(Tournament, pk=pk, owner=request.user)

    slot_interval = max(5, min(120, int(request.GET.get('interval', 30))))

    scheduled = list(
        Match.objects
        .filter(division__tournament=tournament, scheduled_time__isnull=False)
        .exclude(match_number=None)
        .select_related('division', 'team1', 'team2')
        .order_by('scheduled_time', 'court')
    )
    unscheduled_count = (
        Match.objects
        .filter(division__tournament=tournament, scheduled_time__isnull=True)
        .exclude(match_number=None)
        .count()
    )

    # Build grid: {slot_str: {court_str: match}}
    # Slots are derived from tournament.start_time; show from first to last match + buffer
    slots = []
    grid = {}   # slot_label → {court: match}

    if tournament.start_time:
        naive_start = datetime.combine(tournament.date, tournament.start_time)
        start_dt = timezone.make_aware(naive_start) if timezone.is_naive(naive_start) else naive_start

        # Determine how many slots to show
        if scheduled:
            last_end = max(
                m.scheduled_time + _match_duration_td(m, tournament) for m in scheduled
            )
            total_minutes = int((last_end - start_dt).total_seconds() / 60) + slot_interval * 4
        else:
            total_minutes = slot_interval * 20  # show 20 empty slots by default

        n_slots = max(4, (total_minutes + slot_interval - 1) // slot_interval)

        for i in range(n_slots):
            slot_dt = start_dt + timedelta(minutes=i * slot_interval)
            label = slot_dt.strftime("%H:%M")
            slots.append(label)
            grid[label] = {str(c): None for c in range(1, tournament.court_count + 1)}

        # Place scheduled matches into the nearest slot row
        for m in scheduled:
            offset_min = int((m.scheduled_time - start_dt).total_seconds() / 60)
            slot_idx = round(offset_min / slot_interval)
            slot_idx = max(0, min(len(slots) - 1, slot_idx))
            court = m.court or '1'
            label = slots[slot_idx]
            if court not in grid[label]:
                grid[label][court] = m
            elif grid[label][court] is None:
                grid[label][court] = m
            else:
                # Court collision in same slot: add to a spill-over slot if available
                for j in range(slot_idx + 1, len(slots)):
                    alt_label = slots[j]
                    if grid[alt_label].get(court) is None:
                        grid[alt_label][court] = m
                        break

    courts = [str(c) for c in range(1, tournament.court_count + 1)]

    return render(request, 'tournaments/schedule_editor.html', {
        'tournament': tournament,
        'slots': slots,
        'courts': courts,
        'grid': grid,
        'unscheduled_count': unscheduled_count,
        'slot_interval': slot_interval,
    })


@login_required
def schedule_suggestions(request, pk):
    """
    GET ?time=HH:MM&court=1&interval=30
    Returns JSON list of unscheduled matches that can start at the given slot
    without causing player conflicts or court collisions.
    """
    tournament = get_object_or_404(Tournament, pk=pk, owner=request.user)
    time_str = request.GET.get('time', '')
    court_str = request.GET.get('court', '')
    try:
        slot_interval = max(5, int(request.GET.get('interval', 30)))
        naive_dt = datetime.combine(tournament.date, datetime.strptime(time_str, "%H:%M").time())
        slot_dt = timezone.make_aware(naive_dt) if timezone.is_naive(naive_dt) else naive_dt
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Invalid time'}, status=400)

    break_td = timedelta(minutes=tournament.player_break_time)

    # All currently scheduled matches → build player & court intervals
    scheduled = list(
        Match.objects
        .filter(division__tournament=tournament, scheduled_time__isnull=False)
        .select_related('division', 'team1__player1', 'team1__player2',
                        'team2__player1', 'team2__player2')
    )

    player_intervals = {}  # player_pk → [(busy_start, busy_end)]
    court_intervals = {}   # court_str → [(start, end)]

    for m in scheduled:
        dur = _match_duration_td(m, tournament)
        m_start = m.scheduled_time
        m_end = m_start + dur
        # Include break buffer around each match for player checks
        for team in (m.team1, m.team2):
            if team is None:
                continue
            for p_id in filter(None, [team.player1_id, getattr(team, 'player2_id', None)]):
                player_intervals.setdefault(p_id, []).append(
                    (m_start - break_td, m_end + break_td)
                )
        if m.court:
            court_intervals.setdefault(m.court, []).append((m_start, m_end))

    # Unscheduled matches (real matches with two teams assigned, not byes)
    unscheduled = list(
        Match.objects
        .filter(division__tournament=tournament, scheduled_time__isnull=True)
        .exclude(match_number=None)
        .select_related('division', 'team1__player1', 'team1__player2',
                        'team2__player1', 'team2__player2')
        .order_by('division__schedule_priority', 'division__name', 'match_round', 'match_number')
    )

    suggestions = []
    for m in unscheduled:
        dur = _match_duration_td(m, tournament)
        slot_end = slot_dt + dur

        # Court conflict check
        if court_str:
            if any(cs < slot_end and ce > slot_dt
                   for cs, ce in court_intervals.get(court_str, [])):
                continue

        # Player conflict check (includes break buffer)
        conflict = False
        players = []
        for team in (m.team1, m.team2):
            if team is None:
                continue
            for p_id in filter(None, [team.player1_id, getattr(team, 'player2_id', None)]):
                players.append(p_id)

        for p_id in players:
            if any(ps < slot_end + break_td and pe > slot_dt - break_td
                   for ps, pe in player_intervals.get(p_id, [])):
                conflict = True
                break
        if conflict:
            continue

        suggestions.append({
            'id': m.id,
            'match_number': m.match_number,
            'division': m.division.name,
            'priority': m.division.schedule_priority,
            'discipline': m.division.discipline,
            'team1': m.team1.name if m.team1 else (m.bracket_label or 'TBD'),
            'team2': m.team2.name if m.team2 else 'TBD',
            'phase': m.phase,
            'round': m.match_round,
        })

    return JsonResponse({'suggestions': suggestions, 'slot': time_str, 'court': court_str})


@login_required
@require_POST
def schedule_assign(request, pk):
    """POST: assign a match to a time slot + court."""
    tournament = get_object_or_404(Tournament, pk=pk, owner=request.user)
    if tournament.schedule_locked:
        return JsonResponse({'error': 'Spilleplanen er låst.'}, status=403)

    try:
        data = json.loads(request.body)
        match_id = int(data['match_id'])
        time_str = data['time']      # "HH:MM"
        court_str = str(data['court'])
        naive_dt = datetime.combine(tournament.date, datetime.strptime(time_str, "%H:%M").time())
        slot_dt = timezone.make_aware(naive_dt) if timezone.is_naive(naive_dt) else naive_dt
    except (KeyError, ValueError, TypeError):
        return JsonResponse({'error': 'Ugyldige data.'}, status=400)

    match = get_object_or_404(Match, pk=match_id, division__tournament=tournament)
    match.scheduled_time = slot_dt
    match.court = court_str
    match.save(update_fields=['scheduled_time', 'court'])

    return JsonResponse({
        'ok': True,
        'match_number': match.match_number,
        'division': match.division.name,
        'team1': match.team1.name if match.team1 else (match.bracket_label or 'TBD'),
        'team2': match.team2.name if match.team2 else 'TBD',
    })


@login_required
@require_POST
def schedule_unassign(request, pk):
    """POST: remove a match from its time slot."""
    tournament = get_object_or_404(Tournament, pk=pk, owner=request.user)
    if tournament.schedule_locked:
        return JsonResponse({'error': 'Spilleplanen er låst.'}, status=403)

    try:
        data = json.loads(request.body)
        match_id = int(data['match_id'])
    except (KeyError, ValueError, TypeError):
        return JsonResponse({'error': 'Ugyldige data.'}, status=400)

    match = get_object_or_404(Match, pk=match_id, division__tournament=tournament)
    match.scheduled_time = None
    match.court = None
    match.save(update_fields=['scheduled_time', 'court'])

    return JsonResponse({'ok': True})


@login_required
@require_POST
def schedule_clear(request, pk):
    """POST: clear scheduled_time and court from all matches (keeps matches intact)."""
    tournament = get_object_or_404(Tournament, pk=pk, owner=request.user)
    if tournament.schedule_locked:
        return JsonResponse({'error': 'Spilleplanen er låst.'}, status=403)

    count = (
        Match.objects
        .filter(division__tournament=tournament, scheduled_time__isnull=False)
        .update(scheduled_time=None, court=None)
    )
    return JsonResponse({'ok': True, 'cleared': count})


@login_required
@require_POST
def tournament_renumber_matches(request, pk):
    """
    POST: Re-assign consecutive match_numbers starting from 1 across the whole
    tournament, ordered by scheduled_time / division priority / match_round.
    Does NOT change scheduled_time, court or any other field.
    """
    tournament = get_object_or_404(Tournament, pk=pk, owner=request.user)

    matches = list(
        Match.objects
        .filter(division__tournament=tournament)
        .exclude(match_number=None)
        .order_by(
            'division__schedule_priority',
            'scheduled_time',
            'match_round',
            'division',
            'match_number',
        )
    )

    for i, match in enumerate(matches, start=1):
        match.match_number = i

    Match.objects.bulk_update(matches, ['match_number'])
    messages.success(request, f'Kampnumre genberegnet – {len(matches)} kampe nummereret fra 1.')
    return redirect('tournament_detail', pk=pk)
