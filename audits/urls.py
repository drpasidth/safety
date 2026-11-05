from django.urls import path

from . import views

app_name = "audits"

urlpatterns = [
    path("", views.home, name="home"),
    path("standard/", views.standard_view, name="standard"),
    path("standard/checklist.<str:fmt>", views.download_blank_checklist, name="blank_checklist"),
    path("standard/context.<str:fmt>", views.download_blank_context, name="blank_context"),
    path("settings/", views.report_settings, name="settings"),
    path("establishments/<int:pk>/context/", views.context, name="context"),
    path("establishments/<int:pk>/context.<str:fmt>", views.download_context, name="context_download"),
    path("f/<str:token>/", views.public_context, name="public_context"),
    path("establishments/<int:pk>/", views.establishment, name="establishment"),
    path("establishments/<int:pk>/edit/", views.establishment_edit, name="establishment_edit"),
    path("establishments/<int:pk>/delete/", views.establishment_delete, name="establishment_delete"),
    path("rounds/<int:pk>/", views.round_detail, name="round"),
    path("rounds/<int:pk>/edit/", views.round_edit, name="round_edit"),
    path("rounds/<int:pk>/delete/", views.round_delete, name="round_delete"),
    path("rounds/<int:pk>/checklist/", views.checklist, name="checklist"),
    path("rounds/<int:pk>/checklist/<int:item_id>/", views.checklist_item, name="checklist_item"),
    path("rounds/<int:pk>/findings/", views.findings, name="findings"),
    path("findings/<int:pk>/", views.finding_edit, name="finding_edit"),
    path("rounds/<int:pk>/assignments/", views.assignments, name="assignments"),
    path("rounds/<int:pk>/conclusion/", views.conclusion, name="conclusion"),
    path("rounds/<int:pk>/report.<str:fmt>", views.download_report, name="report"),
    path("rounds/<int:pk>/checklist.<str:fmt>", views.download_checklist, name="round_checklist"),
]
