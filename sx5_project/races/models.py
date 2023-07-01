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
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)

    def __str__(self):
        return f'{self.first_name} {self.last_name}'


class Result(models.Model):
    race = models.ForeignKey(
        Race, on_delete=models.CASCADE, blank=True, null=True)
    runner = models.ForeignKey(
        Runner, on_delete=models.CASCADE, blank=True, null=True)
    time = models.DurationField(null=True)

    def __str__(self):
        return f'{self.runner} result for {self.race}'
