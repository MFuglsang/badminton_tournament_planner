from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db.models import Q
from .models import Player, Team
from .forms import PlayerForm, TeamForm
from tournaments.player_status import get_busy_info, player_status as _player_status

def player_list(request):
    division = request.GET.get('division', '')
    gender = request.GET.get('gender', '')
    search = request.GET.get('search', '').strip()
    sort = request.GET.get('sort', 'name')
    direction = request.GET.get('dir', 'asc')

    VALID_SORT_FIELDS = {
        'name': 'name',
        'gender': 'gender',
        'age': 'age',
        'division': 'division',
    }
    sort_field = VALID_SORT_FIELDS.get(sort, 'name')
    if direction == 'desc':
        sort_field = f'-{sort_field}'

    players = list(Player.objects.all().order_by(sort_field))
    if division:
        players = [p for p in players if p.division == division]
    if gender:
        players = [p for p in players if p.gender == gender]
    if search:
        players = [p for p in players if search.lower() in p.name.lower()]

    # Annotate each player with their status
    playing_pks, resting = get_busy_info()
    for p in players:
        status, rest_until = _player_status(p.pk, playing_pks, resting)
        p.play_status = status
        p.rest_until_ts = int(rest_until.timestamp()) if rest_until else None

    return render(request, 'players/player_list.html', {
        'players': players,
        'division_choices': Player.DIVISION_CHOICES,
        'gender_choices': Player.GENDER_CHOICES,
        'selected_division': division,
        'selected_gender': gender,
        'search': search,
        'sort': sort,
        'dir': direction,
        'col_defs': [
            ('name',     'Navn'),
            ('gender',   'Køn'),
            ('age',      'Alder'),
            ('division', 'Division'),
            ('',         ''),
        ],
    })

def player_add(request):
    if request.method == 'POST':
        form = PlayerForm(request.POST)
        if form.is_valid():
            player = form.save()
            messages.success(request, f'Spiller "{player.name}" er oprettet.')
            return redirect('player_list')
    else:
        form = PlayerForm()
    return render(request, 'players/player_form.html', {'form': form})

def player_edit(request, pk):
    player = get_object_or_404(Player, pk=pk)
    if request.method == 'POST':
        form = PlayerForm(request.POST, instance=player)
        if form.is_valid():
            form.save()
            messages.success(request, f'Spiller "{player.name}" er opdateret.')
            return redirect('player_list')
    else:
        form = PlayerForm(instance=player)
    return render(request, 'players/player_form.html', {'form': form, 'player': player})

def player_delete(request, pk):
    player = get_object_or_404(Player, pk=pk)
    if request.method == 'POST':
        name = player.name
        player.delete()
        messages.success(request, f'Spiller "{name}" er slettet.')
        return redirect('player_list')
    return render(request, 'players/player_confirm_delete.html', {'object': player, 'type': 'spiller'})

def team_list(request):
    teams = Team.objects.filter(player2__isnull=False).select_related('player1', 'player2').order_by('name')
    return render(request, 'players/team_list.html', {'teams': teams})

def team_add(request):
    if request.method == 'POST':
        form = TeamForm(request.POST)
        if form.is_valid():
            team = form.save()
            messages.success(request, f'Hold "{team.name}" er oprettet.')
            return redirect('team_list')
    else:
        form = TeamForm()
    return render(request, 'players/team_form.html', {'form': form})

def team_edit(request, pk):
    team = get_object_or_404(Team, pk=pk)
    if request.method == 'POST':
        form = TeamForm(request.POST, instance=team)
        if form.is_valid():
            form.save()
            messages.success(request, f'Hold "{team.name}" er opdateret.')
            return redirect('team_list')
    else:
        form = TeamForm(instance=team)
    return render(request, 'players/team_form.html', {'form': form, 'team': team})

def team_delete(request, pk):
    team = get_object_or_404(Team, pk=pk)
    if request.method == 'POST':
        name = team.name
        team.delete()
        messages.success(request, f'Hold "{name}" er slettet.')
        return redirect('team_list')
    return render(request, 'players/player_confirm_delete.html', {'object': team, 'type': 'hold'})


def player_schedule_print(request, pk):
    """Print-venlig spilleplan for en enkelt spiller på tværs af turneringer."""
    from tournaments.models import Match, Tournament, DivisionSeed
    player = get_object_or_404(Player, pk=pk)
    # Find alle teams som spilleren er en del af
    teams = Team.objects.filter(Q(player1=player) | Q(player2=player))
    # Find alle kampe (med tidspunkt) for disse teams, sorteret efter tidspunkt
    matches = list(
        Match.objects
        .filter(Q(team1__in=teams) | Q(team2__in=teams))
        .filter(scheduled_time__isnull=False)
        .exclude(match_number=None)
        .select_related('team1', 'team2', 'division', 'division__tournament', 'winner')
        .order_by('scheduled_time')
    )
    # Annotate matches with seed display strings
    tournament_ids = set(m.division.tournament_id for m in matches)
    seed_lookup = {
        (s.division_id, s.team_id): s.seed_number
        for s in DivisionSeed.objects.filter(division__tournament_id__in=tournament_ids)
    }
    for match in matches:
        s1 = seed_lookup.get((match.division_id, match.team1_id))
        s2 = seed_lookup.get((match.division_id, match.team2_id))
        match.t1_seed = f' ({s1})' if s1 else ''
        match.t2_seed = f' ({s2})' if s2 else ''

    # Brug logo fra den eneste turnering hvis alle kampe er fra samme turnering
    logo_tournament = None
    if len(tournament_ids) == 1:
        logo_tournament = matches[0].division.tournament if matches else None
    return render(request, 'players/player_schedule_print.html', {
        'player': player,
        'matches': matches,
        'logo_tournament': logo_tournament,
    })
