from django.db import models
from players.models import Player
from tournaments.models import Tournament

# Create your models here.

class Match(models.Model):
    """Stores a simple head-to-head match between two players."""

    player1 = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='player1_matches')
    player2 = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='player2_matches')
    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE)
    score = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        """Return a readable match label."""
        return f"{self.player1} vs {self.player2} in {self.tournament}"
