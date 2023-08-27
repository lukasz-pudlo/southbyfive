from django.db import models
from races.models import Race, Result


class RaceVersion(models.Model):
    race = models.ForeignKey(
        Race, on_delete=models.CASCADE, related_name='race_versions_versions')
    version_number = models.PositiveIntegerField()

    class Meta:
        unique_together = ['race', 'version_number']
        ordering = ['race', 'version_number']

    def __str__(self):
        return f"Version {self.version_number} of {self.race.name}"


class ResultVersion(models.Model):
    result = models.ForeignKey(
        Result, on_delete=models.CASCADE, related_name='race_versions_versions')
    race_version = models.ForeignKey(
        RaceVersion, on_delete=models.CASCADE, related_name='race_versions_result_versions')
    version = models.PositiveIntegerField()
    general_points = models.PositiveIntegerField(null=True, blank=True)
    gender_points = models.PositiveIntegerField(null=True, blank=True)
    category_points = models.PositiveIntegerField(null=True, blank=True)

    def __str__(self):
        return f'Version {self.version} of {self.result.runner} result for {self.result.race}'

    class Meta:
        ordering = ['general_points']
