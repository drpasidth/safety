import io
import shutil
import tempfile
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from docx import Document
from openpyxl import load_workbook
from PIL import Image

from core import scoring

from . import services
from .models import AssessmentRound, ContextAnalysis, ContextIssue, Establishment, Finding, Questionnaire, Result

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
                reverse("audits:establishment_edit", args=[self.est.pk]),
                reverse("audits:context", args=[self.est.pk])]
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

    def test_context_form(self):
        url = reverse("audits:context", args=[self.est.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.post(url, {"action": "prefill"})
        n_parties = self.est.interested_parties.count()
        self.assertEqual(n_parties, len(services.DEFAULT_PARTIES))
        self.assertGreater(self.est.context_issues.count(), 0)

        mgmt = lambda p, n: {f"{p}-TOTAL_FORMS": n, f"{p}-INITIAL_FORMS": 0, f"{p}-MIN_NUM_FORMS": 0,
                             f"{p}-MAX_NUM_FORMS": 1000}
        self.est.context_issues.all().delete()
        self.est.interested_parties.all().delete()
        resp = self.client.post(url, {
            "doc_no": "FM-OSH-001", "revision": "1", "effective_date": "2026-01-15", "prepared_by": "นายจัดทำ",
            "initial_review_note": "ทบทวนกฎหมายครบถ้วน",
            **mgmt("issue", 2), "issue-0-category": "legal", "issue-0-issue": "กฎกระทรวงความร้อนฉบับใหม่",
            "issue-0-nature": "risk", "issue-0-action": "ตรวจวัดความร้อน", "issue-1-nature": "risk",
            **mgmt("party", 1), "party-0-party": "ลูกจ้าง", "party-0-scope": "internal",
            "party-0-needs": "ทำงานปลอดภัย", "party-0-is_requirement": "on"})
        self.assertRedirects(resp, url)
        issue = self.est.context_issues.get()
        self.assertEqual((issue.scope, issue.order), ("external", 1))
        self.assertTrue(self.est.interested_parties.get().is_requirement)

        resp = self.client.get(reverse("audits:context_download", args=[self.est.pk, "docx"]))
        doc = Document(io.BytesIO(resp.content))
        cells = "\n".join(c.text for t in doc.tables for row in t.rows for c in row.cells)
        self.assertIn("กฎกระทรวงความร้อนฉบับใหม่", cells)
        self.assertIn("FM-OSH-001", cells)
        self.assertIn("ร้อยละ 68.64", "\n".join(p.text for p in doc.paragraphs))
        self.assertEqual(self.client.get(reverse("audits:blank_context", args=["docx"])).status_code, 200)

    def test_public_share_link(self):
        url = reverse("audits:context", args=[self.est.pk])
        self.client.post(url, {"action": "share_create", "days": 7})
        ctx = services.context_of(self.est)
        self.assertTrue(ctx.share_active)
        public = reverse("audits:public_context", args=[ctx.share_token])
        self.assertContains(self.client.get(url), public)

        other = Establishment.objects.create(name="บริษัท อื่น จำกัด")
        foreign = ContextIssue.objects.create(establishment=other, category="legal", issue="ของบริษัทอื่น")
        self.client.logout()
        resp = self.client.get(public)
        self.assertContains(resp, self.est.name)
        self.assertNotContains(resp, "ของบริษัทอื่น")
        mgmt = lambda p, n, i=0: {f"{p}-TOTAL_FORMS": n, f"{p}-INITIAL_FORMS": i, f"{p}-MIN_NUM_FORMS": 0,
                                  f"{p}-MAX_NUM_FORMS": 1000}
        form = {"submitter": "นางสาวผู้ประสาน (จป.วิชาชีพ)", "revision": "0",
                **mgmt("issue", 1), "issue-0-category": "social", "issue-0-issue": "ชุมชนร้องเรียนเรื่องฝุ่น",
                "issue-0-nature": "risk", **mgmt("party", 0)}
        self.assertRedirects(self.client.post(public, form), public, fetch_redirect_response=False)
        ctx.refresh_from_db()
        self.assertEqual(ctx.submitted_by, "นางสาวผู้ประสาน (จป.วิชาชีพ)")
        self.assertIsNotNone(ctx.submitted_at)
        self.assertTrue(self.est.context_issues.filter(issue="ชุมชนร้องเรียนเรื่องฝุ่น").exists())

        hijack = {**form, **mgmt("issue", 1, 1), "issue-0-id": foreign.pk, "issue-0-issue": "แก้ข้ามบริษัท"}
        self.client.post(public, hijack)
        foreign.refresh_from_db()
        self.assertEqual(foreign.issue, "ของบริษัทอื่น")

        self.assertEqual(self.client.post(public, {**form, "submitter": ""}).status_code, 200)

        ContextAnalysis.objects.filter(pk=ctx.pk).update(share_expires=date.today() - timedelta(days=1))
        self.assertEqual(self.client.get(public).status_code, 404)

        self.client.force_login(self.user)
        self.client.post(url, {"action": "share_create", "days": 30})
        self.assertEqual(self.client.get(public).status_code, 404)
        ctx.refresh_from_db()
        new_public = reverse("audits:public_context", args=[ctx.share_token])
        self.client.logout()
        self.assertEqual(self.client.get(new_public).status_code, 200)
        self.client.force_login(self.user)
        self.client.post(url, {"action": "share_disable"})
        self.client.logout()
        self.assertEqual(self.client.get(new_public).status_code, 404)

    def test_online_questionnaire_rating(self):
        self.client.post(reverse("audits:questionnaire_new", args=[self.est.pk]), {"scope": ["4.2.1"], "days": 30})
        q = Questionnaire.objects.get()
        self.assertEqual(q.scope, ["4.2.1"])
        public = reverse("audits:public_questionnaire", args=[q.token])
        self.client.logout()
        self.assertContains(self.client.get(public), "ประเด็นภายในที่ส่งผลต่อความสามารถ")

        answers = {"submitter": "นายผู้ตอบ (จป.)"}
        for n in range(3):
            answers |= {f"s_1_{n}": "2", f"n_1_{n}": "เอกสาร FM-01", f"s_2_{n}": "2", f"n_2_{n}": "ทะเบียนผู้มีส่วนได้ส่วนเสีย",
                        f"s_3_{n}": "1", f"s_4_{n}": "0"}
        answers["s_3_0"] = ""
        buf = io.BytesIO(b"%PDF-1.4 test")
        buf.name = "หลักฐาน.pdf"
        bad = io.BytesIO(b"MZ")
        bad.name = "virus.exe"
        resp = self.client.post(public, {**answers, "f_1": [buf, bad], "action": "submit"}, follow=True)
        self.assertContains(resp, "virus.exe")
        self.assertContains(resp, "ยังไม่ได้เลือกคำตอบ")
        q.refresh_from_db()
        self.assertEqual(q.status, Questionnaire.DRAFT)
        self.assertEqual(q.files.count(), 1)

        answers["s_3_0"] = "1"
        self.client.post(public, {**answers, "action": "submit"})
        q.refresh_from_db()
        self.assertEqual((q.status, q.submitted_by), (Questionnaire.SUBMITTED, "นายผู้ตอบ (จป.)"))
        r = services.rating(q)
        self.assertEqual([row["status"] for row in r["rows"]], ["C", "C", "IP", "NS"])
        self.assertAlmostEqual(r["pct"], 100 * (6 + 6 + 3 + 0) / 24)
        self.assertEqual(r["band"][0], "พอใช้")
        self.client.post(public, {**answers, "s_4_0": "2", "action": "save"})
        self.assertEqual(services.rating(q)["rows"][3]["status"], "NS")

        self.client.force_login(self.user)
        self.assertContains(self.client.get(reverse("audits:questionnaire", args=[q.pk])), "พอใช้")
        self.assertContains(self.client.get(reverse("audits:establishment", args=[self.est.pk])), q.title)
        resp = self.client.post(reverse("audits:questionnaire", args=[q.pk]),
                                {"action": "apply", "round": self.visit.pk})
        self.assertRedirects(resp, reverse("audits:checklist", args=[self.visit.pk]) + "?sub=4.2.1")
        self.assertEqual(Result.objects.get(round=self.visit, item_id=4).status, "NS")
        self.assertIn("ทะเบียนผู้มีส่วนได้ส่วนเสีย", Result.objects.get(round=self.visit, item_id=2).evidence)

        self.client.post(reverse("audits:questionnaire", args=[q.pk]), {"action": "reopen"})
        self.client.post(reverse("audits:questionnaire", args=[q.pk]), {"action": "close"})
        self.client.logout()
        self.assertEqual(self.client.get(public).status_code, 404)

    def test_questionnaire_list_page_creates(self):
        url = reverse("audits:questionnaires")
        self.assertContains(self.client.get(url), "แบบสอบถามประเมินตนเองออนไลน์")
        resp = self.client.post(url, {"establishment": self.est.pk, "scope": ["4.2.1", "4.2.2"], "days": 7})
        q = Questionnaire.objects.get()
        self.assertRedirects(resp, reverse("audits:questionnaire", args=[q.pk]))
        self.assertContains(self.client.get(url), q.title)

    def test_generated_questions_cover_every_requirement(self):
        from core import selfassess, standard
        for item in standard.items():
            qs = selfassess.questions(item)
            self.assertTrue(qs and all(q.endswith("หรือไม่") or q.startswith("ดำเนินการตาม") for q in qs), item["id"])

    def test_delete_requires_typed_name(self):
        self.client.post(reverse("audits:establishment_delete", args=[self.est.pk]), {"confirm": "ผิด"})
        self.assertTrue(Establishment.objects.filter(pk=self.est.pk).exists())
        self.client.post(reverse("audits:establishment_delete", args=[self.est.pk]), {"confirm": self.est.name})
        self.assertFalse(Establishment.objects.filter(pk=self.est.pk).exists())
