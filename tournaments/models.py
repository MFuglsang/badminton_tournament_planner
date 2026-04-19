from django.db import models
from django.utils.translation import gettext_lazy as _

# Create your models here.

class Tournament(models.Model):
    name = models.CharField(max_length=200, verbose_name=_("Name"))
    tournament_type = models.CharField(
        max_length=50,
        choices=[('tree', _('Tree')), ('group', _('Group')), ('playoff', _('Group with Playoffs'))],
        verbose_name=_("Tournament Type")
    )
    date = models.DateField(verbose_name=_("Date"))
    DIVISION_MODEL_CHOICES = [
        ('youth', _('Youth Divisions (U9-U19)')),
        ('mixed', _('Mixed Divisions (A, B, C)')),
    ]
    division_model = models.CharField(max_length=10, choices=DIVISION_MODEL_CHOICES, verbose_name=_("Division Model"))
    SCORING_MODEL_CHOICES = [
        ('best_of_3_21', _('Best of 3 sets to 21')),
        ('best_of_5_15', _('Best of 5 sets to 15')),
    ]
    scoring_model = models.CharField(
        max_length=20,
        choices=SCORING_MODEL_CHOICES,
        default='best_of_3_21',
        verbose_name=_("Scoring Model")
    )
    single_match_duration = models.IntegerField(
        help_text=_("Duration of a single match in minutes"),
        default=30,
        verbose_name=_("Single Match Duration")
    )
    double_match_duration = models.IntegerField(
        help_text=_("Duration of a double match in minutes"),
        default=40,
        verbose_name=_("Double Match Duration")
    )
    player_break_time = models.IntegerField(
        help_text=_("Minimum break time for players between matches in minutes"),
        default=15,
        verbose_name=_("Player Break Time")
    )

    def __str__(self):
        return f"{self.name} ({self.scoring_model})"

class Division(models.Model):
    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE, related_name='divisions')
    name = models.CharField(max_length=100, verbose_name=_("Division Name"))

    def __str__(self):
        return f"{self.name} ({self.tournament.name})"

class Match(models.Model):
    division = models.ForeignKey(Division, on_delete=models.CASCADE, related_name='matches')
    team1 = models.ForeignKey('players.Team', on_delete=models.CASCADE, related_name='team1_matches')
    team2 = models.ForeignKey('players.Team', on_delete=models.CASCADE, related_name='team2_matches')
    score = models.CharField(max_length=50, blank=True, null=True, verbose_name=_("Score"))
    scheduled_time = models.DateTimeField(verbose_name=_("Scheduled Time"))

    def __str__(self):
        return f"{self.team1} vs {self.team2} ({self.division.name})"
