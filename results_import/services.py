"""What the results import does to the database.

Drafts only ever touch this app's own tables. Publishing creates the race
through the same code as the original "Add race" form. Reverting removes
exactly what publishing created; it never recalculates standings.
"""

import hashlib
from io import BytesIO

import openpyxl
from django.db import transaction
from django.db.models import Count, Max
from django.utils import timezone
from django.utils.text import slugify

from race_versions.models import RaceVersion
from races.importing import UNAFFILIATED, create_results_for_race
from races.models import Race, Runner
from races.utils import create_result_versions
from results_import import normalise
from results_import.models import ImportRule, ResultsUpload, RowChange, UploadRow
from results_import.normalise import APPLIED, DECIDED, MANUAL, PENDING, REVERTED

VALID_CATEGORIES = {code for code, _ in Runner.RUNNER_CATEGORIES}
CONVERTED_HEADERS = [
    "First Name",
    "Last Name",
    "Participant Number",
    "Category",
    "Club",
    "Time",
]


class ImportProblem(Exception):
    """Something the user asked for can't be done. The message is for them."""


# ------------------------------------------------------------------ drafts


def load_rules():
    rules = normalise.Rules()
    for rule in ImportRule.objects.filter(active=True):
        if rule.kind == ImportRule.NAME:
            rules.names[rule.from_key] = tuple(rule.to_value)
        elif rule.kind == ImportRule.CLUB:
            rules.clubs[rule.from_key] = rule.to_value
        else:
            rules.different.add(frozenset((rule.from_key, rule.to_value)))
    return rules


def build_reference(season):
    runners = [
        normalise.KnownRunner(pk, first, last, year, club or "")
        for pk, first, last, year, club in Runner.objects.values_list(
            "id", "first_name", "last_name", "season__season_start_year", "club"
        )
    ]
    return normalise.Reference(runners, season.season_start_year, load_rules())


@transaction.atomic
def create_draft(data, filename, season, race_name, race_date, description, user):
    """Read an uploaded file and store it as a draft with its proposed changes.
    Raises ``normalise.SheetError`` when the file can't be read."""
    sheet = normalise.read_sheet(data)
    proposals = normalise.propose(sheet, build_reference(season))
    upload = ResultsUpload.objects.create(
        season=season,
        race_name=race_name,
        race_date=race_date,
        description=description or "",
        original_filename=filename,
        original_file=data,
        sha256=hashlib.sha256(data).hexdigest(),
        file_headers=sheet.headers,
        ignored_headers=sheet.ignored_headers,
        uploaded_by=user,
    )
    for proposal in proposals:
        row = UploadRow.objects.create(
            upload=upload,
            number=proposal.number,
            raw=proposal.raw,
            first_name=proposal.first_name,
            last_name=proposal.last_name,
            bib=proposal.bib,
            category=proposal.category,
            club=proposal.club,
            time_text=proposal.time_text,
        )
        for change in proposal.changes:
            RowChange.objects.create(
                row=row,
                field=change.field,
                before=change.before,
                after=change.after,
                rule=change.rule,
                reason=change.reason,
                source=change.source,
                status=change.status,
                options=change.options,
            )
    return upload


def kept_rows(upload):
    """The rows that count: every row except those left out by hand."""
    return upload.rows.filter(left_out=False)


def blocking_problems(upload):
    kept = list(kept_rows(upload))
    rows = [
        {
            "number": row.number,
            "first_name": row.first_name,
            "last_name": row.last_name,
            "category": row.category,
            "time_text": row.time_text,
        }
        for row in kept
    ]
    problems = normalise.check_rows(rows, VALID_CATEGORIES)
    limit = Runner._meta.get_field("participant_number").max_length
    for row in kept:
        if len(row.bib) > limit:
            problems.setdefault(row.number, []).append(
                f"The number is longer than {limit} characters. "
                "Is the right column under the Number header?"
            )
    return problems


