from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db.models import Q
from .models import Player, Team
from .forms import PlayerForm, TeamForm

def player_list(request):
    division = request.GET.get('division', '')
    players = Player.objects.all().order_by('division', 'ranking')
    if division:
        players = players.filter(division=division)
    division_choices = Player.DIVISION_CHOICES
    return render(request, 'players/player_list.html', {
        'players': players,
        'division_choices': division_choices,
        'selected_division': division,
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
    from tournaments.models import Match, Tournament
    player = get_object_or_404(Player, pk=pk)
    # Find alle teams som spilleren er en del af
    teams = Team.objects.filter(Q(player1=player) | Q(player2=player))
    # Find alle kampe (med tidspunkt) for disse teams, sorteret efter tidspunkt
    matches = (
        Match.objects
        .filter(Q(team1__in=teams) | Q(team2__in=teams))
        .filter(scheduled_time__isnull=False)
        .exclude(match_number=None)
        .select_related('team1', 'team2', 'division', 'division__tournament', 'winner')
        .order_by('scheduled_time')
    )
    # Brug logo fra den eneste turnering hvis alle kampe er fra samme turnering
    tournament_ids = set(m.division.tournament_id for m in matches)
    logo_tournament = None
    if len(tournament_ids) == 1:
        logo_tournament = matches[0].division.tournament if matches else None
    return render(request, 'players/player_schedule_print.html', {
        'player': player,
        'matches': matches,
        'logo_tournament': logo_tournament,
    })
