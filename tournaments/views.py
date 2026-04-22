from django.db.models import Max
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
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
        name = tournament.name
        tournament.delete()
        messages.success(request, f'Turnering "{name}" er slettet.')
        return redirect('tournament_list')
    return render(request, 'tournaments/tournament_confirm_delete.html', {'tournament': tournament})


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

    division_data = [
        {
            'division': d,
            'standings': compute_standings(d) if d.tournament_type == 'group' else [],
            'group_standings': compute_group_standings(d) if d.tournament_type == 'playoff' else [],
            'participants_form': get_participants_form(d, owner=request.user),
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
    return render(request, 'tournaments/tournament_detail.html', {
        'tournament': tournament,
        'division_data': division_data,
        'division_form': division_form,
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
        messages.success(request, f'Division "{name}" er slettet.')
        return redirect('tournament_detail', pk=tournament_pk)
    return render(request, 'players/player_confirm_delete.html', {
        'object': division.name,
        'type': 'division',
    })


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
    if request.method == 'POST':
        form = MatchResultForm(request.POST, instance=match)
        if form.is_valid():
            form.save()
            match.refresh_from_db()
            if match.status == 'completed':
                set_player_rest(match)
            advance_bracket(match)
            messages.success(request, 'Resultat er gemt.')
            return redirect('tournament_detail', pk=match.division.tournament.pk)
    else:
        form = MatchResultForm(instance=match)
    return render(request, 'tournaments/match_result_form.html', {'form': form, 'match': match})


WALKOVER_SCORE = '21-0, 21-0'


@login_required
def match_start(request, pk):
    match = get_object_or_404(Match, pk=pk, division__tournament__owner=request.user)
    if request.method == 'POST' and match.status == 'pending':
        errors = check_match_startable(match)
        if errors:
            messages.error(request, 'Kan ikke starte kamp: ' + ' · '.join(errors))
        else:
            match.status = 'in_progress'
            match.save(update_fields=['status'])
            messages.success(request, f'Kamp #{match.match_number or match.pk} er nu i gang.')
    return redirect('tournament_detail', pk=match.division.tournament.pk)


@login_required
def match_walkover(request, pk):
    match = get_object_or_404(Match, pk=pk, division__tournament__owner=request.user)
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
            return redirect('tournament_detail', pk=match.division.tournament.pk)
    else:
        form = WalkoverForm(match=match)
    return render(request, 'tournaments/match_walkover_form.html', {'form': form, 'match': match})


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
            .exclude(team2__isnull=True)
            .exclude(team1__isnull=True)
            .select_related('team1', 'team2')
            .order_by('match_round', 'match_number')
        )
        _apply_seed_labels(matches, seed_lookup)
        division_data.append({
            'division': division,
            'teams': teams,
            'matches': matches,
            'seeds_dict': _seeds_dict_for_division(division, seed_lookup),
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

