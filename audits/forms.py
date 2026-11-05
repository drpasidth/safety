from django import forms
from django.forms import inlineformset_factory

from core import standard

from .models import (AssessmentRound, Assignment, Consultant, Coordinator, Establishment, Finding,
                     ReportSettings)

DATE = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")


class BootstrapMixin:
    """Give every widget the Bootstrap class it needs."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            w = field.widget
            if isinstance(w, (forms.CheckboxInput,)):
                w.attrs.setdefault("class", "form-check-input")
            elif isinstance(w, (forms.Select, forms.SelectMultiple)):
                w.attrs.setdefault("class", "form-select")
            elif not isinstance(w, forms.HiddenInput):
                w.attrs.setdefault("class", "form-control")
            if isinstance(w, forms.Textarea):
                w.attrs.setdefault("rows", 3)


class EstablishmentForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Establishment
        exclude = ["created_at", "updated_at"]
        widgets = {"address": forms.Textarea(attrs={"rows": 2}), "scope": forms.Textarea(attrs={"rows": 2}),
                   "strengths": forms.Textarea(attrs={"rows": 5}), "weaknesses": forms.Textarea(attrs={"rows": 5})}


class EstablishmentCreateForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Establishment
        fields = ["name"]
        widgets = {"name": forms.TextInput(attrs={"placeholder": "บริษัท ... จำกัด"})}


class CoordinatorForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Coordinator
        fields = ["name", "position", "phone", "email"]


CoordinatorFormSet = inlineformset_factory(Establishment, Coordinator, form=CoordinatorForm, extra=1, can_delete=True)


class RoundForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = AssessmentRound
        fields = ["kind", "visit_no", "date", "target_level"]
        widgets = {"date": DATE}

    def clean(self):
        data = super().clean()
        if data.get("kind") == AssessmentRound.SITE_VISIT and not data.get("visit_no"):
            self.add_error("visit_no", "ระบุครั้งที่ของ Site Visit")
        if data.get("kind") == AssessmentRound.INITIAL:
            data["visit_no"] = 0
        return data


class RoundCreateForm(RoundForm):
    copy_results = forms.BooleanField(label="คัดลอกผลการตรวจจากรอบล่าสุดเป็นจุดเริ่มต้น", required=False, initial=True)
    copy_findings = forms.BooleanField(label="ยกข้อเสนอแนะจากรอบล่าสุดมาติดตามผล", required=False, initial=True)


class ConsultantForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Consultant
        fields = ["name", "role"]


def consultant_formset(extra: int = 1):
    return inlineformset_factory(AssessmentRound, Consultant, form=ConsultantForm, extra=extra, can_delete=True)


ConsultantFormSet = consultant_formset()


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleImageField(forms.ImageField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput(attrs={"accept": "image/*"}))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single = super().clean
        if isinstance(data, (list, tuple)):
            return [single(d, initial) for d in data]
        return [single(data, initial)] if data else []


class FindingForm(BootstrapMixin, forms.ModelForm):
    new_photos = MultipleImageField(label="เพิ่มรูปภาพ", required=False)

    class Meta:
        model = Finding
        fields = ["location", "description", "recommendation", "followup"]
        widgets = {"description": forms.Textarea(attrs={"rows": 5}),
                   "recommendation": forms.Textarea(attrs={"rows": 5})}

    def __init__(self, *args, site_visit=False, **kwargs):
        super().__init__(*args, **kwargs)
        if not site_visit:
            del self.fields["followup"]


class AssignmentForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Assignment
        fields = ["clause", "task"]
        widgets = {"task": forms.Textarea(attrs={"rows": 2})}


AssignmentFormSet = inlineformset_factory(AssessmentRound, Assignment, form=AssignmentForm, extra=2, can_delete=True)


class ConclusionForm(BootstrapMixin, forms.ModelForm):
    recommended_level = forms.TypedChoiceField(
        label="ที่ปรึกษาเห็นควรพิจารณาให้การรับรองอยู่ในระดับ", required=False, coerce=int, empty_value=None,
        choices=[("", "อัตโนมัติ (ระดับสูงสุดที่ผ่านครบทุกข้อ)"), (0, "ยังไม่ถึงระดับ SC1")]
        + [(lvl, f"SC{lvl}") for lvl in standard.LEVELS])

    class Meta:
        model = AssessmentRound
        fields = ["recommended_level", "next_visit", "summary_note", "problems"]
        widgets = {"next_visit": DATE, "problems": forms.Textarea(attrs={"rows": 5})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.is_site_visit:
            del self.fields["problems"]


class ReportSettingsForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = ReportSettings
        fields = "__all__"
        widgets = {"org_lines": forms.Textarea(attrs={"rows": 4}), "project_name": forms.Textarea(attrs={"rows": 3})}
