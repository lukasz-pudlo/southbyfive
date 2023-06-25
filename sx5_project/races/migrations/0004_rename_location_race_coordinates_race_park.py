# Generated by Django 4.2.2 on 2023-06-25 00:07

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('races', '0003_race_location'),
    ]

    operations = [
        migrations.RenameField(
            model_name='race',
            old_name='location',
            new_name='coordinates',
        ),
        migrations.AddField(
            model_name='race',
            name='park',
            field=models.CharField(default='Shawlands, Glasgow'),
        ),
    ]