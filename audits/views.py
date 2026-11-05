import re

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Max
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import content_disposition_header
from django.views.decorators.http import require_POST

from core import pdf, scoring, standard

from . import services
from .forms import (AssignmentFormSet, ConclusionForm, ConsultantFormSet, CoordinatorFormSet, EstablishmentCreateForm,
                    EstablishmentForm, FindingForm, ReportSettingsForm, RoundCreateForm, RoundForm,
                    consultant_formset)
from .models import AssessmentRound, Establishment, Finding, FindingPhoto, ReportSettings

MIME = {"docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "pdf": "application/pdf"}


def status_text(site_visit: bool) -> dict:
    if site_visit:
        return {"C": "ดำเนินการแล้ว", "IP": "อยู่ระหว่างดำเนินการ", "NS": "ยังไม่ได้ดำเนินการ"}
    return {"C": "สอดคล้อง", "IP": "ไม่สอดคล้อง (กำลังดำเนินการ)", "NS": "ไม่สอดคล้อง (ไม่พบ)"}


def round_stats(rnd: AssessmentRound) -> dict:
    results = services.results_dict(rnd)
    level, chosen = services.effective_level(rnd, results)
    return {"results": results, "overall": scoring.overall(results), "levels": scoring.by_level(results),
            "suggested": scoring.suggested_level(results), "level": level, "level_chosen": chosen}


def _file(data: bytes, filename: str, fmt: str) -> HttpResponse:
    resp = HttpResponse(data, content_type=MIME[fmt])
    resp["Content-Disposition"] = content_disposition_header(True, filename)
    return resp


def _fname(*parts) -> str:
    return re.sub(r'[\\/:*?"<>|\s]+', "_", "_".join(str(p) for p in parts if p))


# ---------------------------------------------------------------- establishments

@login_required
def home(request):
    form = EstablishmentCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        est = form.save()
        messages.success(request, f"สร้าง {est.name} แล้ว กรอกข้อมูลสถานประกอบกิจการต่อได้เลย")
        return redirect("audits:establishment_edit", est.pk)
    rows = []
    for est in Establishment.objects.prefetch_related("rounds__results"):
        rounds = list(est.rounds.all())[-4:]
        rows.append({"est": est, "rounds": [{"rnd": r, "overall": scoring.overall(services.results_dict(r))}
                                            for r in rounds]})
    return render(request, "audits/home.html", {"rows": rows, "form": form, "level_counts": standard.level_counts()})


@login_required
def establishment(request, pk):
    est = get_object_or_404(Establishment, pk=pk)
    rounds = list(est.rounds.all())
    last = rounds[-1] if rounds else None
    if request.method == "POST":
        form = RoundCreateForm(request.POST)
        consultants = ConsultantFormSet(request.POST, prefix="cons")
        if form.is_valid() and consultants.is_valid():
            with transaction.atomic():
                rnd = form.save(commit=False)
                rnd.establishment = est
                rnd.save()
                consultants.instance = rnd
                consultants.save()
                if last:
                    services.copy_from(rnd, last, form.cleaned_data["copy_results"],
                                       form.cleaned_data["copy_findings"] and rnd.is_site_visit)
                est.save(update_fields=["updated_at"])
            messages.success(request, f"สร้างรอบ {rnd.title} แล้ว")
            return redirect("audits:checklist", rnd.pk)
    else:
        has_initial = any(not r.is_site_visit for r in rounds)
        visits = [r.visit_no for r in rounds if r.is_site_visit]
        form = RoundCreateForm(initial={
            "kind": AssessmentRound.SITE_VISIT if has_initial else AssessmentRound.INITIAL,
            "visit_no": (max(visits) + 1) if visits else (1 if has_initial else 0),
            "target_level": last.target_level if last else 4})
        initial = ([{"name": c.name, "role": c.role} for c in last.consultants.all()] if last
                   else [{"role": "หัวหน้าที่ปรึกษา"}, {"role": "ที่ปรึกษา"}])
        consultants = consultant_formset(len(initial) + 1)(prefix="cons", initial=initial)
    history = [{"rnd": r, **round_stats(r)} for r in rounds]
    return render(request, "audits/establishment.html", {
        "est": est, "history": list(reversed(history)), "form": form, "consultants": consultants, "last": last})


@login_required
def establishment_edit(request, pk):
    est = get_object_or_404(Establishment, pk=pk)
    form = EstablishmentForm(request.POST or None, request.FILES or None, instance=est)
    coords = CoordinatorFormSet(request.POST or None, instance=est, prefix="coord")
    if request.method == "POST" and form.is_valid() and coords.is_valid():
        form.save()
        coords.save()
        messages.success(request, "บันทึกข้อมูลสถานประกอบกิจการแล้ว")
        return redirect("audits:establishment", est.pk)
    return render(request, "audits/establishment_edit.html", {"est": est, "form": form, "coords": coords})


@login_required
@require_POST
def establishment_delete(request, pk):
    est = get_object_or_404(Establishment, pk=pk)
    if request.POST.get("confirm") != est.name:
        messages.error(request, "พิมพ์ชื่อสถานประกอบกิจการให้ตรงเพื่อยืนยันการลบ")
        return redirect("audits:establishment", est.pk)
    est.delete()
    messages.success(request, "ลบสถานประกอบกิจการแล้ว")
    return redirect("audits:home")


# ---------------------------------------------------------------- rounds

def _round(pk) -> AssessmentRound:
    return get_object_or_404(AssessmentRound.objects.select_related("establishment"), pk=pk)


@login_required
def round_detail(request, pk):
    rnd = _round(pk)
    stats = round_stats(rnd)
    results = stats["results"]
    subs = scoring.by_subclause(results)
    for s in subs:
        s["w"] = {k: 100 * s[k] / s["total"] for k in ("conform", "in_progress", "not_started", "unassessed")}
    nc = [{"item": i, "status": scoring.status_of(results, i["id"]),
           "evidence": results.get(str(i["id"]), {}).get("evidence", "")} for i in scoring.non_conforming(results)]
    return render(request, "audits/round_detail.html", {
        "rnd": rnd, "est": rnd.establishment, **stats, "subs": subs, "nc": nc,
        "labels": status_text(rnd.is_site_visit), "word": pdf.word_available()})


@login_required
def round_edit(request, pk):
    rnd = _round(pk)
    form = RoundForm(request.POST or None, instance=rnd)
    consultants = ConsultantFormSet(request.POST or None, instance=rnd, prefix="cons")
    if request.method == "POST" and form.is_valid() and consultants.is_valid():
        form.save()
        consultants.save()
        messages.success(request, "บันทึกข้อมูลรอบการตรวจแล้ว")
        return redirect("audits:round", rnd.pk)
    return render(request, "audits/round_edit.html", {"rnd": rnd, "est": rnd.establishment, "form": form,
                                                      "consultants": consultants})


@login_required
@require_POST
def round_delete(request, pk):
    rnd = _round(pk)
    est = rnd.establishment
    rnd.delete()
    messages.success(request, "ลบรอบการตรวจแล้ว")
    return redirect("audits:establishment", est.pk)


# ---------------------------------------------------------------- checklist

@login_required
def checklist(request, pk):
    rnd = _round(pk)
    subclauses = standard.subclauses()
    codes = [s["code"] for s in subclauses]
    code = request.GET.get("sub") or codes[0]
    if code not in codes and code != "all":
        raise Http404("ไม่พบข้อกำหนดย่อย")
    show = request.GET.get("show", "all")
    only_target = request.GET.get("target") == "1"

    if request.method == "POST":
        ids = [int(x) for x in request.POST.getlist("item")]
        valid = {i["id"] for i in standard.items()}
        updates = {}
        for iid in ids:
            if iid not in valid:
                continue
            status = request.POST.get(f"status_{iid}", "")
            updates[iid] = {"status": status if status in ("C", "IP", "NS") else "",
                            "evidence": request.POST.get(f"evidence_{iid}", "").strip()}
        if request.POST.get("action") == "all_c":
            for v in updates.values():
                v["status"] = "C"
        services.save_results(rnd, updates)
        messages.success(request, f"บันทึก {len(updates)} ข้อแล้ว")
        target = code
        if request.POST.get("action") == "next" and code in codes:
            target = codes[(codes.index(code) + 1) % len(codes)]
        query = f"?sub={target}&show={show}" + ("&target=1" if only_target else "")
        return redirect(reverse("audits:checklist", args=[rnd.pk]) + query)

    results = services.results_dict(rnd)

    def visible(item):
        s = scoring.status_of(results, item["id"])
        if only_target and item["min_level"] > rnd.target_level:
            return False
        return {"todo": s == "", "nc": s in ("IP", "NS")}.get(show, True)

    groups = []
    for sub in subclauses:
        if code != "all" and sub["code"] != code:
            continue
        rows, last_parent = [], None
        for item in standard.items():
            if item["subclause"] != sub["code"] or not visible(item):
                continue
            res = results.get(str(item["id"]), {})
            parent = item.get("parent")
            rows.append({"item": item, "status": res.get("status", ""), "evidence": res.get("evidence", ""),
                         "parent": parent if parent and parent != last_parent else None,
                         "levels": [(lvl, lvl >= item["min_level"]) for lvl in standard.LEVELS]})
            last_parent = parent or last_parent
        groups.append({"sub": sub, "rows": rows})

    progress = {s["code"]: s for s in scoring.by_subclause(results)}
    idx = codes.index(code) if code in codes else None
    return render(request, "audits/checklist.html", {
        "rnd": rnd, "est": rnd.establishment, "groups": groups, "code": code, "show": show,
        "only_target": only_target, "overall": scoring.overall(results), "labels": status_text(rnd.is_site_visit),
        "nav": [{"sub": s, "p": progress[s["code"]]} for s in subclauses],
        "prev_code": codes[idx - 1] if idx is not None else None,
        "next_code": codes[(idx + 1) % len(codes)] if idx is not None else None})


@login_required
@require_POST
def checklist_item(request, pk, item_id):
    rnd = _round(pk)
    if item_id not in {i["id"] for i in standard.items()}:
        raise Http404
    values = {}
    if "status" in request.POST:
        s = request.POST["status"]
        values["status"] = s if s in ("C", "IP", "NS") else ""
    if "evidence" in request.POST:
        values["evidence"] = request.POST["evidence"].strip()
    services.save_results(rnd, {item_id: values})
    return JsonResponse({"ok": True, "overall": scoring.overall(services.results_dict(rnd))})


# ---------------------------------------------------------------- findings / assignments / conclusion

@login_required
def findings(request, pk):
    rnd = _round(pk)
    prev = rnd.establishment.rounds.filter(date__lt=rnd.date).exclude(pk=rnd.pk).last()
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "add":
            order = (rnd.findings.aggregate(m=Max("order"))["m"] or 0) + 1
            f = Finding.objects.create(round=rnd, order=order, followup="pending" if rnd.is_site_visit else "")
            return redirect("audits:finding_edit", f.pk)
        if action == "copy" and prev:
            n = services.copy_findings(rnd, prev)
            messages.success(request, f"ยก {n} ประเด็นจาก {prev.title} แล้ว")
        return redirect("audits:findings", rnd.pk)
    return render(request, "audits/findings.html", {
        "rnd": rnd, "est": rnd.establishment, "prev": prev,
        "findings": rnd.findings.prefetch_related("photos")})


@login_required
def finding_edit(request, pk):
    f = get_object_or_404(Finding.objects.select_related("round__establishment"), pk=pk)
    rnd = f.round
    if request.method == "POST" and request.POST.get("action") in ("delete", "photo_delete", "up", "down"):
        action = request.POST["action"]
        if action == "delete":
            f.delete()
            messages.success(request, "ลบประเด็นแล้ว")
            return redirect("audits:findings", rnd.pk)
        if action == "photo_delete":
            FindingPhoto.objects.filter(finding=f, pk=request.POST.get("photo")).delete()
        else:
            items = list(rnd.findings.all())
            i = items.index(f)
            j = i - 1 if action == "up" else i + 1
            if 0 <= j < len(items):
                items[i], items[j] = items[j], items[i]
                for n, obj in enumerate(items):
                    Finding.objects.filter(pk=obj.pk).update(order=n)
            return redirect("audits:findings", rnd.pk)
        return redirect("audits:finding_edit", f.pk)
    form = FindingForm(request.POST or None, request.FILES or None, instance=f, site_visit=rnd.is_site_visit)
    if request.method == "POST" and form.is_valid():
        form.save()
        start = f.photos.count()
        for n, img in enumerate(form.cleaned_data["new_photos"]):
            FindingPhoto.objects.create(finding=f, image=img, order=start + n)
        messages.success(request, "บันทึกประเด็นแล้ว")
        return redirect("audits:findings", rnd.pk)
    return render(request, "audits/finding_edit.html", {"f": f, "rnd": rnd, "est": rnd.establishment, "form": form})


@login_required
def assignments(request, pk):
    rnd = _round(pk)
    if request.method == "POST" and request.POST.get("action") == "generate":
        n = services.generate_assignments(rnd)
        messages.success(request, f"สร้างรายการมอบหมาย {n} รายการจากข้อที่ยังไม่สอดคล้องแล้ว")
        return redirect("audits:assignments", rnd.pk)
    formset = AssignmentFormSet(request.POST or None, instance=rnd, prefix="a")
    if request.method == "POST" and formset.is_valid():
        objs = formset.save(commit=False)
        for obj in formset.deleted_objects:
            obj.delete()
        base = rnd.assignments.aggregate(m=Max("order"))["m"] or 0
        for n, obj in enumerate(objs, 1):
            if not obj.clause and not obj.task:
                continue
            if obj.pk is None:
                obj.order = base + n
            obj.save()
        messages.success(request, "บันทึกสิ่งที่มอบหมายแล้ว")
        return redirect("audits:assignments", rnd.pk)
    nc_count = len(scoring.non_conforming(services.results_dict(rnd)))
    return render(request, "audits/assignments.html", {"rnd": rnd, "est": rnd.establishment, "formset": formset,
                                                       "nc_count": nc_count})


@login_required
def conclusion(request, pk):
    rnd = _round(pk)
    form = ConclusionForm(request.POST or None, instance=rnd)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "บันทึกสรุปผลแล้ว")
        return redirect("audits:round", rnd.pk)
    return render(request, "audits/conclusion.html", {"rnd": rnd, "est": rnd.establishment, "form": form,
                                                      **round_stats(rnd)})


