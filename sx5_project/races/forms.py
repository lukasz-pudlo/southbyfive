from django import forms
from .models import Race
from location_field.forms.plain import PlainLocationField


class RaceForm(forms.ModelForm):
    race_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    park = forms.CharField()
    coordinates = PlainLocationField(based_fields=['park'],
                                     initial='55.82, -4.26')

    class Meta:
        model = Race
        fields = ['name', 'description', 'race_date', 'park']
