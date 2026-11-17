from functools import wraps

from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from races.models import Runner
from results_import import normalise, services
from results_import.forms import UploadForm
from results_import.models import ImportRule, ResultsUpload, RowChange, UploadRow
from results_import.normalise import APPLIED, PENDING, REVERTED
from results_import.services import ImportProblem

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def staff_required(view):
    """Staff only. Visitors are sent to log in; other accounts are refused."""

    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not (request.user.is_active and request.user.is_staff):
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return wrapped


def _attempt(request, action, success=None):
    """Run a service call, turning a refusal into a message on the page."""
    try:
        result = action()
    except ImportProblem as problem:
        messages.error(request, str(problem))
        return None
    if success:
        messages.success(request, success(result) if callable(success) else success)
    return result


def _back(upload, anchor=""):
    response = redirect("results_import:detail", pk=upload.pk)
    if anchor:
        response["Location"] += f"#{anchor}"
    return response


@staff_required
def upload_list(request):
    uploads = ResultsUpload.objects.select_related("season", "race", "uploaded_by")
    return render(
        request,
        "results_import/upload_list.html",
        {"uploads": uploads.defer("original_file")},
    )


@staff_required
def upload_new(request):
    form = UploadForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        uploaded = form.cleaned_data["results_file"]
        data = uploaded.read()
        try:
            upload = services.create_draft(
                data=data,
                filename=uploaded.name,
                season=form.cleaned_data["season"],
                race_name=form.cleaned_data["race_name"],
                race_date=form.cleaned_data["race_date"],
                description=form.cleaned_data["description"],
                user=request.user,
            )
        except normalise.SheetError as error:
            form.add_error("results_file", str(error))
        else:
            earlier = (
                ResultsUpload.objects.filter(sha256=upload.sha256)
                .exclude(pk=upload.pk)
                .exclude(status=ResultsUpload.DISCARDED)
                .first()
            )
            if earlier is not None:
                messages.warning(
                    request,
                    "This exact file was uploaded before "
                    f"({earlier.race_name} {earlier.season_label}, "
                    f"{earlier.get_status_display().lower()}).",
                )
            return _back(upload)
    return render(request, "results_import/upload_form.html", {"form": form})


def _decision_groups(pending):
    """One card per question, however many rows ask it."""
    groups = {}
    for change in pending:
        key = (change.field, change.rule, repr(change.before), repr(change.options))
        group = groups.setdefault(key, {"change": change, "rows": []})
        group["rows"].append(change.row)
    return list(groups.values())


def _display(field, value):
    if value is None:
        return ""
    if field == "name":
        return normalise.full_name(value)
    return value


@staff_required
def upload_detail(request, pk):
    upload = get_object_or_404(
        ResultsUpload.objects.select_related("season", "race").defer("original_file"),
        pk=pk,
    )
    rows = list(upload.rows.select_related("runner"))
    changes = list(
        RowChange.objects.filter(row__upload=upload).select_related("row", "updated_by")
    )
    for change in changes:
        change.before_text = _display(change.field, change.before)
        change.after_text = _display(change.field, change.after)
        change.can_revert = (
            change.status == APPLIED
            and upload.status in (ResultsUpload.DRAFT, ResultsUpload.PUBLISHED)
            and (
                change.rule == RowChange.UPDATE_RECORD
                or change.row.get_value(change.field) == change.after
            )
        )
        change.can_reapply = (
            change.status == REVERTED
            and upload.status in (ResultsUpload.DRAFT, ResultsUpload.PUBLISHED)
            and change.rule != RowChange.UPDATE_RECORD
            and change.row.get_value(change.field) == change.before
        )

    pending = [c for c in changes if c.status == PENDING]
    made = [c for c in changes if c.status != PENDING]
    problems = services.blocking_problems(upload) if upload.is_draft else {}
    differences = services.record_differences(upload)

    if upload.is_published:
        new_ids = set(upload.created_runner_ids)
        is_new = lambda row: row.runner_id in new_ids  # noqa: E731
    else:
        known = set(services.season_runners(upload)) if upload.is_draft else set()
        is_new = lambda row: (  # noqa: E731
            upload.is_draft and (row.first_name, row.last_name) not in known
        )

    changed_rows = {c.row_id for c in changes if c.status == APPLIED}
    pending_rows = {c.row_id for c in pending}
    for row in rows:
        row.problems = problems.get(row.number, [])
        row.is_changed = row.id in changed_rows
        row.is_pending = row.id in pending_rows
        row.is_new = is_new(row)
        row.is_tie = " " in row.time_text
        row.raw_name = normalise.full_name(
            [row.raw["first_name"], row.raw["last_name"]]
        )
        row.name_differs = [row.first_name, row.last_name] != [
            row.raw["first_name"],
            row.raw["last_name"],
        ]
        row.club_differs = row.club != row.raw["club"]
        row.category_differs = row.category != row.raw["category"]

    current = services.existing_race(upload) if upload.is_draft else None
    replaces = None
    if current is not None:
        replaces = ResultsUpload.objects.filter(
            race=current, status=ResultsUpload.PUBLISHED
        ).first()

    context = {
        "upload": upload,
        "rows": rows,
        "decisions": _decision_groups(pending),
        "pending_count": len(pending),
        "made": made,
        "applied_count": sum(1 for c in made if c.status == APPLIED),
        "problem_rows": [row for row in rows if row.problems],
        "differences": [d for d in differences if not d["file_blank"]],
        "blank_differences": [d for d in differences if d["file_blank"]],
        "new_count": sum(1 for row in rows if row.is_new),
        "tie_count": sum(1 for row in rows if row.is_tie),
        "blockers": services.publish_blockers(upload) if upload.is_draft else [],
        "existing_race": current,
        "replaces": replaces,
        "revert_blocker": (
            services.revert_blocker(upload) if upload.is_published else ""
        ),
        "categories": [code for code, _ in Runner.RUNNER_CATEGORIES],
        "can_reopen": upload.status
        in (ResultsUpload.REVERTED, ResultsUpload.DISCARDED),
        "reopened_as": upload.reopened_as.defer("original_file").first(),
    }
    return render(request, "results_import/upload_detail.html", context)


