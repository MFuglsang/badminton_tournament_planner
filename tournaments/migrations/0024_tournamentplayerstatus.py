from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('players', '0014_player_has_arrived'),
        ('tournaments', '0023_match_started_at'),
    ]

    operations = [
        migrations.CreateModel(
            name='TournamentPlayerStatus',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('has_arrived', models.BooleanField(default=False, verbose_name='Arrived')),
                ('player', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tournament_statuses', to='players.player')),
                ('tournament', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='player_statuses', to='tournaments.tournament')),
            ],
            options={
                'constraints': [
                    models.UniqueConstraint(fields=('tournament', 'player'), name='unique_tournament_player_status'),
                ],
            },
        ),
    ]