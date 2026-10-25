from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('players', '0014_player_has_arrived'),
        ('tournaments', '0024_tournamentplayerstatus'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='player',
            name='has_arrived',
        ),
    ]