from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tournaments', '0022_userprofile_tier'),
    ]

    operations = [
        migrations.AlterField(
            model_name='division',
            name='tournament_type',
            field=models.CharField(
                choices=[
                    ('group',       'Group (round-robin)'),
                    ('playoff',     'Group + playoff bracket'),
                    ('tree',        'Single elimination'),
                    ('double_elim', 'Double elimination'),
                ],
                default='group',
                max_length=12,
                verbose_name='Tournament type',
            ),
        ),
        migrations.AlterField(
            model_name='match',
            name='phase',
            field=models.CharField(
                choices=[
                    ('group',   'Group stage'),
                    ('playoff', 'Playoff bracket'),
                    ('winner',  'Winners bracket'),
                    ('loser',   'Losers bracket'),
                ],
                default='group',
                max_length=10,
                verbose_name='Phase',
            ),
        ),
    ]
