import re

from django import forms
from django.db.models import F
from .models import Match, Division, Tournament
from players.models import Player, Team


# ── Score validation helpers ──────────────────────────────────────────────────

def _parse_score(score_str):
    """Parse '21-15, 18-21, 21-18' → list of (a, b) int tuples.

    Raises ValueError with a Danish message on bad format.
    """
    sets = []
    for part in score_str.split(','):
        part = part.strip()
        m = re.match(r'^(\d{1,2})-(\d{1,2})$', part)
        if not m:
            raise ValueError(
                f"Ugyldigt format: '{part}'. Skriv hvert sæt som f.eks. 21-15"
            )
        sets.append((int(m.group(1)), int(m.group(2))))
    if not sets:
        raise ValueError("Ingen sæt-score fundet")
    return sets


def _validate_set(a, b):
    """Return an error string if (a, b) breaks BWF set-score rules, else ''."""
    if a == b:
        return f"{a}-{b}: et sæt kan ikke slutte uafgjort"
    w, l = (a, b) if a > b else (b, a)
    if w < 21:
        return f"{a}-{b}: vinderen skal have mindst 21 point"
    if w > 30:
        return f"{a}-{b}: maksimal score er 30-29"
    if w == 21 and l <= 19:
        return ""   # normal win
    if w >= 22 and w - l == 2:
        return ""   # deuce win (22-20 … 30-28)
    if w == 30 and l == 29:
        return ""   # max deuce (already covered above, explicit for clarity)
    if w == 21 and l == 20:
        return f"{a}-{b}: ved 20-20 fortsættes til 2 points forskel (f.eks. 22-20)"
    return f"{a}-{b}: ugyldigt sæt-resultat (ved forlænget spil skal forskel være præcis 2 point)"


class TournamentForm(forms.ModelForm):
    class Meta:
        model = Tournament
        fields = [
            'name', 'date', 'division_model',
            'scoring_model', 'court_count', 'start_time',
            'single_match_duration', 'double_match_duration', 'player_break_time',
            'logo',
        ]
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'start_time': forms.TimeInput(attrs={'type': 'time'}),
        }


class DivisionForm(forms.ModelForm):
    class Meta:
        model = Division
        fields = ['name', 'discipline', 'tournament_type', 'group_count', 'advance_count']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'f.eks. Herresingle A, Damedouble B …'}),
            'group_count': forms.NumberInput(attrs={'min': 2, 'max': 16}),
            'advance_count': forms.NumberInput(attrs={'min': 1, 'max': 8}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['group_count'].required = False
        self.fields['advance_count'].required = False
        self.fields['group_count'].initial = 2
        self.fields['advance_count'].initial = 2

    def clean_group_count(self):
        val = self.cleaned_data.get('group_count')
        return val if val is not None else 2

    def clean_advance_count(self):
        val = self.cleaned_data.get('advance_count')
        return val if val is not None else 2


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

    def clean_score(self):
        score = (self.cleaned_data.get('score') or '').strip()
        status = self.data.get('status')
        if status != 'completed' or not score:
            return score

        # 1. Parse
        try:
            sets = _parse_score(score)
        except ValueError as exc:
            raise forms.ValidationError(str(exc))

        # 2. Number of sets: 2 or 3 (best of 3)
        if not (2 <= len(sets) <= 3):
            raise forms.ValidationError(
                "En badminton-kamp spilles bedst af 3 sæt – angiv 2 eller 3 sæt."
            )

        # 3. Each set must be a legal BWF score
        for a, b in sets:
            err = _validate_set(a, b)
            if err:
                raise forms.ValidationError(f"Ugyldigt sæt: {err}")

        # 4. The eventual winner must have exactly 2 set-wins
        t1_sets = sum(1 for a, b in sets if a > b)
        t2_sets = sum(1 for a, b in sets if b > a)
        if max(t1_sets, t2_sets) != 2:
            raise forms.ValidationError(
                f"Vinderen skal have præcis 2 sæt-sejre (nuværende tæller: {t1_sets}–{t2_sets})."
            )

        # 5. If 3 sets were played the first two cannot both go to the same team
        if len(sets) == 3:
            a1, b1 = sets[0]
            a2, b2 = sets[1]
            t1_first2 = (a1 > b1) + (a2 > b2)
            if t1_first2 == 2 or t1_first2 == 0:
                raise forms.ValidationError(
                    "Tredje sæt er unødvendigt: én spiller vandt allerede de to første sæt."
                )

        return score

    def clean(self):
        cleaned = super().clean()
        score = (cleaned.get('score') or '').strip()
        winner = cleaned.get('winner')
        status = cleaned.get('status')

        if status != 'completed' or not score or not winner:
            return cleaned

        match = self.instance
        if not match or not match.team1 or not match.team2:
            return cleaned

        try:
            sets = _parse_score(score)
        except ValueError:
            return cleaned  # already raised in clean_score

        t1_sets = sum(1 for a, b in sets if a > b)
        t2_sets = sum(1 for a, b in sets if b > a)
        if t1_sets == t2_sets:
            return cleaned  # already caught above

        expected_winner = match.team1 if t1_sets > t2_sets else match.team2
        if winner.pk != expected_winner.pk:
            raise forms.ValidationError(
                f"Vinder stemmer ikke overens med scoren: ifølge resultatet vandt "
                f"{expected_winner.name} ({t1_sets}–{t2_sets} sæt), "
                f"men du valgte {winner.name} som vinder."
            )
        return cleaned


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
