from django import forms

from races.models import Race, Season

PARKS = [
    "King's Park",
    "Linn Park",
    "Rouken Glen",
    "Pollok Park",
    "Bellahouston Park",
    "Queen's Park",
]
MAX_UPLOAD_BYTES = 5 * 1024 * 1024


class UploadForm(forms.Form):
    results_file = forms.FileField(
        label="Results file",
        help_text="The Excel file as the organiser sent it. It is stored "
        "unchanged; nothing is published until you have reviewed it.",
    )
    race_name = forms.ChoiceField(label="Race", choices=[(p, p) for p in PARKS])
    season = forms.ModelChoiceField(
        queryset=Season.objects.order_by("-season_start_year"), empty_label=None
    )
    race_date = forms.DateField(
        required=False, widget=forms.DateInput(attrs={"type": "date"})
    )
    description = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"rows": 2})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["season"].label_from_instance = lambda season: (
            f"{season.season_start_year}/{(season.season_start_year + 1) % 100:02d}"
        )
        latest = Season.objects.order_by("-season_start_year").first()
        if latest is not None:
            self.fields["season"].initial = latest.pk
            done = set(
                Race.objects.filter(season=latest).values_list("name", flat=True)
            )
            upcoming = [park for park in PARKS if park not in done]
            if upcoming:
                self.fields["race_name"].initial = upcoming[0]

    def clean_results_file(self):
        uploaded = self.cleaned_data["results_file"]
        if uploaded.size > MAX_UPLOAD_BYTES:
            raise forms.ValidationError(
                "This file is larger than 5 MB, which is far more than a results "
                "sheet needs. Check it is the right file."
            )
        return uploaded
