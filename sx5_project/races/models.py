from django.db import models
from django.urls import reverse
from location_field.models.plain import PlainLocationField


class Race(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()
    park = models.CharField(default="Shawlands, Glasgow")
    coordinates = PlainLocationField(
        based_fields=['park'], zoom=13, default='55.82,-4.26')
    race_date = models.DateField()
    date_added = models.DateTimeField(auto_now=True)
    date_modified = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('races:detail', kwargs={'pk': self.pk})


class Runner(models.Model):
    RUNNER_CATEGORIES = [
        ('MS', 'MS'),
        ('FS', 'FS'),
        ('M40', 'M40'),
        ('F40', 'F40'),
        ('M50', 'M50'),
        ('F50', 'F50'),
        ('M60', 'M60'),
        ('F60', 'F60'),
        ('M70', 'M70'),
        ('F70', 'F70'),
        ('M80', 'M80'),
        ('F80', 'F80'),
    ]

    first_name = models.CharField(max_length=255)
    middle_name = models.CharField(max_length=255, blank=True, null=True)
    last_name = models.CharField(max_length=255)
    category = models.CharField(
        max_length=3, choices=RUNNER_CATEGORIES, null=True)

    def __str__(self):
        name_parts = [self.first_name, self.middle_name, self.last_name]
        return ' '.join(part for part in name_parts if part)


class Result(models.Model):
    race = models.ForeignKey(
        Race, on_delete=models.CASCADE, blank=True, null=True)
    runner = models.ForeignKey(
        Runner, on_delete=models.CASCADE, blank=True, null=True)
    time = models.DurationField(null=True)

    def __str__(self):
        return f'{self.runner} result for {self.race}'
