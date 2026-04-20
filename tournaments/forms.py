from django import forms
from django.db.models import F
from .models import Match, Division, Tournament
from players.models import Player, Team


class TournamentForm(forms.ModelForm):
    class Meta:
        model = Tournament
        fields = [
            'name', 'date', 'division_model',
            'scoring_model', 'court_count', 'start_time',
            'single_match_duration', 'double_match_duration', 'player_break_time',
        ]
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'start_time': forms.TimeInput(attrs={'type': 'time'}),
        }


class DivisionForm(forms.ModelForm):
    class Meta:
        model = Division
        fields = ['name', 'discipline', 'tournament_type']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'f.eks. Herresingle A, Damedouble B …'}),
        }


class DivisionPlayersForm(forms.Form):
    """For single-discipline divisions – select individual players."""
    players = forms.ModelMultipleChoiceField(
        queryset=Player.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label='Spillere',
    )

    def __init__(self, *args, division=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['players'].queryset = Player.objects.order_by('name')
        if division:
            current = division.teams.filter(player2__isnull=True).values_list('player1_id', flat=True)
            self.fields['players'].initial = list(current)


class DivisionPairsForm(forms.Form):
    """For double/mixed-discipline divisions – select existing pairs."""
    pairs = forms.ModelMultipleChoiceField(
        queryset=Team.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label='Par',
    )

    def __init__(self, *args, division=None, **kwargs):
        super().__init__(*args, **kwargs)
        if division and division.discipline == 'mixed':
            # Mixed: one player of each gender
            qs = Team.objects.filter(
                player2__isnull=False
            ).exclude(
                player1__gender=F('player2__gender')
            ).select_related('player1', 'player2').order_by('name')
        else:
            # Double: both players same gender
            qs = Team.objects.filter(
                player2__isnull=False,
                player1__gender=F('player2__gender')
            ).select_related('player1', 'player2').order_by('name')
        self.fields['pairs'].queryset = qs
        if division:
            self.fields['pairs'].initial = division.teams.values_list('pk', flat=True)


def get_participants_form(division, data=None):
    """Factory: returns the right form type for the division's discipline."""
    if division.discipline == 'single':
        return DivisionPlayersForm(data, division=division)
    return DivisionPairsForm(data, division=division)


class MatchResultForm(forms.ModelForm):
    class Meta:
        model = Match
        fields = ['score', 'winner', 'status']
        widgets = {
            'score': forms.TextInput(attrs={'placeholder': '21-15, 18-21, 21-18'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        match = kwargs.get('instance')
        if match:
            pks = [match.team1.pk]
            if match.team2:
                pks.append(match.team2.pk)
            self.fields['winner'].queryset = (
                type(match.team1).objects.filter(pk__in=pks)
            )
        self.fields['status'].initial = 'completed'


class WalkoverForm(forms.Form):
    """Record a walk-over: just pick which team remains (the winner)."""
    winner = forms.ModelChoiceField(
        queryset=None,
        empty_label=None,
        label='Vinder (spilleren der møder op)',
    )

    def __init__(self, *args, match=None, **kwargs):
        super().__init__(*args, **kwargs)
        if match:
            from players.models import Team
            pks = [match.team1.pk]
            if match.team2:
                pks.append(match.team2.pk)
            self.fields['winner'].queryset = Team.objects.filter(pk__in=pks)
