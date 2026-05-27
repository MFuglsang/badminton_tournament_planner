from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tournaments', '0021_remove_tournament_court_count_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='tier',
            field=models.CharField(
                choices=[
                    ('small', 'Small (up to 50 players)'),
                    ('medium', 'Medium (up to 200 players)'),
                    ('large', 'Large (unlimited)'),
                ],
                default='small',
                help_text='Determines how many players the club may register.',
                max_length=10,
                verbose_name='Club tier',
            ),
        ),
    ]
