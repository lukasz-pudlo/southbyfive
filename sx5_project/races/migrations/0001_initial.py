# Generated by Django 4.2.2 on 2023-07-16 10:46

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Race',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True, null=True)),
                ('race_date', models.DateField(blank=True, null=True)),
                ('date_added', models.DateTimeField(auto_now_add=True)),
                ('date_modified', models.DateTimeField(auto_now=True)),
                ('race_file', models.FileField(blank=True, null=True, upload_to='races/%Y/%m/%d/')),
            ],
            options={
                'ordering': ['-date_added'],
            },
        ),
        migrations.CreateModel(
            name='Runner',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('first_name', models.CharField(max_length=255)),
                ('middle_name', models.CharField(blank=True, max_length=255, null=True)),
                ('last_name', models.CharField(max_length=255)),
                ('category', models.CharField(choices=[('MS', 'MS'), ('FS', 'FS'), ('M40', 'M40'), ('F40', 'F40'), ('M50', 'M50'), ('F50', 'F50'), ('M60', 'M60'), ('F60', 'F60'), ('M70', 'M70'), ('F70', 'F70'), ('M80', 'M80'), ('F80', 'F80')], max_length=3, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='Result',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('time', models.DurationField(null=True)),
                ('race', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='races.race')),
                ('runner', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='races.runner')),
            ],
            options={
                'ordering': ['time'],
            },
        ),
    ]
