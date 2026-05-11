import re

from django import forms
from django.db.models import F
from django.utils.translation import gettext_lazy as _
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
                _("Invalid format: '%(part)s'. Write each set as e.g. 21-15") % {'part': part}
            )
        sets.append((int(m.group(1)), int(m.group(2))))
    if not sets:
        raise ValueError(_("No set score found"))
    return sets


def _validate_set(a, b):
    """Return an error string if (a, b) breaks BWF set-score rules, else ''."""
    if a == b:
        return _("%(a)s-%(b)s: a set cannot end in a draw") % {'a': a, 'b': b}
    w, l = (a, b) if a > b else (b, a)
    if w < 21:
        return _("%(a)s-%(b)s: the winner must have at least 21 points") % {'a': a, 'b': b}
    if w > 30:
        return _("%(a)s-%(b)s: maximum score is 30-29") % {'a': a, 'b': b}
    if w == 21 and l <= 19:
        return ""   # normal win
    if w >= 22 and w - l == 2:
        return ""   # deuce win (22-20 … 30-28)
    if w == 30 and l == 29:
        return ""   # max deuce (already covered above, explicit for clarity)
    if w == 21 and l == 20:
        return _("%(a)s-%(b)s: at 20-20 play continues to 2 points difference (e.g. 22-20)") % {'a': a, 'b': b}
    return _("%(a)s-%(b)s: invalid set result (in extended play the difference must be exactly 2 points)") % {'a': a, 'b': b}


class TournamentForm(forms.ModelForm):
    """Form used to create and edit tournaments."""

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
    """Form used to create and edit divisions."""

    class Meta:
        model = Division
        fields = ['name', 'discipline', 'tournament_type', 'group_count', 'advance_count', 'schedule_priority', 'gold_count', 'silver_count', 'bronze_count']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': _('e.g. Mens singles A, Womens doubles B …')}),
            'group_count': forms.NumberInput(attrs={'min': 2, 'max': 16}),
            'advance_count': forms.NumberInput(attrs={'min': 1, 'max': 8}),
            'schedule_priority': forms.NumberInput(attrs={'min': 1, 'max': 10, 'style': 'width:4rem;'}),
            'gold_count': forms.NumberInput(attrs={'min': 0, 'max': 4, 'style': 'width:4rem;'}),
            'silver_count': forms.NumberInput(attrs={'min': 0, 'max': 4, 'style': 'width:4rem;'}),
            'bronze_count': forms.NumberInput(attrs={'min': 0, 'max': 4, 'style': 'width:4rem;'}),
        }

    def __init__(self, *args, **kwargs):
        """Set optional defaults for bracket and medal fields.

        Args:
            *args: Positional arguments passed to ``ModelForm``.
            **kwargs: Keyword arguments passed to ``ModelForm``.
        """
        super().__init__(*args, **kwargs)
        self.fields['group_count'].required = False
        self.fields['advance_count'].required = False
        self.fields['group_count'].initial = 2
        self.fields['advance_count'].initial = 2
        self.fields['schedule_priority'].required = False
        self.fields['schedule_priority'].initial = 5
        self.fields['gold_count'].required = False
        self.fields['gold_count'].initial = 1
        self.fields['silver_count'].required = False
        self.fields['silver_count'].initial = 1
        self.fields['bronze_count'].required = False
        self.fields['bronze_count'].initial = 0

    def clean_group_count(self):
        """Return a default group count when omitted.

        Returns:
            int: Provided group count or the default value ``2``.
        """
        val = self.cleaned_data.get('group_count')
        return val if val is not None else 2

    def clean_advance_count(self):
        """Return a default advance count when omitted.

        Returns:
            int: Provided advance count or the default value ``2``.
        """
        val = self.cleaned_data.get('advance_count')
        return val if val is not None else 2

    def clean_schedule_priority(self):
        """Clamp schedule priority to the supported range.

        Returns:
            int: Priority constrained to the inclusive range 1..10.
        """
        val = self.cleaned_data.get('schedule_priority')
        if val is None:
            return 5
        return max(1, min(10, int(val)))

    def clean_gold_count(self):
        """Return default gold medal count when omitted.

        Returns:
            int: Provided gold count or the default value ``1``.
        """
        val = self.cleaned_data.get('gold_count')
        return val if val is not None else 1

    def clean_silver_count(self):
        """Return default silver medal count when omitted.

        Returns:
            int: Provided silver count or the default value ``1``.
        """
        val = self.cleaned_data.get('silver_count')
        return val if val is not None else 1

    def clean_bronze_count(self):
        """Return default bronze medal count when omitted.

        Returns:
            int: Provided bronze count or the default value ``0``.
        """
        val = self.cleaned_data.get('bronze_count')
        return val if val is not None else 0


class DivisionPlayersForm(forms.Form):
    """For single-discipline divisions – select individual players."""
    players = forms.ModelMultipleChoiceField(
        queryset=Player.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label=_("Players"),
    )

    def __init__(self, *args, division=None, owner=None, **kwargs):
        """Configure player choices and initial selections.

        Args:
            *args: Positional arguments passed to ``Form``.
            division: Division whose current participants should be pre-selected.
            owner: User used to scope player choices.
            **kwargs: Keyword arguments passed to ``Form``.
        """
        super().__init__(*args, **kwargs)
        qs = Player.objects.order_by('name')
        if owner is not None:
            qs = qs.filter(owner=owner)
        self.fields['players'].queryset = qs
        if division:
            current = division.teams.filter(player2__isnull=True).values_list('player1_id', flat=True)
            self.fields['players'].initial = list(current)


