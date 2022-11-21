from django.forms import ModelForm, Textarea

from accounts.models import Configuration


class ConfigurationForm(ModelForm):
    class Meta:
        model = Configuration
        fields = ("key", "value")
        widgets = {
            "value": Textarea(attrs={"rows": 10, "cols": 100}),
        }