def number_warnings(upload):
    """Numbers to check before publishing, one entry per number.

    A number is listed when more than one row of the file carries it, or
    when, in a draft, this season's records have it for a runner who isn't
    on the row that carries it here. Neither stops publishing: a number is
    only shown on the site, never used to work anything out. But a shared
    number usually means the timing system put one finish against several
    people, so the times beside it want checking too.
    """
    if upload.status not in (ResultsUpload.DRAFT, ResultsUpload.PUBLISHED):
        return []
    by_bib = {}
    for row in kept_rows(upload):
        if row.bib:
            by_bib.setdefault(row.bib, []).append(row)

    holders = {}
    undecided = set()
    if upload.is_draft:
        for runner in Runner.objects.filter(season=upload.season):
            bib = _clean_bib(runner.participant_number)
            if bib in by_bib:
                holders.setdefault(bib, []).append(runner)
        # While a row's name is still a question, a different spelling on the
        # record is that question, not a second person with the number.
        undecided = set(
            pending_changes(upload)
            .filter(field="name")
            .values_list("row_id", flat=True)
        )

    warnings = []
    for bib, rows in by_bib.items():
        here = {(row.first_name, row.last_name) for row in rows}
        others = [
            runner
            for runner in holders.get(bib, [])
            if (runner.first_name, runner.last_name) not in here
        ]
        if all(row.id in undecided for row in rows):
            others = []
        if len(rows) < 2 and not others:
            continue
        times = {row.raw.get("time") or "" for row in rows}
        same_time = len(rows) > 1 and len(times) == 1 and times not in ({""}, {"DNF"})
        warnings.append(
            {
                "bib": bib,
                "rows": rows,
                "shared": len(rows) > 1,
                "same_time": times.pop() if same_time else "",
                "holders": others,
            }
        )
    warnings.sort(key=lambda warning: warning["rows"][0].number)
    return warnings


def pending_changes(upload):
    """Questions still open. A row that is left out asks nothing."""
    return RowChange.objects.filter(
        row__upload=upload, row__left_out=False, status=PENDING
    )


def _clean_bib(value):
    text = str(value or "").strip()
    if text.lower() == "nan":
        return ""
    return text[:-2] if text.endswith(".0") else text


def season_runners(upload):
    return {
        (runner.first_name, runner.last_name): runner
        for runner in Runner.objects.filter(season=upload.season)
    }


def record_differences(upload):
    """Where the file disagrees with a runner's existing record this season.
    The record wins unless the user asks for the file's club or number."""
    existing = season_runners(upload)
    using_file = {
        (change.row_id, change.field): change
        for change in RowChange.objects.filter(
            row__upload=upload, rule=RowChange.UPDATE_RECORD, status=APPLIED
        )
    }
    differences = []
    for row in kept_rows(upload):
        runner = row.runner if upload.is_published else None
        runner = runner or existing.get((row.first_name, row.last_name))
        if runner is None or runner.id in upload.created_runner_ids:
            continue
        pairs = [
            ("club", row.club, runner.club or ""),
            ("bib", row.bib, _clean_bib(runner.participant_number)),
            ("category", row.category, runner.category or ""),
        ]
        for name, in_file, on_record in pairs:
            change = using_file.get((row.id, name))
            if name == "club":
                same = (
                    normalise.is_blank_club(in_file)
                    and normalise.is_blank_club(on_record)
                ) or in_file == on_record
                file_blank = normalise.is_blank_club(in_file)
            else:
                same = in_file == on_record
                file_blank = not in_file
            if same and change is None:
                continue
            differences.append(
                {
                    "row": row,
                    "runner": runner,
                    "field": name,
                    "label": dict(RowChange.FIELDS)[name],
                    "in_file": in_file,
                    "on_record": change.before if change else on_record,
                    "file_blank": file_blank,
                    "change": change,
                    "can_use_file": name != "category" and not file_blank,
                }
            )
    return differences


def _same_decision(change):
    """Pending changes asking the same question on other rows (the same new
    club entered by several runners, say), this one included."""
    return [
        other
        for other in RowChange.objects.filter(
            row__upload=change.row.upload,
            row__left_out=False,
            status=PENDING,
            field=change.field,
            rule=change.rule,
        ).select_related("row")
        if other.before == change.before and other.options == change.options
    ]


def _require_draft(upload):
    if not upload.is_draft:
        raise ImportProblem("This upload is no longer a draft, so it can't be edited.")


def _require_kept(row):
    if row.left_out:
        raise ImportProblem(
            f"Row {row.number} is left out. Put it back before changing it."
        )


