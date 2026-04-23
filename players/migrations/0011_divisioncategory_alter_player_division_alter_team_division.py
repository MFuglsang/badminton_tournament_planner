from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('players', '0010_alter_player_age'),
    ]

    operations = [
        migrations.CreateModel(
            name='DivisionCategory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=30, verbose_name='Navn')),
                ('sort_order', models.IntegerField(default=0, verbose_name='Sortering')),
                ('owner', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='division_categories',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Klubbruger',
                )),
            ],
            options={
                'ordering': ['sort_order', 'name'],
            },
        ),
        migrations.AddConstraint(
            model_name='divisioncategory',
            constraint=models.UniqueConstraint(fields=['owner', 'name'], name='unique_owner_category'),
        ),
        migrations.AlterField(
            model_name='player',
            name='division',
            field=models.CharField(blank=True, max_length=30, verbose_name='Division'),
        ),
        migrations.AlterField(
            model_name='team',
            name='division',
            field=models.CharField(blank=True, max_length=30, null=True, verbose_name='Række'),
        ),
    ]