def _change(pk, change_id):
    return get_object_or_404(
        RowChange.objects.select_related("row__upload__season"),
        pk=change_id,
        row__upload_id=pk,
    )


@staff_required
@require_POST
def change_decide(request, pk, change_id):
    change = _change(pk, change_id)
    try:
        option = int(request.POST.get("option", ""))
    except ValueError:
        messages.error(request, "Choose one of the options first.")
        return _back(change.row.upload, "decisions")
    _attempt(
        request,
        lambda: services.decide(
            change, option, request.user, remember=bool(request.POST.get("remember"))
        ),
        lambda count: (
            "Decision saved." if count == 1 else f"Decision saved for {count} rows."
        ),
    )
    return _back(change.row.upload, "decisions")


@staff_required
@require_POST
def change_revert(request, pk, change_id):
    change = _change(pk, change_id)
    _attempt(
        request,
        lambda: services.revert_change(change, request.user),
        "Change reverted.",
    )
    return _back(change.row.upload, "changes")


@staff_required
@require_POST
def change_reapply(request, pk, change_id):
    change = _change(pk, change_id)
    _attempt(
        request,
        lambda: services.reapply_change(change, request.user),
        "Change applied again.",
    )
    return _back(change.row.upload, "changes")


@staff_required
@require_POST
def row_edit(request, pk, row_id):
    row = get_object_or_404(
        UploadRow.objects.select_related("upload__season"), pk=row_id, upload_id=pk
    )
    edits = [
        (
            "name",
            [request.POST.get("first_name", ""), request.POST.get("last_name", "")],
        ),
        ("club", request.POST.get("club", "")),
        ("category", request.POST.get("category", "")),
        ("bib", request.POST.get("bib", "")),
        ("time", request.POST.get("time_text", "")),
    ]
    saved = 0
    for field, value in edits:
        try:
            if services.edit_row(row, field, value, request.user) is not None:
                saved += 1
        except ImportProblem as problem:
            messages.error(request, f"Row {row.number}: {problem}")
    if saved:
        messages.success(request, f"Row {row.number} updated.")
    return _back(row.upload, f"row-{row.number}")


@staff_required
@require_POST
def row_use_file(request, pk, row_id, field):
    row = get_object_or_404(
        UploadRow.objects.select_related("upload__season"), pk=row_id, upload_id=pk
    )
    _attempt(
        request,
        lambda: services.use_file_value(row, field, request.user),
        "The file's value will replace the record when this is published.",
    )
    return _back(row.upload, "differences")


def _upload(pk):
    return get_object_or_404(
        ResultsUpload.objects.select_related("season", "race"), pk=pk
    )


@staff_required
@require_POST
def upload_publish(request, pk):
    upload = _upload(pk)
    published = _attempt(
        request,
        lambda: services.publish_upload(
            upload, request.user, replace=bool(request.POST.get("replace"))
        ),
    )
    if published is not None:
        messages.success(
            request,
            f"{published.race_name} {published.season_label} is published. "
            "This page is now the record of what was changed.",
        )
    return _back(upload)


@staff_required
@require_POST
def upload_revert(request, pk):
    upload = _upload(pk)
    notes = _attempt(request, lambda: services.revert_upload(upload, request.user))
    if notes is not None:
        messages.success(
            request,
            f"{upload.race_name} {upload.season_label} has been taken off the site. "
            "Reopen it as a draft to change it and publish again.",
        )
        for name in notes:
            messages.warning(request, f'"{name}" could not be renamed back.')
    return _back(upload)


@staff_required
@require_POST
def upload_discard(request, pk):
    upload = _upload(pk)
    _attempt(
        request,
        lambda: services.discard_draft(upload, request.user),
        "Draft discarded.",
    )
    return redirect("results_import:list")


@staff_required
@require_POST
def upload_reopen(request, pk):
    upload = _upload(pk)
    draft = _attempt(
        request,
        lambda: services.reopen_as_draft(upload, request.user),
        "Reopened as a new draft with your decisions and edits kept.",
    )
    return _back(draft or upload)


def _download_name(upload, suffix):
    stem = upload.original_filename.rsplit(".", 1)[0]
    safe = (
        "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in stem) or "results"
    )
    return f"{safe}{suffix}.xlsx"


@staff_required
def upload_original(request, pk):
    upload = _upload(pk)
    response = HttpResponse(bytes(upload.original_file), content_type=XLSX)
    response["Content-Disposition"] = (
        f'attachment; filename="{_download_name(upload, "")}"'
    )
    return response


@staff_required
def upload_converted(request, pk):
    upload = _upload(pk)
    response = HttpResponse(services.converted_workbook(upload), content_type=XLSX)
    response["Content-Disposition"] = (
        f'attachment; filename="{_download_name(upload, "_converted")}"'
    )
    return response


@staff_required
def rule_list(request):
    rules = ImportRule.objects.filter(active=True).select_related(
        "created_from__row__upload__season"
    )
    return render(request, "results_import/rule_list.html", {"rules": rules})


@staff_required
@require_POST
def rule_forget(request, rule_id):
    rule = get_object_or_404(ImportRule, pk=rule_id)
    rule.active = False
    rule.save(update_fields=["active"])
    messages.success(
        request, f'Forgotten: "{rule.from_label}". You will be asked again next time.'
    )
    return redirect("results_import:rules")
