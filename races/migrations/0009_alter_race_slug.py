# Generated by Django 4.2.2 on 2024-11-03 22:51

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('races', '0008_alter_race_slug'),
    ]

    operations = [
        migrations.AlterField(
            model_name='race',
            name='slug',
            field=models.SlugField(max_length=255, null=True, unique=True),
        ),
    ]
