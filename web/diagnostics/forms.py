from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import FaultEvent, Site, Unit

MAX_UPLOAD = 5 * 1024 * 1024


class SignUpForm(UserCreationForm):
    pass


class SiteForm(forms.ModelForm):
    class Meta:
        model = Site
        fields = ["name", "city"]

    def __init__(self, *args, owner=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.owner = owner

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        qs = Site.objects.filter(owner=self.owner, name__iexact=name).exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("You already have a site with this name.")
        return name


class UnitForm(forms.ModelForm):
    class Meta:
        model = Unit
        fields = ["site", "name", "tonnage", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, owner=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["site"].queryset = Site.objects.filter(owner=owner)

    def clean_tonnage(self):
        t = self.cleaned_data.get("tonnage")
        if t is not None and not 1 <= t <= 200:
            raise forms.ValidationError("Rooftop units are between 1 and 200 tons.")
        return t


class UploadForm(forms.Form):
    csv_file = forms.FileField(label="Trend export (CSV)")

    def clean_csv_file(self):
        f = self.cleaned_data["csv_file"]
        if not f.name.lower().endswith(".csv"):
            raise forms.ValidationError("Upload a .csv file.")
        if f.size > MAX_UPLOAD:
            raise forms.ValidationError("The file is larger than 5 MB.")
        head = f.read(4096)
        f.seek(0)
        if b"\x00" in head:
            raise forms.ValidationError("This looks like a binary file, not a CSV export.")
        return f


class ReviewForm(forms.ModelForm):
    class Meta:
        model = FaultEvent
        fields = ["review_status", "technician_notes"]
        widgets = {"technician_notes": forms.Textarea(attrs={"rows": 3, "placeholder": "What did you find on site?"})}

    def clean(self):
        data = super().clean()
        if data.get("review_status") == FaultEvent.Review.CONFIRMED and not data.get("technician_notes", "").strip():
            self.add_error("technician_notes", "Add a short note on what you found when confirming a fault.")
        return data


class AssistantForm(forms.Form):
    text = forms.CharField(
        label="Describe what you see",
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "e.g. supply air stays warm even with the compressor at 100%"}),
        max_length=1000,
    )