def _remember(change, option):
    row = change.row
    if option.get("remember_name"):
        ImportRule.objects.create(
            kind=ImportRule.NAME,
            from_key=normalise.name_rule_key(
                row.raw["first_name"], row.raw["last_name"]
            ),
            from_label=normalise.full_name(
                [row.raw["first_name"], row.raw["last_name"]]
            ),
            to_value=option["value"],
            to_label=normalise.full_name(option["value"]),
            created_from=change,
        )
    if option.get("remember_club"):
        ImportRule.objects.create(
            kind=ImportRule.CLUB,
            from_key=normalise.match_key(change.before),
            from_label=change.before,
            to_value=option["value"],
            to_label=option["value"],
            created_from=change,
        )
    for other_key in option.get("different_from", []):
        ImportRule.objects.create(
            kind=ImportRule.DIFFERENT,
            from_key=normalise.name_key(*option["value"]),
            from_label=normalise.full_name(option["value"]),
            to_value=other_key,
            to_label=other_key.replace("|", " "),
            created_from=change,
        )


@transaction.atomic
def decide(change, option_index, user, remember=True):
    """Answer a pending question. The answer goes to every row asking it."""
    _require_draft(change.row.upload)
    if change.status != PENDING:
        raise ImportProblem("This has already been decided.")
    if not 0 <= option_index < len(change.options):
        raise ImportProblem("Choose one of the options.")
    option = change.options[option_index]
    same = _same_decision(change)
    for other in same:
        row = other.row
        other.before = row.get_value(other.field)
        other.after = option["value"]
        other.chosen = option_index
        other.scope = option.get("scope", "row")
        other.status = APPLIED
        other.updated_by = user
        other.save()
        row.set_value(other.field, option["value"])
        row.save()
    if remember:
        _remember(change, option)
    return len(same)


def _name_taken(pair, season, excluding):
    return (
        Runner.objects.filter(first_name=pair[0], last_name=pair[1], season=season)
        .exclude(pk=excluding)
        .exists()
    )


def _rename_runner(runner, pair):
    """Rename a runner record. Refuses when the season already has another
    runner by that name: that would be merging two people, which changes who
    qualifies and so everyone's points."""
    if not pair[0].strip() or not pair[1].strip():
        raise ImportProblem("A runner needs both a first name and a last name.")
    if _name_taken(pair, runner.season, runner.pk):
        label = normalise.season_label(runner.season.season_start_year)
        raise ImportProblem(
            f'{label} already has another runner called "{normalise.full_name(pair)}". '
            "Renaming would merge two runner records, which changes the standings, "
            "so it isn't done here."
        )
    runner.first_name, runner.last_name = pair
    runner.save(update_fields=["first_name", "last_name"])


def _restore_affected(change):
    """Put back every runner record this change altered outside its own row."""
    skipped = []
    for item in reversed(change.affected):
        runner = (
            Runner.objects.select_related("season").filter(pk=item["runner_id"]).first()
        )
        if runner is None:
            continue
        if item["field"] == "name":
            if [runner.first_name, runner.last_name] != item["new"]:
                continue  # changed again since; leave it alone
            if _name_taken(item["old"], runner.season, runner.pk):
                skipped.append(normalise.full_name(item["old"]))
                continue
            runner.first_name, runner.last_name = item["old"]
            runner.save(update_fields=["first_name", "last_name"])
        else:
            column = "participant_number" if item["field"] == "bib" else item["field"]
            if getattr(runner, column) == item["new"]:
                setattr(runner, column, item["old"])
                runner.save(update_fields=[column])
    change.affected = []
    if skipped:
        change.note = "Not renamed back, the name is now taken: " + ", ".join(skipped)
    return skipped


POINTS_MESSAGE = (
    "Times and categories decide positions and points, so they can't be changed "
    "one at a time on a published race. Revert the whole upload, reopen it as a "
    "draft (your decisions are kept), make the change there and publish again."
)


def _set_published_value(change, value, upload):
    """Apply one side of a change to the live runner record."""
    row = change.row
    runner = row.runner
    if change.field in ("time", "category"):
        raise ImportProblem(POINTS_MESSAGE)
    if runner is None:
        raise ImportProblem("This row's runner record no longer exists.")
    if change.field == "name":
        _rename_runner(runner, value)
    elif runner.id not in upload.created_runner_ids:
        raise ImportProblem(
            "The site shows this runner's existing record for the season, which "
            "this change didn't alter, so there is nothing to put back."
        )
    elif change.field == "club":
        runner.club = value or UNAFFILIATED
        runner.save(update_fields=["club"])
    else:
        runner.participant_number = value
        runner.save(update_fields=["participant_number"])
    row.set_value(change.field, value)
    row.save()


