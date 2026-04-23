from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from .models import Player, Team
from .forms import PlayerForm, TeamForm
from tournaments.player_status import get_busy_info, player_status as _player_status

@login_required
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

    players = list(Player.objects.filter(owner=request.user).order_by(sort_field))
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
            ('division', 'Række'),
            ('',         ''),
        ],
    })

@login_required
def player_add(request):
    if request.method == 'POST':
        form = PlayerForm(request.POST)
        if form.is_valid():
            player = form.save(commit=False)
            player.owner = request.user
            player.save()
            messages.success(request, f'Spiller "{player.name}" er oprettet.')
            return redirect('player_list')
    else:
        form = PlayerForm()
    return render(request, 'players/player_form.html', {'form': form})

@login_required
def player_edit(request, pk):
    player = get_object_or_404(Player, pk=pk, owner=request.user)
    if request.method == 'POST':
        form = PlayerForm(request.POST, instance=player)
        if form.is_valid():
            form.save()
            messages.success(request, f'Spiller "{player.name}" er opdateret.')
            return redirect('player_list')
    else:
        form = PlayerForm(instance=player)
    return render(request, 'players/player_form.html', {'form': form, 'player': player})

@login_required
def player_delete(request, pk):
    player = get_object_or_404(Player, pk=pk, owner=request.user)
    if request.method == 'POST':
        name = player.name
        player.delete()
        messages.success(request, f'Spiller "{name}" er slettet.')
        return redirect('player_list')
    return render(request, 'players/player_confirm_delete.html', {'object': player, 'type': 'spiller'})

@login_required
def player_clear_rest(request, pk):
    """POST-only: clear rest_until for a player so they can be scheduled immediately."""
    if request.method == 'POST':
        player = get_object_or_404(Player, pk=pk, owner=request.user)
        player.rest_until = None
        player.save(update_fields=['rest_until'])
        messages.success(request, f'Hvileperiode for {player.name} er fjernet.')
    return redirect('player_list')

@login_required
def team_list(request):
    search = request.GET.get('search', '').strip()
    filter_division = request.GET.get('division', '')
    filter_type = request.GET.get('pair_type', '')
    sort = request.GET.get('sort', 'name')
    direction = request.GET.get('dir', 'asc')

    VALID_SORT_FIELDS = {
        'name': 'name',
        'division': 'division',
        'pair_type': 'pair_type',
    }
    sort_field = VALID_SORT_FIELDS.get(sort, 'name')
    if direction == 'desc':
        sort_field = f'-{sort_field}'

    teams = list(
        Team.objects.filter(player2__isnull=False, player1__owner=request.user)
        .select_related('player1', 'player2')
        .order_by(sort_field)
    )
    if search:
        q = search.lower()
        teams = [t for t in teams if q in (t.name or '').lower()
                 or q in t.player1.name.lower()
                 or (t.player2 and q in t.player2.name.lower())]
    if filter_division:
        teams = [t for t in teams if t.division == filter_division]
    if filter_type:
        teams = [t for t in teams if t.pair_type == filter_type]

    col_defs = [
        ('name',      'Par'),
        ('pair_type', 'Type'),
        ('division',  'Række'),
        ('',          'Spiller 1'),
        ('',          'Spiller 2'),
        ('',          ''),
    ]

    return render(request, 'players/team_list.html', {
        'teams': teams,
        'search': search,
        'sort': sort,
        'dir': direction,
        'selected_division': filter_division,
        'selected_type': filter_type,
        'division_choices': Team.DIVISION_CHOICES,
        'pair_type_choices': Team.PAIR_TYPE_CHOICES,
        'col_defs': col_defs,
    })

@login_required
def team_add(request):
    if request.method == 'POST':
        form = TeamForm(request.POST, owner=request.user)
        if form.is_valid():
            team = form.save()
            messages.success(request, f'Par "{team.name}" er oprettet.')
            return redirect('team_list')
    else:
        form = TeamForm(owner=request.user)
    return render(request, 'players/team_form.html', {'form': form, 'division_choices': Player.DIVISION_CHOICES})

@login_required
def team_edit(request, pk):
    team = get_object_or_404(Team, pk=pk, player1__owner=request.user)
    if request.method == 'POST':
        form = TeamForm(request.POST, instance=team, owner=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, f'Par "{team.name}" er opdateret.')
            return redirect('team_list')
    else:
        form = TeamForm(instance=team, owner=request.user)
    return render(request, 'players/team_form.html', {'form': form, 'team': team, 'division_choices': Player.DIVISION_CHOICES})

@login_required
def team_delete(request, pk):
    team = get_object_or_404(Team, pk=pk, player1__owner=request.user)
    if request.method == 'POST':
        name = team.name
        team.delete()
        messages.success(request, f'Par "{name}" er slettet.')
        return redirect('team_list')
    return render(request, 'players/player_confirm_delete.html', {'object': team, 'type': 'par'})


@login_required
def player_schedule_print(request, pk):
    """Print-venlig spilleplan for en enkelt spiller på tværs af turneringer."""
    from tournaments.models import Match, Tournament, DivisionSeed
    player = get_object_or_404(Player, pk=pk, owner=request.user)
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
