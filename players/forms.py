from django import forms
from .models import Player, Team

class PlayerForm(forms.ModelForm):
    class Meta:
        model = Player
        fields = ['name', 'age', 'gender', 'division']

class TeamForm(forms.ModelForm):
    class Meta:
        model = Team
        fields = ['player1', 'player2', 'pair_type', 'division']

    def __init__(self, *args, owner=None, **kwargs):
        super().__init__(*args, **kwargs)
        if owner is not None:
            qs = Player.objects.filter(owner=owner).order_by('name')
            self.fields['player1'].queryset = qs
            self.fields['player2'].queryset = qs

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get('player1')
        p2 = cleaned.get('player2')
        pair_type = cleaned.get('pair_type')

        if p2:
            if not pair_type:
                self.add_error('pair_type', 'Vælg par-type (double eller mixeddouble) når du tilføjer to spillere.')
            elif p1 and pair_type == 'double' and p1.gender != p2.gender:
                self.add_error('pair_type', 'Double kræver to spillere af samme køn.')
            elif p1 and pair_type == 'mixed' and p1.gender == p2.gender:
                self.add_error('pair_type', 'Mixeddouble kræver én mand og én kvinde.')
        else:
            # Singles don't need a pair_type
            cleaned['pair_type'] = None

        return cleaned