from django import forms
from django.contrib.auth import get_user_model

from .models import TicketTracking


class TrackingUpdateForm(forms.Form):
    internal_status = forms.ChoiceField(choices=TicketTracking.InternalStatus.choices)
    assigned_to = forms.ModelChoiceField(queryset=get_user_model().objects.none(), required=False)
    internal_priority = forms.ChoiceField(
        choices=(("", "Sem prioridade interna"), *TicketTracking.InternalPriority.choices),
        required=False,
    )
    next_action_at = forms.DateTimeField(
        required=False,
        input_formats=("%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S"),
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
    )
    revision = forms.IntegerField(min_value=0, widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        user_model = kwargs.pop("user_model", get_user_model())
        super().__init__(*args, **kwargs)
        self.fields["assigned_to"].queryset = user_model.objects.filter(is_active=True).order_by(
            "first_name", "last_name", "username",
        )


class TicketTrackingNoteForm(forms.Form):
    body = forms.CharField(
        min_length=1,
        max_length=2000,
        strip=True,
        widget=forms.Textarea(attrs={"rows": 3, "maxlength": 2000}),
    )
    revision = forms.IntegerField(min_value=0)


class TicketTrackingStatusForm(forms.Form):
    internal_status = forms.ChoiceField(choices=TicketTracking.InternalStatus.choices)
    revision = forms.IntegerField(min_value=0)


class TicketTrackingAssumeForm(forms.Form):
    revision = forms.IntegerField(min_value=0)
