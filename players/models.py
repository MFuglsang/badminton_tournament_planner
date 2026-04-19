from django.db import models
from django.utils.translation import gettext_lazy as _

# Create your models here.

class Player(models.Model):
    name = models.CharField(max_length=100, verbose_name=_("Name"))
    age = models.IntegerField(verbose_name=_("Age"))
    ranking = models.IntegerField(verbose_name=_("Ranking"))
    DIVISION_CHOICES = [
        ('U9', _('Under 9')),
        ('U11', _('Under 11')),
        ('U13', _('Under 13')),
        ('U15', _('Under 15')),
        ('U17', _('Under 17')),
        ('U19', _('Under 19')),
        ('A', _('A Række')),
        ('B', _('B Række')),
        ('C', _('C Række')),
    ]
    division = models.CharField(max_length=10, choices=DIVISION_CHOICES, verbose_name=_("Division"))

    def __str__(self):
        return f"{self.name} ({self.division})"

class Team(models.Model):
    player1 = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='team_player1')
    player2 = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='team_player2')
    name = models.CharField(max_length=100, blank=True, null=True)

    def save(self, *args, **kwargs):
        if not self.name:
            self.name = f"{self.player1.name} & {self.player2.name}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name
