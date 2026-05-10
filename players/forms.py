from django import forms
from django.utils.translation import gettext_lazy as _
from .models import Player, Team, DivisionCategory


def _division_choices(owner):
    """Return a list of (value, label) tuples from the user's DivisionCategory list."""
    cats = DivisionCategory.objects.filter(owner=owner).values_list('name', flat=True)
    return [('', _("— Select division —"))] + [(c, c) for c in cats]


class PlayerForm(forms.ModelForm):
    """Form for creating and editing a player."""

    class Meta:
        model = Player
        fields = ['name', 'age', 'gender', 'division']

    def __init__(self, *args, owner=None, **kwargs):
        """Configure owner-specific division choices.

        Args:
            *args: Positional form arguments.
            owner: User that owns available division categories.
            **kwargs: Keyword form arguments.
        """
        super().__init__(*args, **kwargs)
        if owner is not None:
            self.fields['division'].widget = forms.Select(choices=_division_choices(owner))


class TeamForm(forms.ModelForm):
    """Form for creating and editing a doubles or mixed team."""

    class Meta:
        model = Team
        fields = ['player1', 'player2', 'pair_type', 'division']

    def __init__(self, *args, owner=None, **kwargs):
        """Limit selectable players and divisions to the owner.

        Args:
            *args: Positional form arguments.
            owner: User that owns available players and divisions.
            **kwargs: Keyword form arguments.
        """
        super().__init__(*args, **kwargs)
        if owner is not None:
            qs = Player.objects.filter(owner=owner).order_by('name')
            self.fields['player1'].queryset = qs
            self.fields['player2'].queryset = qs
            self.fields['division'].widget = forms.Select(choices=_division_choices(owner))

    def clean(self):
        """Validate pair type and gender constraints for two-player teams.

        Returns:
            dict: Cleaned form data.
        """
        cleaned = super().clean()
        p1 = cleaned.get('player1')
        p2 = cleaned.get('player2')
        pair_type = cleaned.get('pair_type')

        if p2:
            if not pair_type:
                self.add_error('pair_type', _("Select pair type (doubles or mixed doubles) when adding two players."))
            elif p1 and pair_type == 'double' and p1.gender != p2.gender:
                self.add_error('pair_type', _("Doubles requires two players of the same gender."))
            elif p1 and pair_type == 'mixed' and p1.gender == p2.gender:
                self.add_error('pair_type', _("Mixed doubles requires one male and one female player."))
        else:
            # Singles don't need a pair_type
            cleaned['pair_type'] = None

        return cleaned
