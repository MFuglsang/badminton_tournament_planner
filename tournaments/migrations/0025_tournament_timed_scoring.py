from django.db import migrations, models
from django.utils.translation import gettext_lazy as _


class Migration(migrations.Migration):

    dependencies = [
        ('tournaments', '0024_tournamentplayerstatus'),
    ]

    operations = [
        migrations.AlterField(
            model_name='tournament',
            name='scoring_model',
            field=models.CharField(
                choices=[
                    ('best_of_3_21', _('Best of 3 sets to 21')),
                    ('best_of_5_15', _('Best of 3 sets to 15')),
                    ('timed', _('Timed match')),
                ],
                default='best_of_3_21',
                max_length=20,
                verbose_name=_('Scoring model'),
            ),
        ),
    ]
