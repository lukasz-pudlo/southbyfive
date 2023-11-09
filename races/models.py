from django.db import models
from django.urls import reverse


class Race(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    race_date = models.DateField(null=True, blank=True)
    date_added = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)
    race_file = models.FileField(
        upload_to='races/%Y/%m/%d/', null=True, blank=True)
    race_number = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('races:detail', kwargs={'pk': self.pk})

    def calculate_positions(self):
        results = list(self.result_set.all())

        # Calculate general position
        results.sort(key=lambda res: (res.time is None, res.time))
        for i, result in enumerate((res for res in results if res.time is not None), start=1):
            result.general_position = i
            result.save(update_fields=['general_position'])
        for result in (res for res in results if res.time is None):
            result.general_position = None
            result.save(update_fields=['general_position'])

        # Calculate position for each gender
        for gender_prefix in ['M', 'F', 'N']:
            gender_results = [
                res for res in results if res.runner.category.startswith(gender_prefix)]
            gender_results.sort(key=lambda res: (res.time is None, res.time))
            for i, result in enumerate((res for res in gender_results if res.time is not None), start=1):
                result.gender_position = i
                result.save(update_fields=['gender_position'])
            for result in (res for res in gender_results if res.time is None):
                result.gender_position = None
                result.save(update_fields=['gender_position'])

        # Calculate position for each category
        for category in Runner.RUNNER_CATEGORIES:
            cat_code = category[0]
            cat_results = [
                res for res in results if res.runner.category == cat_code]
            cat_results.sort(key=lambda res: (res.time is None, res.time))
            for i, result in enumerate((res for res in cat_results if res.time is not None), start=1):
                result.category_position = i
                result.save(update_fields=['category_position'])
            for result in (res for res in cat_results if res.time is None):
                result.category_position = None
                result.save(update_fields=['category_position'])

    class Meta:
        ordering = ['-date_added']


class Runner(models.Model):
    RUNNER_CATEGORIES = [
        ('MS', 'MS'),
        ('FS', 'FS'),
        ('NBS', 'NBS'),
        ('M40', 'M40'),
        ('F40', 'F40'),
        ('NB40', 'NB40'),
        ('M50', 'M50'),
        ('F50', 'F50'),
        ('NB50', 'NB50'),
        ('M60', 'M60'),
        ('F60', 'F60'),
        ('NB60', 'NB60'),
        ('M70', 'M70'),
        ('F70', 'F70'),
        ('NB70', 'NB70'),
        ('M80', 'M80'),
        ('F80', 'F80'),
        ('NB80', 'NB80'),
    ]

    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    participant_number = models.CharField(max_length=10, null=True, blank=True)
    category = models.CharField(
        max_length=10, choices=RUNNER_CATEGORIES, null=True)
    club = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        name_parts = [self.first_name, self.last_name]
        return ' '.join(part for part in name_parts if part)


class Result(models.Model):
    race = models.ForeignKey(
        Race, on_delete=models.CASCADE, blank=True, null=True)
    runner = models.ForeignKey(
        Runner, on_delete=models.CASCADE, blank=True, null=True)
    time = models.DurationField(null=True)
    general_position = models.PositiveIntegerField(null=True, blank=True)
    gender_position = models.PositiveIntegerField(null=True, blank=True)
    category_position = models.PositiveIntegerField(null=True, blank=True)
    club_position = models.PositiveIntegerField(null=True, blank=True)
    dnf = models.BooleanField(default=False)

    def __str__(self):
        return f'{self.runner} result for {self.race}'

    class Meta:
        ordering = ['dnf', 'time']
