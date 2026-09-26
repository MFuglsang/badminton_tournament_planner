from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tournaments', '0022_userprofile_tier'),
    ]

    operations = [
        migrations.AddField(
            model_name='match',
            name='started_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Started at'),
        ),
    ]