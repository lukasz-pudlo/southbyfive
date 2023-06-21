from django.db import models
from django.urls import reverse


class Race(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()
    location = models.CharField(max_length=255)
    race_date = models.DateField()
    date_added = models.DateTimeField(auto_now=True)
    date_modified = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('races:detail', kwargs={'pk': self.pk})
