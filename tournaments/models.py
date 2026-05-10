from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class UserProfile(models.Model):
    """Stores per-club preferences, e.g. default language."""
    LANGUAGE_CHOICES = [
        ('da', 'Dansk'),
        ('en', 'English'),
    ]
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile',
        verbose_name=_("User"),
    )
    language = models.CharField(
        max_length=10,
        choices=LANGUAGE_CHOICES,
        default='da',
        verbose_name=_("Default language"),
    )

    def __str__(self):
        return f"{self.user.username} profile"

    class Meta:
        verbose_name = _("User profile")
        verbose_name_plural = _("User profiles")


# Create your models here.

class Tournament(models.Model):
    name = models.CharField(max_length=200, verbose_name=_("Name"))
    date = models.DateField(verbose_name=_("Date"))
    DIVISION_MODEL_CHOICES = [
        ('youth', _("Youth divisions (U9-U19)")),
        ('mixed', _("Mixed divisions (A, B, C)")),
    ]
    division_model = models.CharField(max_length=10, choices=DIVISION_MODEL_CHOICES, verbose_name=_("Division model"))
    SCORING_MODEL_CHOICES = [
        ('best_of_3_21', _("Best of 3 sets to 21")),
        ('best_of_5_15', _("Best of 3 sets to 15")),
    ]
    scoring_model = models.CharField(
        max_length=20,
        choices=SCORING_MODEL_CHOICES,
        default='best_of_3_21',
        verbose_name=_("Scoring model")
    )
    single_match_duration = models.IntegerField(
        help_text=_("Duration of a singles match in minutes"),
        default=30,
        verbose_name=_("Singles match duration")
    )
    double_match_duration = models.IntegerField(
        help_text=_("Duration of a doubles match in minutes"),
        default=40,
        verbose_name=_("Doubles match duration")
    )
    player_break_time = models.IntegerField(
        help_text=_("Minimum rest period for players between matches in minutes"),
        default=15,
        verbose_name=_("Player break time")
    )
    court_count = models.IntegerField(
        default=4,
        verbose_name=_("Number of courts"),
        help_text=_("Number of courts available during the tournament"),
    )
    start_time = models.TimeField(
        null=True, blank=True,
        verbose_name=_("Start time"),
        help_text=_("Time of first match"),
    )
    schedule_locked = models.BooleanField(
        default=False,
        verbose_name=_("Schedule locked"),
        help_text=_("When locked, the match schedule cannot be changed."),
    )
    logo = models.ImageField(
        upload_to='tournament_logos/',
        null=True, blank=True,
        verbose_name=_("Logo"),
        help_text=_("Logo is shown on printed programmes and schedules."),
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='tournaments',
        verbose_name=_("Club user"),
    )

    def __str__(self):
        return f"{self.name} ({self.scoring_model})"

class Division(models.Model):
    DISCIPLINE_CHOICES = [
        ('single', _("Singles")),
        ('double', _("Doubles")),
        ('mixed', _("Mixed doubles")),
    ]
    TOURNAMENT_TYPE_CHOICES = [
        ('group', _("Group (round-robin)")),
        ('playoff', _("Group + playoff bracket")),
        ('tree', _("Single elimination")),
    ]
    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE, related_name='divisions')
    name = models.CharField(max_length=100, verbose_name=_("Division name"))
    discipline = models.CharField(
        max_length=10, choices=DISCIPLINE_CHOICES, default='single',
        verbose_name=_("Discipline")
    )
    tournament_type = models.CharField(
        max_length=10, choices=TOURNAMENT_TYPE_CHOICES, default='group',
        verbose_name=_("Tournament type")
    )
    group_count = models.IntegerField(
        default=2, verbose_name=_("Number of groups"),
        help_text=_("Number of groups in the group stage (only for 'Group + playoff bracket')."),
    )
    advance_count = models.IntegerField(
        default=2, verbose_name=_("Players advancing per group"),
        help_text=_("Number of players/teams advancing from each group to the playoff bracket."),
    )
    schedule_priority = models.IntegerField(
        default=5,
        verbose_name=_("Schedule priority"),
        help_text=_("1 = schedule earliest · 10 = schedule latest. Use this to ensure younger divisions finish first."),
    )
    gold_count = models.IntegerField(
        default=1, verbose_name=_("Gold medals"),
        help_text=_("Number of teams awarded gold (typically 1)."),
    )
    silver_count = models.IntegerField(
        default=1, verbose_name=_("Silver medals"),
        help_text=_("Number of teams awarded silver (typically 1)."),
    )
    bronze_count = models.IntegerField(
        default=0, verbose_name=_("Bronze medals"),
        help_text=_("0, 1 or 2. Use 2 for bracket tournaments where both semi-final losers receive bronze."),
    )
    teams = models.ManyToManyField('players.Team', related_name='divisions', blank=True, verbose_name=_("Participants"))

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
    group_number = models.IntegerField(null=True, blank=True, verbose_name=_("Group number"))
    phase = models.CharField(
        max_length=10, default='group',
        choices=[('group', _("Group stage")), ('playoff', _("Playoff bracket"))],
        verbose_name=_("Phase"),
    )

    def __str__(self):
        t1 = self.team1 or self.bracket_label or 'TBD'
        t2 = self.team2 or ('Bye' if not self.bracket_label else 'TBD')
        return f"R{self.match_round}: {t1} vs {t2} ({self.division.name})"


class DivisionSeed(models.Model):
    """Records the seed number of a team within a division (optional seeding)."""
    division = models.ForeignKey(Division, on_delete=models.CASCADE, related_name='seeds')
    team = models.ForeignKey('players.Team', on_delete=models.CASCADE, related_name='division_seeds')
    seed_number = models.PositiveIntegerField(verbose_name=_("Seed number"))

    class Meta:
        unique_together = [('division', 'team'), ('division', 'seed_number')]
        ordering = ['seed_number']

    def __str__(self):
        return f"Seed {self.seed_number}: {self.team.name} ({self.division.name})"


class MedalOverride(models.Model):
    """Manually assigned medal for a division, overriding the computed result."""
    MEDAL_CHOICES = [
        ('gold',   _("Gold")),
        ('silver', _("Silver")),
        ('bronze', _("Bronze")),
    ]
    division = models.ForeignKey(Division, on_delete=models.CASCADE, related_name='medal_overrides')
    medal = models.CharField(max_length=10, choices=MEDAL_CHOICES)
    team = models.ForeignKey('players.Team', on_delete=models.CASCADE, related_name='medal_overrides')
    order = models.PositiveSmallIntegerField(default=1)

    class Meta:
        unique_together = [('division', 'medal', 'order')]
        ordering = ['medal', 'order']

    def __str__(self):
        return f"{self.get_medal_display()}: {self.team.name} ({self.division.name})"