# ---------------------------------------------------------------- downloads

@login_required
def download_report(request, pk, fmt):
    rnd = _round(pk)
    if fmt not in ("docx", "pdf") or (fmt == "pdf" and not pdf.word_available()):
        raise Http404
    kind = "Initial_Review" if not rnd.is_site_visit else f"Site_Visit_{rnd.visit_no}"
    return _file(services.build_report(rnd, fmt == "pdf"),
                 _fname(kind, rnd.establishment.name, rnd.date) + f".{fmt}", fmt)


@login_required
def download_checklist(request, pk, fmt):
    rnd = _round(pk)
    if fmt not in MIME or (fmt == "pdf" and not pdf.word_available()):
        raise Http404
    kind = "Initial_Review" if not rnd.is_site_visit else f"Site_Visit_{rnd.visit_no}"
    return _file(services.build_checklist(rnd, fmt),
                 _fname("checklist", kind, rnd.establishment.name, rnd.date) + f".{fmt}", fmt)


@login_required
def download_blank_checklist(request, fmt):
    if fmt not in MIME or (fmt == "pdf" and not pdf.word_available()):
        raise Http404
    return _file(services.build_checklist(None, fmt), f"checklist_T-OSH_OSHMS_2023.{fmt}", fmt)


# ---------------------------------------------------------------- settings / standard

@login_required
def report_settings(request):
    obj = ReportSettings.load()
    form = ReportSettingsForm(request.POST or None, request.FILES or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "บันทึกการตั้งค่าแล้ว")
        return redirect("audits:settings")
    return render(request, "audits/settings.html", {"form": form, "obj": obj, "word": pdf.word_available()})


@login_required
def standard_view(request):
    sections = []
    for sec in standard.sections():
        subs = []
        for sub in sec["subclauses"]:
            subs.append({"sub": sub, "items": [i for i in standard.items() if i["subclause"] == sub["code"]]})
        sections.append({"sec": sec, "subs": subs})
    return render(request, "audits/standard.html", {"sections": sections, "level_counts": standard.level_counts(),
                                                    "word": pdf.word_available()})
