# Generated by Django 4.2.2 on 2023-06-24 23:04

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('races', '0001_initial'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='race',
            name='location',
        ),
    ]