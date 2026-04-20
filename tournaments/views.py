from django.db.models import Max
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from .models import Tournament, Division, Match
from .forms import MatchResultForm, DivisionForm, TournamentForm, get_participants_form, WalkoverForm
from .standings import compute_standings, compute_group_standings
from players.models import Team
from .scheduler import generate_schedule, advance_bracket, get_bracket_data
from .schedule_planner import generate_time_schedule


def tournament_list(request):
    tournaments = Tournament.objects.prefetch_related('divisions').order_by('-date')
    return render(request, 'tournaments/tournament_list.html', {'tournaments': tournaments})


def tournament_create(request):
    if request.method == 'POST':
        form = TournamentForm(request.POST, request.FILES)
        if form.is_valid():
            tournament = form.save()
            messages.success(request, f'Turnering "{tournament.name}" er oprettet.')
            return redirect('tournament_detail', pk=tournament.pk)
    else:
        form = TournamentForm()
    return render(request, 'tournaments/tournament_form.html', {'form': form})


def tournament_edit(request, pk):
    tournament = get_object_or_404(Tournament, pk=pk)
    if request.method == 'POST':
        form = TournamentForm(request.POST, request.FILES, instance=tournament)
        if form.is_valid():
            form.save()
            messages.success(request, f'Turnering "{tournament.name}" er opdateret.')
            return redirect('tournament_detail', pk=tournament.pk)
    else:
        form = TournamentForm(instance=tournament)
    return render(request, 'tournaments/tournament_form.html', {'form': form, 'tournament': tournament})


def tournament_delete(request, pk):
    tournament = get_object_or_404(Tournament, pk=pk)
    if request.method == 'POST':
        name = tournament.name
        tournament.delete()
        messages.success(request, f'Turnering "{name}" er slettet.')
        return redirect('tournament_list')
    return render(request, 'tournaments/tournament_confirm_delete.html', {'tournament': tournament})


def tournament_detail(request, pk):
    tournament = get_object_or_404(Tournament, pk=pk)
    divisions = tournament.divisions.prefetch_related('teams', 'matches__team1', 'matches__team2', 'matches__winner')
    division_data = [
        {
            'division': d,
            'standings': compute_standings(d) if d.tournament_type == 'group' else [],
            'group_standings': compute_group_standings(d) if d.tournament_type == 'playoff' else [],
            'participants_form': get_participants_form(d),
            'match_count': d.matches.count(),
            'pending_count': d.matches.filter(status='pending').count(),
            'bracket_data': get_bracket_data(d) if d.tournament_type in ('tree', 'playoff') else None,
        }
        for d in divisions
    ]
    division_form = DivisionForm()
    return render(request, 'tournaments/tournament_detail.html', {
        'tournament': tournament,
        'division_data': division_data,
        'division_form': division_form,
    })


def division_create(request, tournament_pk):
    tournament = get_object_or_404(Tournament, pk=tournament_pk)
    if request.method == 'POST':
        form = DivisionForm(request.POST)
        if form.is_valid():
            division = form.save(commit=False)
            division.tournament = tournament
            division.save()
            messages.success(request, f'Division "{division.name}" er oprettet.')
    return redirect('tournament_detail', pk=tournament_pk)


def division_update_teams(request, pk):
    division = get_object_or_404(Division, pk=pk)
    if request.method == 'POST':
        form = get_participants_form(division, request.POST)
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


def division_delete(request, pk):
    division = get_object_or_404(Division, pk=pk)
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


def division_generate_schedule(request, pk):
    division = get_object_or_404(Division, pk=pk)
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


def match_record_result(request, pk):
    match = get_object_or_404(Match, pk=pk)
    if request.method == 'POST':
        form = MatchResultForm(request.POST, instance=match)
        if form.is_valid():
            form.save()
            advance_bracket(match)
            messages.success(request, 'Resultat er gemt.')
            return redirect('tournament_detail', pk=match.division.tournament.pk)
    else:
        form = MatchResultForm(instance=match)
    return render(request, 'tournaments/match_result_form.html', {'form': form, 'match': match})


WALKOVER_SCORE = '21-0, 21-0'


def match_start(request, pk):
    match = get_object_or_404(Match, pk=pk)
    if request.method == 'POST' and match.status == 'pending':
        match.status = 'in_progress'
        match.save(update_fields=['status'])
        messages.success(request, f'Kamp #{match.match_number or match.pk} er nu i gang.')
    return redirect('tournament_detail', pk=match.division.tournament.pk)


def match_walkover(request, pk):
    match = get_object_or_404(Match, pk=pk)
    if request.method == 'POST':
        form = WalkoverForm(request.POST, match=match)
        if form.is_valid():
            match.winner = form.cleaned_data['winner']
            match.score = WALKOVER_SCORE
            match.status = 'completed'
            match.walkover = True
            match.save()
            advance_bracket(match)
            messages.success(request, f'Walk-over registreret – {match.winner} vinder.')
            return redirect('tournament_detail', pk=match.division.tournament.pk)
    else:
        form = WalkoverForm(match=match)
    return render(request, 'tournaments/match_walkover_form.html', {'form': form, 'match': match})


def tournament_scoresheet(request, pk):
    tournament = get_object_or_404(Tournament, pk=pk)
    matches = (
        Match.objects
        .filter(division__tournament=tournament)
        .exclude(match_number=None)
        .exclude(team2__isnull=True)
        .exclude(team1__isnull=True)
        .select_related('team1', 'team2', 'division')
        .order_by('match_number')
    )
    return render(request, 'tournaments/scoresheet.html', {
        'tournament': tournament,
        'matches': matches,
        'title_suffix': None,
    })


def tournament_program_print(request, pk):
    """Print-venligt samlet kampprogram for hele turneringen, division for division."""
    tournament = get_object_or_404(Tournament, pk=pk)
    divisions = tournament.divisions.prefetch_related(
        'teams', 'teams__player1', 'teams__player2',
        'matches__team1', 'matches__team2',
    ).order_by('name')
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
        division_data.append({
            'division': division,
            'teams': teams,
            'matches': matches,
        })
    return render(request, 'tournaments/tournament_program_print.html', {
        'tournament': tournament,
        'division_data': division_data,
    })


def division_scoresheet(request, pk):
    division = get_object_or_404(Division, pk=pk)
    matches = (
        Match.objects
        .filter(division=division)
        .exclude(match_number=None)
        .exclude(team2__isnull=True)
        .exclude(team1__isnull=True)
        .select_related('team1', 'team2', 'division')
        .order_by('match_number')
    )
    return render(request, 'tournaments/scoresheet.html', {
        'tournament': division.tournament,
        'matches': matches,
        'title_suffix': division.name,
    })


def tournament_schedule(request, pk):
    from django.utils import timezone
    tournament = get_object_or_404(Tournament, pk=pk)
    matches = (
        Match.objects
        .filter(division__tournament=tournament, scheduled_time__isnull=False)
        .select_related('division', 'team1', 'team2', 'winner')
        .order_by('scheduled_time', 'court')
    )
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


def tournament_generate_time_schedule(request, pk):
    tournament = get_object_or_404(Tournament, pk=pk)
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


def tournament_toggle_lock(request, pk):
    tournament = get_object_or_404(Tournament, pk=pk)
    if request.method == 'POST':
        tournament.schedule_locked = not tournament.schedule_locked
        tournament.save(update_fields=['schedule_locked'])
        if tournament.schedule_locked:
            messages.success(request, 'Spilleplanen er nu låst.')
        else:
            messages.success(request, 'Spilleplanen er nu låst op.')
    return redirect('tournament_schedule', pk=pk)