class DivisionPairsForm(forms.Form):
    """For double/mixed-discipline divisions – select existing pairs."""
    pairs = forms.ModelMultipleChoiceField(
        queryset=Team.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label=_("Teams"),
    )

    def __init__(self, *args, division=None, owner=None, **kwargs):
        """Configure pair choices and initial selections.

        Args:
            *args: Positional arguments passed to ``Form``.
            division: Division used to determine discipline and initial pairs.
            owner: User used to scope pair choices.
            **kwargs: Keyword arguments passed to ``Form``.
        """
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
        if owner is not None:
            qs = qs.filter(player1__owner=owner)
        self.fields['pairs'].queryset = qs
        if division:
            self.fields['pairs'].initial = division.teams.values_list('pk', flat=True)


def get_participants_form(division, data=None, owner=None):
    """Factory: returns the right form type for the division's discipline."""
    if division.discipline == 'single':
        return DivisionPlayersForm(data, division=division, owner=owner)
    return DivisionPairsForm(data, division=division, owner=owner)


class MatchResultForm(forms.ModelForm):
    """Form used to record match score and winner."""

    class Meta:
        model = Match
        fields = ['score', 'winner']
        widgets = {
            'score': forms.TextInput(attrs={'placeholder': '21-15, 18-21, 21-18'}),
        }

    def __init__(self, *args, **kwargs):
        """Limit winner choices to teams participating in the match.

        Args:
            *args: Positional arguments passed to ``ModelForm``.
            **kwargs: Keyword arguments passed to ``ModelForm``.
        """
        super().__init__(*args, **kwargs)
        match = kwargs.get('instance')
        if match:
            pks = [match.team1.pk]
            if match.team2:
                pks.append(match.team2.pk)
            self.fields['winner'].queryset = (
                type(match.team1).objects.filter(pk__in=pks)
            )

    def clean_score(self):
        """Validate badminton score format and set-level rules.

        Returns:
            str: Normalized score string.

        Raises:
            forms.ValidationError: If the submitted score is invalid.
        """
        score = (self.cleaned_data.get('score') or '').strip()
        if not score:
            return score

        # 1. Parse
        try:
            sets = _parse_score(score)
        except ValueError as exc:
            raise forms.ValidationError(str(exc))

        # 2. Number of sets: 2 or 3 (best of 3)
        if not (2 <= len(sets) <= 3):
            raise forms.ValidationError(
                _("A badminton match is best of 3 sets – provide 2 or 3 sets.")
            )

        # 3. Each set must be a legal BWF score
        for a, b in sets:
            err = _validate_set(a, b)
            if err:
                raise forms.ValidationError(_("Invalid set: %(err)s") % {'err': err})

        # 4. The eventual winner must have exactly 2 set-wins
        t1_sets = sum(1 for a, b in sets if a > b)
        t2_sets = sum(1 for a, b in sets if b > a)
        if max(t1_sets, t2_sets) != 2:
            raise forms.ValidationError(
                _("The winner must have exactly 2 set wins (current count: %(t1)s–%(t2)s).") % {'t1': t1_sets, 't2': t2_sets}
            )

        # 5. If 3 sets were played the first two cannot both go to the same team
        if len(sets) == 3:
            a1, b1 = sets[0]
            a2, b2 = sets[1]
            t1_first2 = (a1 > b1) + (a2 > b2)
            if t1_first2 == 2 or t1_first2 == 0:
                raise forms.ValidationError(
                    _("Third set is unnecessary: one player already won the first two sets.")
                )

        return score

    def clean(self):
        """Validate winner selection against parsed set results.

        Returns:
            dict: Cleaned form data with status set to ``completed`` when valid.

        Raises:
            forms.ValidationError: If winner does not match computed set winner.
        """
        cleaned = super().clean()
        score = (cleaned.get('score') or '').strip()
        winner = cleaned.get('winner')

        if not score or not winner:
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
                _("Winner does not match the score: according to the result %(winner)s won (%(t1)s–%(t2)s sets), but you selected %(selected)s as winner.") % {'winner': expected_winner.name, 't1': t1_sets, 't2': t2_sets, 'selected': winner.name}
            )
        # Auto-complete the match when score + winner are valid
        cleaned['status'] = 'completed'
        return cleaned


class WalkoverForm(forms.Form):
    """Record a walk-over: just pick which team remains (the winner)."""
    winner = forms.ModelChoiceField(
        queryset=None,
        empty_label=None,
        label=_("Winner (the player who shows up)"),
    )

    def __init__(self, *args, match=None, **kwargs):
        """Limit walkover winner choices to teams in the match.

        Args:
            *args: Positional arguments passed to ``Form``.
            match: Match whose teams are valid walkover winners.
            **kwargs: Keyword arguments passed to ``Form``.
        """
        super().__init__(*args, **kwargs)
        if match:
            from players.models import Team
            pks = [match.team1.pk]
            if match.team2:
                pks.append(match.team2.pk)
            self.fields['winner'].queryset = Team.objects.filter(pk__in=pks)
