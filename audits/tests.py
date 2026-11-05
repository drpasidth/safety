import io
import shutil
import tempfile

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from docx import Document
from openpyxl import load_workbook
from PIL import Image

from core import scoring

from . import services
from .models import AssessmentRound, Establishment, Finding, Result

MEDIA = tempfile.mkdtemp(prefix="oshms-test-media-")


@override_settings(MEDIA_ROOT=MEDIA)
class SampleFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("load_sample", stdout=io.StringIO())
        cls.user = User.objects.create_user("consultant", password="test-pass-123")
        cls.est = Establishment.objects.get()
        cls.initial, cls.visit = list(cls.est.rounds.all())

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def setUp(self):
        self.client.force_login(self.user)

    def test_login_required(self):
        self.client.logout()
        resp = self.client.get(reverse("audits:home"))
        self.assertRedirects(resp, reverse("login") + "?next=/")

    def test_sample_matches_example_reports(self):
        self.assertEqual(scoring.overall(services.results_dict(self.initial))["pct"], 68.64)
        self.assertEqual(scoring.overall(services.results_dict(self.visit))["pct"], 94.08)
        self.assertEqual(self.visit.findings.count(), 11)

    def test_every_page_renders(self):
        urls = [reverse("audits:home"), reverse("audits:standard"), reverse("audits:settings"),
                reverse("audits:establishment", args=[self.est.pk]),
                reverse("audits:establishment_edit", args=[self.est.pk])]
        for rnd in (self.initial, self.visit):
            urls += [reverse(f"audits:{name}", args=[rnd.pk])
                     for name in ("round", "round_edit", "checklist", "findings", "assignments", "conclusion")]
            urls += [reverse("audits:checklist", args=[rnd.pk]) + q for q in ("?sub=all", "?sub=4.4.4&show=nc&target=1")]
            urls.append(reverse("audits:finding_edit", args=[rnd.findings.first().pk]))
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_checklist_form_and_autosave(self):
        url = reverse("audits:checklist", args=[self.visit.pk])
        resp = self.client.post(url + "?sub=4.2.1", {"item": ["1", "2"], "status_1": "NS", "evidence_1": "ไม่พบเอกสาร",
                                                     "status_2": "IP", "evidence_2": "", "action": "next"})
        self.assertRedirects(resp, url + "?sub=4.2.2&show=all")
        r1 = Result.objects.get(round=self.visit, item_id=1)
        self.assertEqual((r1.status, r1.evidence), ("NS", "ไม่พบเอกสาร"))

        resp = self.client.post(reverse("audits:checklist_item", args=[self.visit.pk, 1]), {"status": "C"})
        self.assertEqual(resp.json()["ok"], True)
        self.assertEqual(Result.objects.get(round=self.visit, item_id=1).status, "C")
        self.assertEqual(self.client.post(reverse("audits:checklist_item", args=[self.visit.pk, 999]),
                                          {"status": "C"}).status_code, 404)

    def test_create_round_copies_previous(self):
        resp = self.client.post(reverse("audits:establishment", args=[self.est.pk]), {
            "kind": "site_visit", "visit_no": 3, "date": "2026-08-01", "target_level": 4,
            "copy_results": "on", "copy_findings": "on",
            "cons-TOTAL_FORMS": 1, "cons-INITIAL_FORMS": 0, "cons-MIN_NUM_FORMS": 0, "cons-MAX_NUM_FORMS": 1000,
            "cons-0-name": "นายทดสอบ ระบบ", "cons-0-role": "ที่ปรึกษา"})
        rnd = AssessmentRound.objects.get(visit_no=3)
        self.assertRedirects(resp, reverse("audits:checklist", args=[rnd.pk]))
        self.assertEqual(rnd.results.count(), 169)
        self.assertEqual(rnd.findings.count(), 11)
        self.assertEqual(rnd.consultants.get().name, "นายทดสอบ ระบบ")

    def test_finding_with_photo_upload(self):
        self.client.post(reverse("audits:findings", args=[self.initial.pk]), {"action": "add"})
        f = Finding.objects.filter(round=self.initial).order_by("-order").first()
        buf = io.BytesIO()
        Image.new("RGB", (40, 30), "red").save(buf, "PNG")
        buf.seek(0)
        buf.name = "photo.png"
        resp = self.client.post(reverse("audits:finding_edit", args=[f.pk]),
                                {"location": "คลังสินค้า", "description": "ทางเดินมีสิ่งกีดขวาง",
                                 "recommendation": "จัดระเบียบพื้นที่", "new_photos": [buf]})
        self.assertRedirects(resp, reverse("audits:findings", args=[self.initial.pk]))
        self.assertEqual(f.photos.count(), 1)

    def test_generate_assignments_and_conclusion(self):
        self.client.post(reverse("audits:assignments", args=[self.visit.pk]), {"action": "generate"})
        self.assertEqual(self.visit.assignments.count(), 10)
        self.client.post(reverse("audits:conclusion", args=[self.visit.pk]),
                         {"recommended_level": "", "next_visit": "2026-07-30", "summary_note": "", "problems": "x"})
        self.visit.refresh_from_db()
        self.assertIsNone(self.visit.recommended_level)
        self.assertEqual(str(self.visit.next_visit), "2026-07-30")

    def test_downloads(self):
        resp = self.client.get(reverse("audits:report", args=[self.initial.pk, "docx"]))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("attachment", resp["Content-Disposition"])
        text = "\n".join(p.text for p in Document(io.BytesIO(resp.content)).paragraphs)
        self.assertIn("ผลการทบทวนสถานะเริ่มต้น (Initial Review)", text)
        self.assertIn("ระดับ SC 2", text)

        resp = self.client.get(reverse("audits:round_checklist", args=[self.visit.pk, "xlsx"]))
        wb = load_workbook(io.BytesIO(resp.content))
        self.assertEqual(wb.sheetnames, ["Checklist", "สรุปผล"])

        for fmt in ("docx", "xlsx"):
            self.assertEqual(self.client.get(reverse("audits:blank_checklist", args=[fmt])).status_code, 200)
        self.assertEqual(self.client.get(reverse("audits:blank_checklist", args=["exe"])).status_code, 404)

    def test_delete_requires_typed_name(self):
        self.client.post(reverse("audits:establishment_delete", args=[self.est.pk]), {"confirm": "ผิด"})
        self.assertTrue(Establishment.objects.filter(pk=self.est.pk).exists())
        self.client.post(reverse("audits:establishment_delete", args=[self.est.pk]), {"confirm": self.est.name})
        self.assertFalse(Establishment.objects.filter(pk=self.est.pk).exists())