@transaction.atomic
def revert_change(change, user):
    upload = change.row.upload
    row = change.row
    if change.status != APPLIED:
        raise ImportProblem("Only a change that is applied can be reverted.")
    if upload.status not in (ResultsUpload.DRAFT, ResultsUpload.PUBLISHED):
        raise ImportProblem("This upload is closed, so its changes can't be altered.")

    if change.rule == RowChange.ADDED:
        # Undoing an added row takes the row, and its later edits, out again.
        if upload.is_published:
            raise ImportProblem(POINTS_MESSAGE)
        row.delete()
        return
    if change.rule == RowChange.LEFT_OUT:
        # Undoing a leave-out puts the row back among the results.
        if upload.is_published:
            raise ImportProblem(POINTS_MESSAGE)
        row.left_out = False
        row.save(update_fields=["left_out"])
        change.status = REVERTED
    elif change.rule == RowChange.UPDATE_RECORD:
        if upload.is_published:
            _restore_affected(change)
        change.status = REVERTED
    else:
        if row.get_value(change.field) != change.after:
            raise ImportProblem(
                "This value was changed again afterwards. Revert the later change first."
            )
        if upload.is_published:
            if change.field in ("time", "category"):
                raise ImportProblem(POINTS_MESSAGE)
            if change.affected:
                _restore_affected(change)
            if change.before != change.after:
                _set_published_value(change, change.before, upload)
            elif row.runner is not None:
                # The decision kept the file's spelling and renamed other
                # records to it; with those put back, show what the row's
                # runner is called now.
                row.runner.refresh_from_db()
                row.set_value("name", [row.runner.first_name, row.runner.last_name])
                row.save()
            change.status = REVERTED
        else:
            row.set_value(change.field, change.before)
            row.save()
            if change.source == DECIDED and change.options:
                # An undone decision is a question again.
                change.status = PENDING
                change.after = None
                change.chosen = None
                change.scope = "row"
                ImportRule.objects.filter(created_from=change).delete()
            else:
                change.status = REVERTED
    change.updated_by = user
    change.save()


@transaction.atomic
def reapply_change(change, user):
    upload = change.row.upload
    row = change.row
    if change.status != REVERTED:
        raise ImportProblem("Only a reverted change can be applied again.")
    if upload.status not in (ResultsUpload.DRAFT, ResultsUpload.PUBLISHED):
        raise ImportProblem("This upload is closed, so its changes can't be altered.")
    if change.rule == RowChange.LEFT_OUT:
        leave_out(row, user)
        return
    if change.rule == RowChange.UPDATE_RECORD:
        if upload.is_published:
            raise ImportProblem(
                "Reopen the upload as a draft to use the file's value again."
            )
    else:
        if row.get_value(change.field) != change.before:
            raise ImportProblem(
                "This value has been changed since. Revert the later change first."
            )
        if upload.is_published:
            if change.scope != "row":
                raise ImportProblem(
                    "This change also renamed other records. Reopen the upload as "
                    "a draft to apply it again."
                )
            _set_published_value(change, change.after, upload)
        else:
            row.set_value(change.field, change.after)
            row.save()
    change.status = APPLIED
    change.updated_by = user
    change.save()


def _typed_value(field, value):
    """A hand-typed value, tidied the way the site holds it."""
    if field == "name":
        return [normalise.squeeze_spaces(part) for part in value]
    value = normalise.squeeze_spaces(value)
    if field == "category":
        value = value.upper()
    if field == "time" and value.upper() == normalise.DNF:
        value = normalise.DNF
    return value


def _check_typed_value(field, value):
    if field == "name" and not all(value):
        raise ImportProblem("A runner needs both a first name and a last name.")
    if field == "category" and value not in VALID_CATEGORIES:
        raise ImportProblem(f"\"{value}\" isn't one of the site's categories.")
    if field == "time" and not normalise.is_valid_time_text(value):
        raise ImportProblem("The time has to look like 00:23:45, 00:23:45 1 or DNF.")


@transaction.atomic
def edit_row(row, field, value, user):
    """Type a value in by hand. Recorded as a change like any other; if the
    field had an open question, the typed value answers it. Returns ``None``
    when the value is what the row already holds."""
    _require_draft(row.upload)
    _require_kept(row)
    before = row.get_value(field)
    value = _typed_value(field, value)
    if value == before:
        return None
    _check_typed_value(field, value)

    change = row.changes.filter(field=field, status=PENDING).first()
    if change is not None:
        change.before = before
        change.after = value
        change.source = MANUAL
        change.status = APPLIED
        change.chosen = None
        change.note = "Typed in by hand instead of choosing an option"
    else:
        change = RowChange(
            row=row,
            field=field,
            before=before,
            after=value,
            rule="manual",
            reason="Edited by hand",
            source=MANUAL,
            status=APPLIED,
        )
    change.updated_by = user
    change.save()
    row.set_value(field, value)
    row.save()
    return change


