# Generated by Django 4.2.2 on 2023-08-27 08:10

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('races', '0009_remove_resultversion_race_version_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='RaceVersion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('version_number', models.PositiveIntegerField()),
                ('race', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='race_versions_versions', to='races.race')),
            ],
            options={
                'ordering': ['race', 'version_number'],
                'unique_together': {('race', 'version_number')},
            },
        ),
        migrations.CreateModel(
            name='ResultVersion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('version', models.PositiveIntegerField()),
                ('general_points', models.PositiveIntegerField(blank=True, null=True)),
                ('gender_points', models.PositiveIntegerField(blank=True, null=True)),
                ('category_points', models.PositiveIntegerField(blank=True, null=True)),
                ('race_version', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='race_versions_result_versions', to='race_versions.raceversion')),
                ('result', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='race_versions_versions', to='races.result')),
            ],
            options={
                'ordering': ['general_points'],
            },
        ),
    ]
