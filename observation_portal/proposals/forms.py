from django import forms

from observation_portal.common.configdb import configdb
from observation_portal.requestgroups.models import RequestGroup
from observation_portal.proposals.models import TimeAllocation, CollaborationAllocation


class ProposalNotificationForm(forms.Form):
    notifications_enabled = forms.BooleanField(required=False)


class CollaborationAllocationForm(forms.ModelForm):
    class Meta:
        model = CollaborationAllocation
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['telescope_name'] = forms.ChoiceField(choices=configdb.get_telescope_name_tuples())


class TimeAllocationForm(forms.ModelForm):
    class Meta:
        model = TimeAllocation
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['instrument_type'] = forms.ChoiceField(choices=configdb.get_instrument_type_tuples())

    def clean(self):
        cleaned_data = super().clean()
        if self.instance.pk is None:
            return
        instrument_type_changed = cleaned_data.get('instrument_type') != self.instance.instrument_type
        semester_changed = cleaned_data.get('semester') != self.instance.semester
        if instrument_type_changed or semester_changed:
            # instrument_type has changed. We should block this if the old instrument_type was in use
            requestgroups = RequestGroup.objects.filter(proposal=self.instance.proposal).prefetch_related(
                'requests', 'requests__windows', 'requests__configurations'
            )
            for requestgroup in requestgroups:
                if requestgroup.observation_type != RequestGroup.DIRECT:
                    for request in requestgroup.requests.all():
                        if (request.time_allocation_key.instrument_type == self.instance.instrument_type and
                                request.time_allocation_key.semester == self.instance.semester.id):
                            raise forms.ValidationError("Cannot change TimeAllocation's instrument_type/semester when it is in use")


class TimeAllocationFormSet(forms.models.BaseInlineFormSet):
    def clean(self):
        super().clean()
        for form in self.forms:
            if not form.is_valid():
                return
            if form.cleaned_data and form.cleaned_data.get('DELETE'):
                requestgroups = RequestGroup.objects.filter(proposal=form.cleaned_data.get('proposal')).prefetch_related(
                    'requests', 'requests__windows', 'requests__configurations'
                )
                for requestgroup in requestgroups:
                    if requestgroup.observation_type != RequestGroup.DIRECT:
                        for request in requestgroup.requests.all():
                            if (request.time_allocation_key.instrument_type == form.cleaned_data.get('instrument_type') and
                                    request.time_allocation_key.semester == form.cleaned_data.get('semester').id):
                                raise forms.ValidationError('Cannot delete TimeAllocation when it is in use')
