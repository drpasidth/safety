from django.db import models
from django.urls import reverse

from core import standard

LEVEL_CHOICES = [(lvl, f"SC{lvl}") for lvl in standard.LEVELS]


class Establishment(models.Model):
    name = models.CharField("ชื่อสถานประกอบกิจการ", max_length=255)
    product = models.CharField("ชื่อสินค้า (ผลิตภัณฑ์) / บริการหลัก", max_length=255, blank=True)
    business_type = models.CharField("ประเภทของสถานประกอบกิจการ", max_length=255, blank=True)
    address = models.TextField("สถานที่ตั้ง", blank=True)
    employees = models.CharField("จำนวนพนักงาน (คน)", max_length=50, blank=True)
    officers_executive = models.CharField("จป. ระดับบริหาร", max_length=20, blank=True)
    officers_supervisor = models.CharField("จป. ระดับหัวหน้างาน", max_length=20, blank=True)
    officers_technical = models.CharField("จป. ระดับเทคนิค", max_length=20, blank=True)
    officers_technical_adv = models.CharField("จป. ระดับเทคนิคขั้นสูง", max_length=20, blank=True)
    officers_professional = models.CharField("จป. ระดับวิชาชีพ", max_length=20, blank=True)
    certifications = models.CharField("ระบบมาตรฐานที่ได้รับการรับรอง", max_length=255, blank=True)
    productivity_description = models.CharField("ผลิตภาพ: คำอธิบาย", max_length=255, blank=True)
    productivity_value = models.CharField("ผลิตภาพ: จำนวน/ปี", max_length=100, blank=True)
    productivity_period = models.CharField("ผลิตภาพ: ช่วงเวลา", max_length=100, blank=True)
    process_chart = models.ImageField("แผนผังกระบวนการผลิต", upload_to="charts/", blank=True)
    org_chart = models.ImageField("โครงสร้างการบริหารงาน", upload_to="charts/", blank=True)
    strengths = models.TextField("จุดแข็ง (บรรทัดละ 1 ข้อ)", blank=True)
    weaknesses = models.TextField("จุดอ่อน (บรรทัดละ 1 ข้อ)", blank=True)
    scope = models.TextField("ขอบข่ายการขอรับรอง", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "สถานประกอบกิจการ"
        verbose_name_plural = "สถานประกอบกิจการ"

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("audits:establishment", args=[self.pk])


class Coordinator(models.Model):
    establishment = models.ForeignKey(Establishment, on_delete=models.CASCADE, related_name="coordinators")
    name = models.CharField("ชื่อ-สกุล", max_length=255)
    position = models.CharField("ตำแหน่ง", max_length=255, blank=True)
    phone = models.CharField("เบอร์โทร", max_length=50, blank=True)
    email = models.CharField("อีเมล", max_length=255, blank=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "ผู้ประสานงาน"
        verbose_name_plural = "ผู้ประสานงาน"

    def __str__(self):
        return self.name


class AssessmentRound(models.Model):
    INITIAL, SITE_VISIT = "initial", "site_visit"
    KIND_CHOICES = list(standard.ROUND_TYPES.items())

    establishment = models.ForeignKey(Establishment, on_delete=models.CASCADE, related_name="rounds")
    kind = models.CharField("ประเภท", max_length=20, choices=KIND_CHOICES, default=INITIAL)
    visit_no = models.PositiveSmallIntegerField("ครั้งที่ (Site Visit)", default=0)
    date = models.DateField("วันที่ตรวจ")
    target_level = models.PositiveSmallIntegerField("ระดับที่สถานประกอบกิจการคาดหวัง", choices=LEVEL_CHOICES, default=4)
    recommended_level = models.PositiveSmallIntegerField(
        "ระดับที่ที่ปรึกษาเห็นควร", null=True, blank=True,
        help_text="ว่าง = ใช้ระดับสูงสุดที่ผ่านครบทุกข้อ, 0 = ยังไม่ถึง SC1")
    next_visit = models.DateField("นัดหมายครั้งถัดไป", null=True, blank=True)
    problems = models.TextField("ปัญหาอุปสรรคและข้อเสนอแนะ", blank=True)
    summary_note = models.TextField("ข้อความสรุปเพิ่มเติม", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["date", "id"]
        verbose_name = "รอบการตรวจประเมิน"
        verbose_name_plural = "รอบการตรวจประเมิน"

    def __str__(self):
        return f"{self.establishment} · {self.title}"

    @property
    def is_site_visit(self) -> bool:
        return self.kind == self.SITE_VISIT

    @property
    def title(self) -> str:
        return f"Site Visit ครั้งที่ {self.visit_no}" if self.is_site_visit else "Initial Review"

    def get_absolute_url(self):
        return reverse("audits:round", args=[self.pk])


class Consultant(models.Model):
    ROLE_CHOICES = [("หัวหน้าที่ปรึกษา", "หัวหน้าที่ปรึกษา"), ("ที่ปรึกษา", "ที่ปรึกษา"),
                    ("ผู้ตรวจประเมิน", "ผู้ตรวจประเมิน")]
    round = models.ForeignKey(AssessmentRound, on_delete=models.CASCADE, related_name="consultants")
    name = models.CharField("ชื่อ-สกุล", max_length=255)
    role = models.CharField("บทบาท", max_length=50, choices=ROLE_CHOICES, default="ที่ปรึกษา")
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "ที่ปรึกษา"
        verbose_name_plural = "ที่ปรึกษา"

    def __str__(self):
        return f"{self.role} {self.name}"


class Result(models.Model):
    STATUS_CHOICES = [("C", standard.STATUS_LABELS["C"]), ("IP", standard.STATUS_LABELS["IP"]),
                      ("NS", standard.STATUS_LABELS["NS"]), ("", "ยังไม่ประเมิน")]
    round = models.ForeignKey(AssessmentRound, on_delete=models.CASCADE, related_name="results")
    item_id = models.PositiveSmallIntegerField("ลำดับข้อกำหนด")
    status = models.CharField("ผลการตรวจ", max_length=2, choices=STATUS_CHOICES, blank=True)
    evidence = models.TextField("ผลการตรวจ / หลักฐาน", blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["item_id"]
        constraints = [models.UniqueConstraint(fields=["round", "item_id"], name="unique_result_per_item")]
        verbose_name = "ผลการตรวจรายข้อ"
        verbose_name_plural = "ผลการตรวจรายข้อ"

    def __str__(self):
        return f"{self.round_id}:{self.item_id}={self.status}"


class Finding(models.Model):
    FOLLOWUP_CHOICES = [("", "—"), ("pending", "รอดำเนินการ"), ("in_progress", "กำลังดำเนินการ"),
                        ("done", "ดำเนินการแก้ไขแล้ว")]
    round = models.ForeignKey(AssessmentRound, on_delete=models.CASCADE, related_name="findings")
    order = models.PositiveSmallIntegerField(default=0)
    location = models.CharField("จุด/พื้นที่", max_length=255, blank=True)
    description = models.TextField("คำอธิบาย (ประเด็นที่ไม่สอดคล้อง)", blank=True)
    recommendation = models.TextField("ข้อเสนอแนะในการปรับปรุงแก้ไข", blank=True)
    followup = models.CharField("สถานะการแก้ไข", max_length=20, choices=FOLLOWUP_CHOICES, blank=True)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "ข้อเสนอแนะ"
        verbose_name_plural = "ข้อเสนอแนะ"

    def __str__(self):
        return self.location or self.description[:60]


class FindingPhoto(models.Model):
    finding = models.ForeignKey(Finding, on_delete=models.CASCADE, related_name="photos")
    image = models.ImageField("รูปภาพ", upload_to="findings/%Y/%m/")
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]


class Assignment(models.Model):
    round = models.ForeignKey(AssessmentRound, on_delete=models.CASCADE, related_name="assignments")
    order = models.PositiveSmallIntegerField(default=0)
    clause = models.CharField("ข้อกำหนด", max_length=255, blank=True)
    task = models.TextField("สิ่งที่มอบหมาย", blank=True)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "สิ่งที่มอบหมาย"
        verbose_name_plural = "สิ่งที่มอบหมาย"


class ContextAnalysis(models.Model):
    establishment = models.OneToOneField(Establishment, on_delete=models.CASCADE, related_name="context")
    doc_no = models.CharField("เลขที่เอกสาร", max_length=50, blank=True)
    revision = models.CharField("แก้ไขครั้งที่", max_length=20, blank=True, default="0")
    effective_date = models.DateField("วันที่มีผลบังคับใช้", null=True, blank=True)
    reviewed_date = models.DateField("วันที่ทบทวนล่าสุด", null=True, blank=True)
    next_review = models.DateField("กำหนดทบทวนครั้งถัดไป", null=True, blank=True)
    prepared_by = models.CharField("ผู้จัดทำ", max_length=255, blank=True)
    prepared_position = models.CharField("ตำแหน่งผู้จัดทำ", max_length=255, blank=True)
    approved_by = models.CharField("ผู้อนุมัติ (นายจ้าง/ผู้บริหารสูงสุด)", max_length=255, blank=True)
    approved_position = models.CharField("ตำแหน่งผู้อนุมัติ", max_length=255, blank=True)
    initial_review_note = models.TextField(
        "การทบทวนสถานะเบื้องต้น (ข้อ 3)", blank=True,
        help_text="สรุปผลการทบทวนสถานะเบื้องต้น รวมถึงการปฏิบัติตามกฎหมายและข้อกำหนดอื่นที่เกี่ยวข้อง")
    effectiveness_note = models.TextField(
        "การติดตามประสิทธิผลของระบบ (ข้อ 4)", blank=True,
        help_text="วิธีติดตามว่าระบบการจัดการฯ ดำเนินการได้อย่างมีประสิทธิภาพและประสิทธิผล เช่น ตัวชี้วัด การทบทวนของฝ่ายบริหาร")
    share_token = models.CharField(max_length=64, unique=True, null=True, blank=True, editable=False)
    share_expires = models.DateField("ลิงก์ใช้ได้ถึง", null=True, blank=True)
    submitted_at = models.DateTimeField("ส่งข้อมูลออนไลน์ล่าสุด", null=True, blank=True)
    submitted_by = models.CharField("ผู้กรอกออนไลน์", max_length=255, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "บริบทของสถานประกอบกิจการ (4.2.1)"
        verbose_name_plural = "บริบทของสถานประกอบกิจการ (4.2.1)"

    def __str__(self):
        return f"บริบท · {self.establishment}"

    @property
    def share_active(self) -> bool:
        from django.utils import timezone
        return bool(self.share_token) and (self.share_expires is None
                                           or self.share_expires >= timezone.localdate())


INTERNAL, EXTERNAL = "internal", "external"
SCOPE_CHOICES = [(INTERNAL, "ภายใน"), (EXTERNAL, "ภายนอก")]
ISSUE_CATEGORIES = [
    ("ประเด็นภายใน", [
        ("people", "บุคลากร / ความสามารถ / จำนวนลูกจ้าง"),
        ("process", "กระบวนการผลิต / การปฏิบัติงาน"),
        ("equipment", "เครื่องจักร อุปกรณ์ และเทคโนโลยี"),
        ("workplace", "สถานที่และสภาพแวดล้อมในการทำงาน"),
        ("resources", "งบประมาณ / ทรัพยากร"),
        ("management", "การบริหาร / วัฒนธรรมความปลอดภัย / ระบบที่มีอยู่"),
    ]),
    ("ประเด็นภายนอก", [
        ("legal", "กฎหมายและข้อกำหนดอื่น ๆ"),
        ("economic", "เศรษฐกิจ / การแข่งขัน / ตลาด"),
        ("social", "สังคม / ชุมชนโดยรอบ"),
        ("technology", "เทคโนโลยีภายนอก"),
        ("environment", "สิ่งแวดล้อม / สภาพภูมิอากาศ / ภัยธรรมชาติ"),
        ("political", "นโยบายภาครัฐ / การเมือง"),
        ("supply", "ผู้รับเหมา / ผู้ส่งมอบ / ห่วงโซ่อุปทาน"),
    ]),
]
EXTERNAL_CATEGORIES = {k for k, _ in ISSUE_CATEGORIES[1][1]}


class ContextIssue(models.Model):
    RISK, OPPORTUNITY = "risk", "opportunity"
    NATURE_CHOICES = [(RISK, "ความเสี่ยง"), (OPPORTUNITY, "โอกาส")]

    establishment = models.ForeignKey(Establishment, on_delete=models.CASCADE, related_name="context_issues")
    order = models.PositiveSmallIntegerField(default=0)
    category = models.CharField("ประเภทประเด็น", max_length=20, choices=ISSUE_CATEGORIES)
    issue = models.TextField("ประเด็น")
    effect = models.TextField("ผลกระทบต่อความปลอดภัยฯ / ต่อการบรรลุผลของระบบ", blank=True)
    nature = models.CharField("ความเสี่ยง / โอกาส", max_length=20, choices=NATURE_CHOICES, default=RISK)
    action = models.TextField("การดำเนินการ / มาตรการ", blank=True)
    responsible = models.CharField("ผู้รับผิดชอบ", max_length=255, blank=True)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "ประเด็นภายในและภายนอก"
        verbose_name_plural = "ประเด็นภายในและภายนอก"

    def __str__(self):
        return self.issue[:60]

    @property
    def scope(self) -> str:
        return EXTERNAL if self.category in EXTERNAL_CATEGORIES else INTERNAL


class InterestedParty(models.Model):
    establishment = models.ForeignKey(Establishment, on_delete=models.CASCADE, related_name="interested_parties")
    order = models.PositiveSmallIntegerField(default=0)
    party = models.CharField("ผู้มีส่วนได้ส่วนเสีย", max_length=255)
    scope = models.CharField("ภายใน / ภายนอก", max_length=10, choices=SCOPE_CHOICES, default=INTERNAL)
    needs = models.TextField("ความต้องการและความคาดหวัง")
    is_requirement = models.BooleanField("นำมาเป็นข้อกำหนดที่ต้องปฏิบัติ", default=False,
                                         help_text="เช่น เป็นข้อกฎหมายหรือข้อตกลงที่ต้องปฏิบัติตาม")
    action = models.TextField("การตอบสนอง / การดำเนินการ", blank=True)
    responsible = models.CharField("ผู้รับผิดชอบ", max_length=255, blank=True)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "ผู้มีส่วนได้ส่วนเสีย"
        verbose_name_plural = "ผู้มีส่วนได้ส่วนเสีย"

    def __str__(self):
        return self.party


class ReportSettings(models.Model):
    org_lines = models.TextField("หัวกระดาษ (บรรทัดละ 1 บรรทัด)", default="\n".join([
        "สถาบันส่งเสริมความปลอดภัย อาชีวอนามัย และสภาพแวดล้อมในการทำงาน (องค์การมหาชน)",
        "Thailand Institute of Occupational Safety and Health (Public Organization)",
        "เลขที่ 18 ถนนบรมราชชนนี แขวงฉิมพลี เขตตลิ่งชัน กรุงเทพมหานคร",
        "โทรศัพท์ 0 2448 9111",
    ]))
    logo = models.ImageField("โลโก้", upload_to="settings/", blank=True)
    project_name = models.TextField("ชื่อโครงการ (หน้าปก)", default=(
        "โครงการพัฒนาศักยภาพสถานประกอบกิจการตามข้อกำหนดมาตรฐานระบบการจัดการด้านความปลอดภัย "
        "อาชีวอนามัย และสภาพแวดล้อมในการทำงาน (T-OSH OSHMS 2023)"))
    fiscal_year = models.CharField("ประจำปี", max_length=10, default="2569")
    font = models.CharField("ฟอนต์", max_length=100, default="TH SarabunPSK")
    font_size = models.PositiveSmallIntegerField("ขนาดตัวอักษรเนื้อหา", default=16)
    table_font_size = models.PositiveSmallIntegerField("ขนาดตัวอักษรในตาราง", default=14)

    class Meta:
        verbose_name = "ตั้งค่ารายงาน"
        verbose_name_plural = "ตั้งค่ารายงาน"

    def __str__(self):
        return "ตั้งค่ารายงาน"

    @classmethod
    def load(cls) -> "ReportSettings":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
