from django import forms
from .models import Race


class RaceForm(forms.ModelForm):
    race_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'})
    )

    class Meta:
        model = Race
        fields = ['name', 'description', 'race_date']
