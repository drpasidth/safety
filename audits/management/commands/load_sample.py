from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand
from django.db import transaction

from audits import sample_data
from audits.models import (AssessmentRound, Assignment, Consultant, Coordinator, Establishment, Finding, FindingPhoto,
                           ReportSettings, Result)

OFFICER_FIELDS = {"executive": "officers_executive", "supervisor": "officers_supervisor",
                  "technical": "officers_technical", "technical_adv": "officers_technical_adv",
                  "professional": "officers_professional"}


def _attach(field, path: Path):
    with path.open("rb") as fh:
        field.save(path.name, File(fh), save=False)


class Command(BaseCommand):
    help = "สร้างข้อมูลตัวอย่าง บริษัท แปซิฟิคเมล็ดพันธุ์ จำกัด (Initial Review และ Site Visit ครั้งที่ 2)"

    def add_arguments(self, parser):
        parser.add_argument("--replace", action="store_true", help="ลบข้อมูลตัวอย่างเดิมก่อนสร้างใหม่")

    @transaction.atomic
    def handle(self, *args, replace=False, **opts):
        data = sample_data.build()
        prof = data["profile"]
        existing = Establishment.objects.filter(name=prof["name"])
        if existing.exists():
            if not replace:
                self.stdout.write(self.style.WARNING("มีข้อมูลตัวอย่างอยู่แล้ว (ใช้ --replace เพื่อสร้างใหม่)"))
                return
            existing.delete()

        est = Establishment(
            name=prof["name"], product=prof["product"], business_type=prof["business_type"],
            address=prof["address"], employees=prof["employees"], certifications=prof["certifications"],
            productivity_description=prof["productivity"]["description"],
            productivity_value=prof["productivity"]["value"], productivity_period=prof["productivity"]["period"],
            strengths=prof["strengths"], weaknesses=prof["weaknesses"], scope=prof["scope"],
            **{OFFICER_FIELDS[k]: v for k, v in prof["officers"].items()})
        _attach(est.process_chart, prof["process_chart"])
        _attach(est.org_chart, prof["org_chart"])
        est.save()
        Coordinator.objects.bulk_create([Coordinator(establishment=est, order=i, **c)
                                         for i, c in enumerate(prof["coordinators"])])

        for r in data["rounds"]:
            rnd = AssessmentRound.objects.create(
                establishment=est, kind=r["type"], visit_no=r["visit_no"], date=r["date"],
                target_level=r["target_level"], recommended_level=r["recommended_level"],
                next_visit=r["next_visit"], problems=r["problems"], summary_note=r["summary_note"])
            Consultant.objects.bulk_create([Consultant(round=rnd, order=i, **c) for i, c in enumerate(r["consultants"])])
            Result.objects.bulk_create([Result(round=rnd, item_id=int(k), **v) for k, v in r["results"].items()])
            Assignment.objects.bulk_create([Assignment(round=rnd, order=i, **a) for i, a in enumerate(r["assignments"])])
            for i, f in enumerate(r["findings"]):
                finding = Finding.objects.create(round=rnd, order=i, location=f["location"],
                                                 description=f["description"], recommendation=f["recommendation"],
                                                 followup=f["followup"])
                for j, path in enumerate(f["photos"]):
                    photo = FindingPhoto(finding=finding, order=j)
                    _attach(photo.image, path)
                    photo.save()

        settings = ReportSettings.load()
        if not settings.logo:
            _attach(settings.logo, sample_data.LOGO)
            settings.save()
        self.stdout.write(self.style.SUCCESS(
            f"สร้าง {est.name} แล้ว: " + ", ".join(r.title for r in est.rounds.all())))
