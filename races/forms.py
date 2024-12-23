from django import forms
from .models import Race, Result
from datetime import timedelta


class RaceForm(forms.ModelForm):
    race_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        required=False
    )
    season_start_year = forms.IntegerField(
        required=True, label="Season Start Year")
    race_file = forms.FileField()

    class Meta:
        model = Race
        fields = ['name', 'description', 'race_date',
                  'race_file', 'season_start_year']


class ResultForm(forms.ModelForm):
    minutes = forms.IntegerField(min_value=0)
    seconds = forms.IntegerField(min_value=0, max_value=59)
    microseconds = forms.IntegerField(
        min_value=0, max_value=999999, required=False)

    class Meta:
        model = Result
        fields = ['race', 'runner', 'minutes', 'seconds', 'time']

    def save(self, commit=True):
        instance = super().save(commit=False)
        minutes = self.cleaned_data.get('minutes')
        seconds = self.cleaned_data.get('seconds')
        microseconds = self.cleaned_data.get('microseconds', 0)

        if minutes is not None and seconds is not None:
            instance.time = timedelta(
                minutes=minutes, seconds=seconds, microseconds=microseconds)

        if commit:
            instance.save()
            self.save_m2m()

        return instance
