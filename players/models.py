from django.db import models
from django.utils.translation import gettext_lazy as _

# Create your models here.

class Player(models.Model):
    name = models.CharField(max_length=100, verbose_name=_("Name"))
    age = models.IntegerField(verbose_name=_("Age"))
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
    GENDER_CHOICES = [
        ('M', _('Mand')),
        ('K', _('Kvinde')),
    ]
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, default='M', verbose_name=_("Køn"))

    def __str__(self):
        return f"{self.name} ({self.get_gender_display()}, {self.division})"

class Team(models.Model):
    PAIR_TYPE_CHOICES = [
        ('double', _('Double')),
        ('mixed', _('Mixeddouble')),
    ]
    player1 = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='team_player1')
    player2 = models.ForeignKey(Player, on_delete=models.SET_NULL, related_name='team_player2', null=True, blank=True)
    pair_type = models.CharField(
        max_length=10, choices=PAIR_TYPE_CHOICES, null=True, blank=True,
        verbose_name=_('Par-type'),
        help_text=_('Double: samme køn · Mixeddouble: et af hvert'),
    )
    name = models.CharField(max_length=100, blank=True, null=True)

    @property
    def is_single(self):
        return self.player2 is None

    def save(self, *args, **kwargs):
        if not self.name:
            if self.player2:
                self.name = f"{self.player1.name} & {self.player2.name}"
            else:
                self.name = self.player1.name
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name
