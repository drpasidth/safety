from django.contrib import admin

from .models import (AssessmentRound, Assignment, Consultant, Coordinator, Establishment, Finding, FindingPhoto,
                     ReportSettings, Result)


class CoordinatorInline(admin.TabularInline):
    model = Coordinator
    extra = 0


@admin.register(Establishment)
class EstablishmentAdmin(admin.ModelAdmin):
    list_display = ["name", "business_type", "updated_at"]
    search_fields = ["name", "address"]
    inlines = [CoordinatorInline]


class ConsultantInline(admin.TabularInline):
    model = Consultant
    extra = 0


class AssignmentInline(admin.TabularInline):
    model = Assignment
    extra = 0


@admin.register(AssessmentRound)
class AssessmentRoundAdmin(admin.ModelAdmin):
    list_display = ["establishment", "kind", "visit_no", "date", "target_level", "recommended_level"]
    list_filter = ["kind", "establishment"]
    inlines = [ConsultantInline, AssignmentInline]


@admin.register(Result)
class ResultAdmin(admin.ModelAdmin):
    list_display = ["round", "item_id", "status"]
    list_filter = ["status", "round__establishment"]


class FindingPhotoInline(admin.TabularInline):
    model = FindingPhoto
    extra = 0


@admin.register(Finding)
class FindingAdmin(admin.ModelAdmin):
    list_display = ["round", "order", "location", "followup"]
    inlines = [FindingPhotoInline]


admin.site.register(ReportSettings)
