# Generated by Django 4.2.2 on 2023-07-01 09:10

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('races', '0007_remove_runner_results_results_runners_results_time_and_more'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='Results',
            new_name='Result',
        ),
    ]