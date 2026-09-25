# Generated manually for Player.has_arrived

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('players', '0013_userprofile'),
    ]

    operations = [
        migrations.AddField(
            model_name='player',
            name='has_arrived',
            field=models.BooleanField(default=False, help_text='Whether the player has checked in at the judge table.', verbose_name='Arrived'),
        ),
    ]
