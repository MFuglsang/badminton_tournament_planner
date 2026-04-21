from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

# Create your models here.

class Tournament(models.Model):
    name = models.CharField(max_length=200, verbose_name=_("Name"))
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
    court_count = models.IntegerField(
        default=4,
        verbose_name=_("Antal baner"),
        help_text=_("Antal tilgængelige baner under turneringen"),
    )
    start_time = models.TimeField(
        null=True, blank=True,
        verbose_name=_("Starttidspunkt"),
        help_text=_("Klokkeslæt for første kamp"),
    )
    schedule_locked = models.BooleanField(
        default=False,
        verbose_name=_("Program låst"),
        help_text=_("Når programmet er låst, kan kampprogram og spilleplan ikke ændres."),
    )
    logo = models.ImageField(
        upload_to='tournament_logos/',
        null=True, blank=True,
        verbose_name=_("Logo"),
        help_text=_("Logo vises på udprintede programmer og spilleplaner."),
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='tournaments',
        verbose_name=_("Klubbruger"),
    )

    def __str__(self):
        return f"{self.name} ({self.scoring_model})"

class Division(models.Model):
    DISCIPLINE_CHOICES = [
        ('single', _('Single')),
        ('double', _('Double')),
        ('mixed', _('Mixeddouble')),
    ]
    TOURNAMENT_TYPE_CHOICES = [
        ('group', _('Gruppe (round-robin)')),
        ('playoff', _('Gruppe med slutspil')),
        ('tree', _('Enkeltelimination')),
    ]
    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE, related_name='divisions')
    name = models.CharField(max_length=100, verbose_name=_("Division Name"))
    discipline = models.CharField(
        max_length=10, choices=DISCIPLINE_CHOICES, default='single',
        verbose_name=_("Disciplin")
    )
    tournament_type = models.CharField(
        max_length=10, choices=TOURNAMENT_TYPE_CHOICES, default='group',
        verbose_name=_("Turneringstype")
    )
    group_count = models.IntegerField(
        default=2, verbose_name=_("Antal grupper"),
        help_text=_("Antal grupper i gruppespillet (kun ved 'Gruppe med slutspil')."),
    )
    advance_count = models.IntegerField(
        default=2, verbose_name=_("Antal der går videre"),
        help_text=_("Antal spillere/hold der går videre fra hver gruppe til slutspillet."),
    )
    teams = models.ManyToManyField('players.Team', related_name='divisions', blank=True, verbose_name=_("Deltagere"))

    def __str__(self):
        return f"{self.name} – {self.get_discipline_display()} ({self.tournament.name})"

class Match(models.Model):
    STATUS_CHOICES = [
        ('pending', _('Pending')),
        ('in_progress', _('In Progress')),
        ('completed', _('Completed')),
    ]
    division = models.ForeignKey(Division, on_delete=models.CASCADE, related_name='matches')
    team1 = models.ForeignKey('players.Team', on_delete=models.SET_NULL, null=True, blank=True, related_name='team1_matches')
    team2 = models.ForeignKey('players.Team', on_delete=models.SET_NULL, null=True, blank=True, related_name='team2_matches')
    winner = models.ForeignKey('players.Team', on_delete=models.SET_NULL, null=True, blank=True, related_name='won_matches', verbose_name=_("Winner"))
    score = models.CharField(max_length=50, blank=True, null=True, verbose_name=_("Score"))
    match_round = models.IntegerField(default=1, verbose_name=_("Round"))
    match_number = models.IntegerField(null=True, blank=True, verbose_name=_("Match Number"))
    bracket_slot = models.IntegerField(null=True, blank=True, verbose_name=_("Bracket Slot"))
    bracket_label = models.CharField(max_length=120, null=True, blank=True, verbose_name=_("Bracket Label"))
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name=_("Status"))
    walkover = models.BooleanField(default=False, verbose_name=_("Walk-over"))
    scheduled_time = models.DateTimeField(verbose_name=_("Scheduled Time"), null=True, blank=True)
    court = models.CharField(max_length=50, blank=True, null=True, verbose_name=_("Court"))
    group_number = models.IntegerField(null=True, blank=True, verbose_name=_("Gruppe nr."))
    phase = models.CharField(
        max_length=10, default='group',
        choices=[('group', _('Gruppespil')), ('playoff', _('Slutspil'))],
        verbose_name=_("Fase"),
    )

    def __str__(self):
        t1 = self.team1 or self.bracket_label or 'TBD'
        t2 = self.team2 or ('Bye' if not self.bracket_label else 'TBD')
        return f"R{self.match_round}: {t1} vs {t2} ({self.division.name})"


class DivisionSeed(models.Model):
    """Records the seed number of a team within a division (optional seeding)."""
    division = models.ForeignKey(Division, on_delete=models.CASCADE, related_name='seeds')
    team = models.ForeignKey('players.Team', on_delete=models.CASCADE, related_name='division_seeds')
    seed_number = models.PositiveIntegerField(verbose_name=_("Seedningsnummer"))

    class Meta:
        unique_together = [('division', 'team'), ('division', 'seed_number')]
        ordering = ['seed_number']

    def __str__(self):
        return f"Seed {self.seed_number}: {self.team.name} ({self.division.name})"
