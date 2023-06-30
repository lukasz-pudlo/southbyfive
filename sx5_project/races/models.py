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


class Results(models.Model):
    race = models.ForeignKey(Race, on_delete=models.CASCADE)


class Runner(models.Model):
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    results = models.ManyToManyField(Results, blank=True)

    def __str__(self):
        return f'{self.first_name} {self.last_name}'
