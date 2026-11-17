from datetime import timedelta

from django import forms

from .models import PARK_NAMES, Race, Result, ScheduledRace


class RaceForm(forms.ModelForm):
    race_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}), required=False
    )
    season_start_year = forms.IntegerField(required=True, label="Season Start Year")
    race_file = forms.FileField()

    class Meta:
        model = Race
        fields = ["name", "description", "race_date", "race_file", "season_start_year"]


class ResultForm(forms.ModelForm):
    minutes = forms.IntegerField(min_value=0)
    seconds = forms.IntegerField(min_value=0, max_value=59)
    microseconds = forms.IntegerField(min_value=0, max_value=999999, required=False)

    class Meta:
        model = Result
        fields = ["race", "runner", "minutes", "seconds", "time"]

    def save(self, commit=True):
        instance = super().save(commit=False)
        minutes = self.cleaned_data.get("minutes")
        seconds = self.cleaned_data.get("seconds")
        microseconds = self.cleaned_data.get("microseconds", 0)

        if minutes is not None and seconds is not None:
            instance.time = timedelta(
                minutes=minutes, seconds=seconds, microseconds=microseconds
            )

        if commit:
            instance.save()
            self.save_m2m()

        return instance


class RaceDatesForm(forms.Form):
    """The planned date of each park's race in one season. A blank date
    means none is shown for that park."""

    def __init__(self, *args, season, **kwargs):
        super().__init__(*args, **kwargs)
        self.season = season
        planned = dict(season.scheduled_races.values_list("name", "race_date"))
        for index, park in enumerate(PARK_NAMES):
            self.fields[f"park_{index}"] = forms.DateField(
                label=park,
                required=False,
                initial=planned.get(park),
                widget=forms.DateInput(
                    attrs={"type": "date", "class": "form-control"},
                    format="%Y-%m-%d",
                ),
            )

    def save(self):
        for index, park in enumerate(PARK_NAMES):
            planned = self.cleaned_data.get(f"park_{index}")
            if planned is None:
                ScheduledRace.objects.filter(season=self.season, name=park).delete()
            else:
                ScheduledRace.objects.update_or_create(
                    season=self.season, name=park, defaults={"race_date": planned}
                )
