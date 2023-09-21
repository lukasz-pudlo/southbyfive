from django.db import models
from races.models import Race, Runner


class Classification(models.Model):
    race = models.ForeignKey(
        Race, on_delete=models.CASCADE, related_name='classifications')
    version_number = models.PositiveIntegerField()

    class Meta:
        unique_together = ['race', 'version_number']
        ordering = ['race', 'version_number']

    def __str__(self):
        return f"Classification after {self.race.name}"


class ClassificationResult(models.Model):
    runner = models.ForeignKey(
        Runner, on_delete=models.CASCADE, related_name='classification_results')
    classification = models.ForeignKey(
        Classification, on_delete=models.CASCADE, related_name='classification_results')
    general_points = models.PositiveIntegerField(null=True, blank=True)
    gender_points = models.PositiveIntegerField(null=True, blank=True)
    category_points = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ['general_points']

    def __str__(self):
        return f'Classification Result for {self.runner} in {self.classification}'
