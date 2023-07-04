from django import forms
from .models import Race, Result
from location_field.forms.plain import PlainLocationField
from datetime import timedelta


class RaceForm(forms.ModelForm):
    race_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    park = forms.CharField()
    coordinates = PlainLocationField(based_fields=['park'],
                                     initial='55.82, -4.26')
    race_file = forms.FileField()

    class Meta:
        model = Race
        fields = ['name', 'description', 'race_date', 'park', 'race_file']


class ResultForm(forms.ModelForm):
    minutes = forms.IntegerField(min_value=0)
    seconds = forms.IntegerField(min_value=0, max_value=59)

    class Meta:
        model = Result
        fields = ['race', 'runner', 'minutes', 'seconds', 'time']

    def save(self, commit=True):
        instance = super().save(commit=False)
        minutes = self.cleaned_data.get('minutes')
        seconds = self.cleaned_data.get('seconds')

        if minutes is not None and seconds is not None:
            instance.time = timedelta(minutes=minutes, seconds=seconds)

        if commit:
            instance.save()
            self.save_m2m()

        return instance