@transaction.atomic
def add_row(upload, values, user):
    """Add a finisher the file left out. ``values`` holds name, bib, category,
    club and time as typed. The row goes after the file's own rows; where the
    runner finished comes from the time, as for every other row."""
    _require_draft(upload)
    typed = {field: _typed_value(field, values[field]) for field, _ in RowChange.FIELDS}
    for field, value in typed.items():
        _check_typed_value(field, value)
    last = upload.rows.aggregate(Max("number"))["number__max"] or 1
    row = UploadRow(
        upload=upload,
        number=last + 1,
        raw={
            "first_name": "",
            "last_name": "",
            "bib": "",
            "category": "",
            "club": "",
            "time": "",
            "time_error": "",
            "time_is_precise": False,
            "added": True,
        },
    )
    for field, value in typed.items():
        row.set_value(field, value)
    row.save()
    RowChange.objects.create(
        row=row,
        field="name",
        before=None,
        after=typed["name"],
        rule=RowChange.ADDED,
        reason="Added by hand: this finisher isn't in the file",
        source=MANUAL,
        status=APPLIED,
        updated_by=user,
    )
    return row


@transaction.atomic
def leave_out(row, user):
    """Take a row out of the results: someone the file lists who didn't run.
    The row stays in the draft, marked, with its values as they were, and
    can be put back. Everyone behind moves up when the draft is published."""
    _require_draft(row.upload)
    if row.left_out:
        raise ImportProblem(f"Row {row.number} is already left out.")
    if row.is_added:
        raise ImportProblem(
            f"Row {row.number} was added by hand. Remove it in the list of "
            "changes instead."
        )
    change = row.changes.filter(rule=RowChange.LEFT_OUT).first() or RowChange(
        row=row,
        field="name",
        rule=RowChange.LEFT_OUT,
        reason="Left out by hand: in the file, but didn't run",
        source=MANUAL,
    )
    change.before = row.get_value("name")
    change.after = None
    change.status = APPLIED
    change.updated_by = user
    change.save()
    row.left_out = True
    row.save(update_fields=["left_out"])
    return change


def put_back(row, user):
    """Undo ``leave_out``."""
    change = row.changes.filter(rule=RowChange.LEFT_OUT, status=APPLIED).first()
    if change is None:
        raise ImportProblem(f"Row {row.number} isn't left out.")
    revert_change(change, user)


@transaction.atomic
def use_file_value(row, field, user):
    """Make the runner's existing record for the season take the file's club
    or number when this upload is published."""
    upload = row.upload
    _require_draft(upload)
    _require_kept(row)
    if field not in ("club", "bib"):
        raise ImportProblem("Only the club and the number can be taken from the file.")
    runner = season_runners(upload).get((row.first_name, row.last_name))
    if runner is None:
        raise ImportProblem("This runner has no record yet this season.")
    existing = row.changes.filter(rule=RowChange.UPDATE_RECORD, field=field).first()
    on_record = (
        runner.club if field == "club" else _clean_bib(runner.participant_number)
    )
    change = existing or RowChange(row=row, field=field, rule=RowChange.UPDATE_RECORD)
    change.before = on_record or ""
    change.after = row.get_value(field)
    change.reason = (
        f"Use the file's value for this runner's {upload.season_label} record"
    )
    change.source = DECIDED
    change.status = APPLIED
    change.scope = "season"
    change.updated_by = user
    change.save()
    return change


def discard_draft(upload, user):
    _require_draft(upload)
    upload.status = ResultsUpload.DISCARDED
    upload.reverted_by = user
    upload.reverted_at = timezone.now()
    upload.save()


# ---------------------------------------------------------- publish, revert


def _lock(upload):
    """Hold the upload's row for this transaction and work from its current
    state, so two requests can't publish or revert it at once."""
    ResultsUpload.objects.select_for_update().filter(pk=upload.pk).first()
    upload.refresh_from_db()


def race_slug(upload):
    return f"{slugify(upload.race_name)}-{upload.season_year}"


