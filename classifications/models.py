from django.db import models
from django.urls import reverse
from django.utils.text import slugify

from races.models import Race, Runner


class Classification(models.Model):
    race = models.ForeignKey(
        Race, on_delete=models.CASCADE, related_name="classifications"
    )
    version_number = models.PositiveIntegerField()
    slug = models.SlugField(max_length=255, unique=True, null=True)

    class Meta:
        unique_together = ["race", "version_number"]
        ordering = ["race", "version_number"]

    def __str__(self):
        return f"{self.name} Classification"

    @property
    def name(self):
        # Returns the name of the classification as the race name + ' Classification'
        return f"{self.race.slug} - Classification"

    def save(self, *args, **kwargs):
        # Set the slug based on the classification name
        if not self.slug:
            self.slug = slugify(self.name)
        super(Classification, self).save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("races:detail", kwargs={"slug": self.slug})


class ClassificationResult(models.Model):
    runner = models.ForeignKey(
        Runner, on_delete=models.CASCADE, related_name="classification_results"
    )
    classification = models.ForeignKey(
        Classification, on_delete=models.CASCADE, related_name="classification_results"
    )
    general_points = models.PositiveIntegerField(null=True, blank=True)
    gender_points = models.PositiveIntegerField(null=True, blank=True)
    category_points = models.PositiveIntegerField(null=True, blank=True)
    club_points = models.PositiveIntegerField(null=True, blank=True)

    def runner_category(self):
        return self.runner.category

    class Meta:
        ordering = ["general_points", "gender_points", "category_points"]

    def __str__(self):
        return f"Classification Result for {self.runner} in {self.classification}"
