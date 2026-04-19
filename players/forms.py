from django import forms
from .models import Player, Team

class PlayerForm(forms.ModelForm):
    class Meta:
        model = Player
        fields = ['name', 'age', 'ranking', 'division']

class TeamForm(forms.ModelForm):
    class Meta:
        model = Team
        fields = ['player1', 'player2']