def existing_race(upload):
    return Race.objects.filter(slug=race_slug(upload)).first()


def _apply_renames(change, year):
    """Carry a name decision over to the runner's other records: this season's
    (scope "season") or every season's (scope "all")."""
    key = change.chosen_option.get("rename_key")
    if not key:
        return
    new = list(change.after)
    affected, notes = [], []
    runners = Runner.objects.select_related("season").order_by(
        "season__season_start_year"
    )
    for runner in runners:
        if normalise.name_key(runner.first_name, runner.last_name) != key:
            continue
        runner_year = runner.season.season_start_year
        if change.scope == "season" and runner_year != year:
            continue
        old = [runner.first_name, runner.last_name]
        if old == new:
            continue
        if _name_taken(new, runner.season, runner.pk):
            notes.append(
                f"{normalise.season_label(runner_year)} not renamed: another runner "
                "there already has this name"
            )
            continue
        runner.first_name, runner.last_name = new
        runner.save(update_fields=["first_name", "last_name"])
        affected.append(
            {
                "runner_id": runner.id,
                "field": "name",
                "old": old,
                "new": new,
                "season": runner_year,
            }
        )
    change.affected = affected
    change.note = "; ".join(notes)
    change.save()


def _apply_record_update(change, upload):
    row = change.row
    runner = Runner.objects.filter(
        first_name=row.first_name, last_name=row.last_name, season=upload.season
    ).first()
    if runner is None:
        return
    column = "participant_number" if change.field == "bib" else "club"
    old = getattr(runner, column)
    new = row.get_value(change.field) or (UNAFFILIATED if column == "club" else "")
    setattr(runner, column, new)
    runner.save(update_fields=[column])
    change.affected = [
        {"runner_id": runner.id, "field": change.field, "old": old, "new": new}
    ]
    change.after = new
    change.save()


def publish_blockers(upload):
    """Why this draft can't be published yet, as messages for the user."""
    blockers = []
    pending = pending_changes(upload).count()
    if pending:
        blockers.append(
            f"{pending} change{'s' if pending != 1 else ''} still need a decision."
        )
    problems = blocking_problems(upload)
    if problems:
        blockers.append(
            f"{len(problems)} row{'s' if len(problems) != 1 else ''} "
            "have a problem to fix."
        )
    return blockers


@transaction.atomic
def publish_upload(upload, user, replace=False):
    _lock(upload)
    _require_draft(upload)
    blockers = publish_blockers(upload)
    if blockers:
        raise ImportProblem(" ".join(blockers))

    season = upload.season
    year = upload.season_year
    current = existing_race(upload)
    if current is not None:
        previous = ResultsUpload.objects.filter(
            race=current, status=ResultsUpload.PUBLISHED
        ).first()
        if previous is None:
            raise ImportProblem(
                f"{upload.race_name} {upload.season_label} already has results that "
                "were added before the results import existed, so the import can't "
                "replace them. Delete that race first if these results should "
                "take its place."
            )
        if not replace:
            raise ImportProblem(
                f"{upload.race_name} {upload.season_label} already has results. "
                "Tick the box to replace them."
            )
        revert_upload(previous, user)

    season_races = Race.objects.filter(season_start_year=year)
    latest = dict(
        RaceVersion.objects.filter(race__in=season_races)
        .values_list("race_id")
        .annotate(Max("version_number"))
    )
    upload.versions_before = {
        str(race.id): latest.get(race.id, 0) for race in season_races
    }

    changes = list(
        RowChange.objects.filter(
            row__upload=upload, row__left_out=False, status=APPLIED
        ).select_related("row")
    )
    for change in changes:
        if change.field == "name" and change.scope in ("season", "all"):
            _apply_renames(change, year)
    for change in changes:
        if change.rule == RowChange.UPDATE_RECORD:
            _apply_record_update(change, upload)

    race = Race(
        name=upload.race_name,
        description=upload.description,
        race_date=upload.race_date,
        season_start_year=year,
        season=season,
        race_number=Race.objects.count() + 1,
    )
    race.save()

    rows = list(kept_rows(upload))
    _, created = create_results_for_race(
        race,
        season,
        [
            {
                "first_name": row.first_name,
                "last_name": row.last_name,
                "participant_number": row.bib,
                "category": row.category,
                "club": row.club,
                "time": row.time_text,
            }
            for row in rows
        ],
    )
    create_result_versions(race, season_start_year=year)

    results = {result.runner_id: result for result in race.result_set.all()}
    runners = season_runners(upload)
    for row in rows:
        row.runner = runners.get((row.first_name, row.last_name))
        row.result = results.get(row.runner_id)
        row.save(update_fields=["runner", "result"])

    upload.race = race
    upload.created_runner_ids = [runner.id for runner in created]
    upload.status = ResultsUpload.PUBLISHED
    upload.published_by = user
    upload.published_at = timezone.now()
    upload.save()
    return upload


