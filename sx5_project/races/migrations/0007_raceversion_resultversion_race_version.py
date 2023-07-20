# Generated by Django 4.2.2 on 2023-07-19 22:32

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('races', '0006_rename_points_resultversion_category_points_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='RaceVersion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('version_number', models.PositiveIntegerField()),
                ('race', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='versions', to='races.race')),
            ],
            options={
                'ordering': ['race', 'version_number'],
                'unique_together': {('race', 'version_number')},
            },
        ),
        migrations.AddField(
            model_name='resultversion',
            name='race_version',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.CASCADE, related_name='result_versions', to='races.raceversion'),
            preserve_default=False,
        ),
    ]