def revert_blocker(upload):
    """Why this published upload can't be reverted right now, or ``""``.

    Only the season's most recent race can be undone exactly: a later race's
    standings were worked out with this one in place.
    """
    if not upload.is_published:
        return "Only a published upload can be reverted."
    race = upload.race
    if race is None:
        return ""
    later = (
        Race.objects.filter(
            season_start_year=upload.season_year, date_added__gt=race.date_added
        )
        .exclude(pk=race.pk)
        .order_by("date_added")
    )
    if later:
        names = ", ".join(r.name for r in later)
        return (
            f"Added after this race: {names}. Their standings were worked out with "
            "this race in place, so revert or delete the later ones first."
        )
    return ""


@transaction.atomic
def revert_upload(upload, user):
    """Undo a published upload: remove exactly what publishing created."""
    _lock(upload)
    blocker = revert_blocker(upload)
    if blocker:
        raise ImportProblem(blocker)

    race = upload.race
    if race is not None:
        for race_id, version in upload.versions_before.items():
            if int(race_id) != race.id:
                RaceVersion.objects.filter(
                    race_id=int(race_id), version_number__gt=version
                ).delete()
        race.delete()

    notes = []
    for change in RowChange.objects.filter(row__upload=upload).order_by("-id"):
        if change.affected:
            notes += _restore_affected(change)
            change.save()

    Runner.objects.filter(id__in=upload.created_runner_ids).annotate(
        results=Count("result")
    ).filter(results=0).delete()
    upload.rows.update(runner=None, result=None)

    upload.race = None
    upload.status = ResultsUpload.REVERTED
    upload.reverted_by = user
    upload.reverted_at = timezone.now()
    upload.save()
    return notes


@transaction.atomic
def reopen_as_draft(upload, user):
    """A new draft from a reverted or discarded upload, with every decision
    and edit carried over."""
    if upload.status not in (ResultsUpload.REVERTED, ResultsUpload.DISCARDED):
        raise ImportProblem("Only a reverted or discarded upload can be reopened.")
    draft = ResultsUpload.objects.create(
        season=upload.season,
        race_name=upload.race_name,
        race_date=upload.race_date,
        description=upload.description,
        original_filename=upload.original_filename,
        original_file=bytes(upload.original_file),
        sha256=upload.sha256,
        file_headers=upload.file_headers,
        ignored_headers=upload.ignored_headers,
        uploaded_by=user,
        reopened_from=upload,
    )
    for row in upload.rows.prefetch_related("changes"):
        copy = UploadRow.objects.create(
            upload=draft,
            number=row.number,
            raw=row.raw,
            first_name=row.first_name,
            last_name=row.last_name,
            bib=row.bib,
            category=row.category,
            club=row.club,
            time_text=row.time_text,
            left_out=row.left_out,
        )
        for change in row.changes.all():
            RowChange.objects.create(
                row=copy,
                field=change.field,
                before=change.before,
                after=change.after,
                rule=change.rule,
                reason=change.reason,
                source=change.source,
                status=change.status,
                options=change.options,
                chosen=change.chosen,
                scope=change.scope,
                updated_by=change.updated_by,
            )
    return draft


# ---------------------------------------------------------------- downloads


def converted_workbook(upload):
    """The upload as it stands, in the six-column format of the original
    "Add race" form. Every cell is text except the number."""
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Results"
    sheet.append(CONVERTED_HEADERS)
    for row in kept_rows(upload):
        bib = int(row.bib) if row.bib.isdigit() else row.bib or None
        sheet.append(
            [
                row.first_name,
                row.last_name,
                bib,
                row.category,
                row.club or None,
                row.time_text,
            ]
        )
    for cells in sheet.iter_rows(min_row=2):
        for cell in cells:
            if isinstance(cell.value, str):
                cell.number_format = "@"
    out = BytesIO()
    workbook.save(out)
    return out.getvalue()
