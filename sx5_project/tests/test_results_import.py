"""The results import end to end: upload, review, publish, revert."""

import io

import openpyxl
import pytest
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from classifications.models import Classification, ClassificationResult
from race_versions.models import RaceVersion, ResultVersion
from races.models import Race, Result, Runner, Season
from results_import import services
from results_import.models import ImportRule, ResultsUpload, RowChange
from results_import.services import ImportProblem
from sx5_project.tests.test_normalise import raw_file

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def plain_static_storage(settings):
    settings.STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        },
    }


@pytest.fixture
def season():
    Season.objects.create(season_start_year=2025)
    return Season.objects.create(season_start_year=2026)


@pytest.fixture
def staff():
    return User.objects.create_user("owner", password="p", is_staff=True)


@pytest.fixture
def staff_client(client, staff):
    client.force_login(staff)
    return client


FIELD = [
    # forename, surname, club, category, number, seconds
    ("Ann", "Archer", "Club A", "FS", 1, 1200.0),
    ("Bob", "Baker", "Club A", "MS", 2, 1260.4),
    ("Cat", "Cooper", "", "F40", 3, 1260.6),
    ("Dan", "Dixon", "Club B", "M40", 4, 1300.2),
    ("Eve", "Ellis", "Club B", "FS", 5, 1410.0),
]


def draft(season, staff, rows=FIELD, race_name="King's Park", filename="Kx5.xlsx"):
    return services.create_draft(
        data=raw_file(rows),
        filename=filename,
        season=season,
        race_name=race_name,
        race_date=None,
        description="",
        user=staff,
    )


def publish(season, staff, rows=FIELD, race_name="King's Park"):
    return services.publish_upload(draft(season, staff, rows, race_name), staff)


def post_file(client, season, rows=FIELD, race_name="King's Park", data=None):
    return client.post(
        reverse("results_import:new"),
        {
            "results_file": SimpleUploadedFile(
                "Kx5Lukazs.xlsx", data or raw_file(rows), content_type=XLSX
            ),
            "race_name": race_name,
            "season": season.pk,
        },
    )


def site_state():
    """Everything publishing can touch, for before-and-after comparison."""
    models = [
        Race, Runner, Result, RaceVersion, ResultVersion,
        Classification, ClassificationResult,
    ]  # fmt: skip
    state = {}
    for model in models:
        fields = [f.attname for f in model._meta.concrete_fields]
        fields = [f for f in fields if f not in ("date_modified",)]
        state[model.__name__] = sorted(model.objects.values_list(*fields), key=repr)
    return state


# ----------------------------------------------------------------- access


def test_visitors_are_sent_to_log_in(client):
    response = client.get(reverse("results_import:list"))
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


def test_accounts_without_staff_rights_are_refused(client):
    client.force_login(User.objects.create_user("member", password="p"))
    for name in ("results_import:list", "results_import:new", "results_import:rules"):
        assert client.get(reverse(name)).status_code == 403


def test_deleting_a_race_needs_staff_rights(client, season, staff):
    upload = publish(season, staff)
    url = reverse("races:delete", kwargs={"slug": upload.race.slug})
    assert client.post(url).status_code == 302
    client.force_login(User.objects.create_user("member", password="p"))
    assert client.post(url).status_code == 403
    assert Race.objects.count() == 1


# ----------------------------------------------------------------- drafts


def test_uploading_makes_a_draft_and_nothing_on_the_site(staff_client, season):
    data = raw_file(FIELD)
    response = post_file(staff_client, season, data=data)
    upload = ResultsUpload.objects.get()
    assert response.status_code == 302
    assert response["Location"] == reverse("results_import:detail", args=[upload.pk])
    assert upload.status == ResultsUpload.DRAFT
    assert bytes(upload.original_file) == data
    assert upload.rows.count() == 5
    assert (Race.objects.count(), Runner.objects.count(), Result.objects.count()) == (
        0,
        0,
        0,
    )


def test_the_original_file_downloads_unchanged(staff_client, season, staff):
    data = raw_file(FIELD)
    post_file(staff_client, season, data=data)
    upload = ResultsUpload.objects.get()
    response = staff_client.get(reverse("results_import:original", args=[upload.pk]))
    assert response.content == data


def test_a_file_with_the_wrong_columns_is_explained_on_the_form(staff_client, season):
    workbook = openpyxl.Workbook()
    workbook.active.append(["Name", "Time"])
    workbook.active.append(["Ann Archer", "00:20:00"])
    out = io.BytesIO()
    workbook.save(out)
    response = post_file(staff_client, season, data=out.getvalue())
    assert response.status_code == 200
    assert "these are missing" in response.content.decode()
    assert ResultsUpload.objects.count() == 0


def test_the_review_page_shows_changes_times_and_ties(staff_client, season, staff):
    rows = [("mark", "Bailkoski", "", "MS", 1, 1260.4)] + FIELD[1:]
    upload = draft(season, staff, rows)
    page = staff_client.get(reverse("results_import:detail", args=[upload.pk]))
    html = page.content.decode()
    assert page.status_code == 200
    assert "mark Bailkoski" in html and "Mark Bailkoski" in html
    assert "0:21:00.4" in html and "00:21:00 1" in html
    assert "Ready to publish" in html


def test_the_converted_file_is_in_the_six_column_format(staff_client, season, staff):
    upload = draft(season, staff)
    response = staff_client.get(reverse("results_import:converted", args=[upload.pk]))
    sheet = openpyxl.load_workbook(io.BytesIO(response.content)).active
    rows = list(sheet.iter_rows(values_only=True))
    assert rows[0] == (
        "First Name",
        "Last Name",
        "Participant Number",
        "Category",
        "Club",
        "Time",
    )
    assert rows[2] == ("Bob", "Baker", 2, "MS", "Club A", "00:21:00")
    assert rows[3] == ("Cat", "Cooper", 3, "F40", None, "00:21:01")


def test_a_change_can_be_reverted_and_applied_again(staff_client, season, staff):
    upload = draft(season, staff, [("mark", "Bailkoski", "", "MS", 1, 1200.0)])
    row = upload.rows.get()
    change = RowChange.objects.get()
    assert (row.first_name, change.status) == ("Mark", "applied")

    staff_client.post(
        reverse("results_import:change_revert", args=[upload.pk, change.pk])
    )
    row.refresh_from_db()
    change.refresh_from_db()
    assert (row.first_name, change.status) == ("mark", "reverted")

    staff_client.post(
        reverse("results_import:change_reapply", args=[upload.pk, change.pk])
    )
    row.refresh_from_db()
    assert row.first_name == "Mark"


def test_an_open_question_blocks_publishing_until_decided(staff_client, season, staff):
    Runner.objects.create(
        first_name="Margo",
        last_name="Brewer",
        category="FS",
        season=Season.objects.get(season_start_year=2025),
    )
    rows = FIELD + [("Margot", "Brewer", "", "FS", 6, 1500.0)]
    upload = draft(season, staff, rows)
    change = RowChange.objects.get(status="pending")

    staff_client.post(reverse("results_import:publish", args=[upload.pk]))
    upload.refresh_from_db()
    assert upload.status == ResultsUpload.DRAFT
    assert Race.objects.count() == 0

    staff_client.post(
        reverse("results_import:change_decide", args=[upload.pk, change.pk]),
        {"option": "0"},
    )
    staff_client.post(reverse("results_import:publish", args=[upload.pk]))
    upload.refresh_from_db()
    assert upload.status == ResultsUpload.PUBLISHED
    assert Runner.objects.filter(first_name="Margo", season=season).exists()


def test_an_undone_decision_becomes_a_question_again(season, staff):
    Runner.objects.create(
        first_name="B",
        last_name="B",
        category="FS",
        club="Migo Run Club",
        season=Season.objects.get(season_start_year=2025),
    )
    upload = draft(season, staff, [("James", "Young", "MIGO", "MS", 1, 1200.0)])
    change = RowChange.objects.get()
    services.decide(change, 0, staff)
    assert ImportRule.objects.filter(kind="club").count() == 1
    change.refresh_from_db()
    services.revert_change(change, staff)
    change.refresh_from_db()
    assert change.status == "pending"
    assert upload.rows.get().club == "MIGO"
    assert ImportRule.objects.count() == 0


def test_one_answer_covers_every_row_asking_the_same_question(season, staff):
    Runner.objects.create(
        first_name="B",
        last_name="B",
        category="FS",
        club="Migo Run Club",
        season=Season.objects.get(season_start_year=2025),
    )
    rows = [
        ("James", "Young", "MIGO", "MS", 1, 1200.0),
        ("Egbert", "Pos", "MIGO", "MS", 2, 1300.0),
    ]
    upload = draft(season, staff, rows)
    assert services.decide(RowChange.objects.first(), 0, staff) == 2
    assert set(upload.rows.values_list("club", flat=True)) == {"Migo Run Club"}


def test_a_remembered_club_is_applied_to_the_next_upload(season, staff):
    Runner.objects.create(
        first_name="B",
        last_name="B",
        category="FS",
        club="Migo Run Club",
        season=Season.objects.get(season_start_year=2025),
    )
    first = draft(season, staff, [("James", "Young", "MIGO", "MS", 1, 1200.0)])
    services.decide(RowChange.objects.get(), 0, staff, remember=True)
    services.discard_draft(first, staff)

    second = draft(season, staff, [("Egbert", "Pos", "migo", "MS", 2, 1300.0)])
    change = RowChange.objects.get(row__upload=second)
    assert second.rows.get().club == "Migo Run Club"
    assert (change.source, change.status) == ("remembered", "applied")


def test_rows_can_be_edited_by_hand_and_problems_block(staff_client, season, staff):
    rows = FIELD + [("Ann", "Archer", "", "F35", 9, "23:45")]
    upload = draft(season, staff, rows)
    assert len(services.blocking_problems(upload)) == 2
    assert services.publish_blockers(upload)

    row = upload.rows.get(number=7)
    staff_client.post(
        reverse("results_import:row_edit", args=[upload.pk, row.pk]),
        {
            "first_name": "Anne",
            "last_name": "Archer",
            "bib": "9",
            "category": "f40",
            "club": "",
            "time_text": "00:23:45",
        },
    )
    row.refresh_from_db()
    assert (row.first_name, row.category, row.time_text) == ("Anne", "F40", "00:23:45")
    assert services.blocking_problems(upload) == {}
    manual = RowChange.objects.filter(source="manual")
    assert sorted(manual.values_list("field", flat=True)) == [
        "category",
        "name",
        "time",
    ]


LATE = {
    "first_name": " Finn ",
    "last_name": "Fraser",
    "bib": "6",
    "category": "m40",
    "club": "",
    "time_text": "00:21:30",
}


def test_a_finisher_missing_from_the_file_can_be_added(staff_client, season, staff):
    upload = draft(season, staff)
    response = staff_client.post(
        reverse("results_import:row_add", args=[upload.pk]), LATE
    )
    assert response.url.endswith("#row-7")
    row = upload.rows.get(number=7)
    assert row.is_added
    assert (row.first_name, row.category, row.time_text) == ("Finn", "M40", "00:21:30")
    change = row.changes.get()
    assert (change.rule, change.source, change.after) == (
        "added",
        "manual",
        ["Finn", "Fraser"],
    )
    page = staff_client.get(reverse("results_import:detail", args=[upload.pk]))
    assert "added by hand" in page.content.decode()

    services.publish_upload(upload, staff)
    result = Result.objects.get(runner__last_name="Fraser")
    # 21:30 falls between Cat Cooper's 21:01 and Dan Dixon's 21:40.
    assert result.general_position == 4
    assert result.category_position == 1
    assert Result.objects.get(runner__last_name="Dixon").category_position == 2
    assert Result.objects.get(runner__last_name="Ellis").general_position == 6
    row.refresh_from_db()
    assert row.result == result


def test_an_added_row_is_checked_like_any_other(staff_client, season, staff):
    upload = draft(season, staff)
    url = reverse("results_import:row_add", args=[upload.pk])
    for wrong in ({"category": "M35"}, {"time_text": "21.30"}, {"last_name": " "}):
        staff_client.post(url, {**LATE, **wrong})
    assert upload.rows.count() == len(FIELD)

    # Same name or same time as a row in the file: added, but it blocks.
    staff_client.post(url, {**LATE, "first_name": "Ann", "last_name": "Archer"})
    assert 7 in services.blocking_problems(upload)


def test_an_added_row_can_be_removed_and_survives_reopening(season, staff):
    values = {
        "name": ["Finn", "Fraser"],
        "bib": "6",
        "category": "M40",
        "club": "Club B",
        "time": "00:21:30",
    }
    upload = draft(season, staff)
    row = services.add_row(upload, values, staff)
    services.edit_row(row, "time", "00:21:31", staff)
    services.revert_change(row.changes.get(rule="added"), staff)
    assert upload.rows.count() == len(FIELD)
    assert not RowChange.objects.filter(source="manual").exists()

    services.add_row(upload, values, staff)
    services.publish_upload(upload, staff)
    with pytest.raises(ImportProblem):
        services.revert_change(RowChange.objects.get(rule="added"), staff)
    with pytest.raises(ImportProblem):
        services.add_row(upload, values, staff)
    services.revert_upload(upload, staff)
    assert not Runner.objects.filter(last_name="Fraser").exists()

    again = services.reopen_as_draft(upload, staff)
    added = again.rows.get(number=7)
    assert added.is_added and added.club == "Club B"
    services.publish_upload(again, staff)
    assert Result.objects.get(runner__last_name="Fraser").general_position == 4


def test_someone_who_did_not_run_can_be_left_out(staff_client, season, staff):
    upload = draft(season, staff)
    cat = upload.rows.get(last_name="Cooper")
    response = staff_client.post(
        reverse("results_import:row_leave_out", args=[upload.pk, cat.pk])
    )
    assert response.url.endswith(f"#row-{cat.number}")
    cat.refresh_from_db()
    assert cat.left_out
    change = cat.changes.get(rule="left_out")
    assert (change.source, change.status, change.before, change.after) == (
        "manual",
        "applied",
        ["Cat", "Cooper"],
        None,
    )
    page = staff_client.get(
        reverse("results_import:detail", args=[upload.pk])
    ).content.decode()
    assert "is-left-out" in page and "Put back" in page
    assert "1 row left out by hand" in page

    converted = openpyxl.load_workbook(
        io.BytesIO(services.converted_workbook(upload))
    ).active
    assert "Cooper" not in [row[1] for row in converted.iter_rows(values_only=True)]

    services.publish_upload(upload, staff)
    assert not Runner.objects.filter(last_name="Cooper").exists()
    assert Result.objects.count() == len(FIELD) - 1
    # Everyone behind her moves up a place.
    assert Result.objects.get(runner__last_name="Dixon").general_position == 3
    assert Result.objects.get(runner__last_name="Ellis").general_position == 4
    assert Result.objects.get(runner__last_name="Ellis").gender_position == 2
    cat.refresh_from_db()
    assert cat.runner is None and cat.result is None


def test_a_left_out_row_can_be_put_back_and_survives_reopening(
    staff_client, season, staff
):
    upload = draft(season, staff)
    cat = upload.rows.get(last_name="Cooper")
    services.leave_out(cat, staff)
    with pytest.raises(ImportProblem):
        services.leave_out(cat, staff)
    with pytest.raises(ImportProblem):
        services.edit_row(cat, "club", "Club C", staff)

    staff_client.post(reverse("results_import:row_put_back", args=[upload.pk, cat.pk]))
    cat.refresh_from_db()
    assert not cat.left_out
    change = cat.changes.get(rule="left_out")
    assert change.status == "reverted"
    with pytest.raises(ImportProblem):
        services.put_back(cat, staff)

    # Leaving the row out again reuses the one record of it.
    staff_client.post(
        reverse("results_import:change_reapply", args=[upload.pk, change.pk])
    )
    cat.refresh_from_db()
    assert cat.left_out and cat.changes.filter(rule="left_out").count() == 1

    services.publish_upload(upload, staff)
    with pytest.raises(ImportProblem):
        services.put_back(cat, staff)
    services.revert_upload(upload, staff)

    again = services.reopen_as_draft(upload, staff)
    copy = again.rows.get(last_name="Cooper")
    assert copy.left_out
    services.put_back(copy, staff)
    services.publish_upload(again, staff)
    assert Result.objects.get(runner__last_name="Cooper").general_position == 3


def test_a_left_out_row_no_longer_blocks_or_asks(season, staff):
    # Two rows with one name block publishing; so does an open question.
    rows = FIELD + [
        ("Ann", "Archer", "Club A", "FS", 6, 1500.0),
        ("James", "Young", "MIGO", "MS", 9, 1600.0),
    ]
    Runner.objects.create(
        first_name="B",
        last_name="B",
        category="FS",
        club="Migo Run Club",
        season=Season.objects.get(season_start_year=2025),
    )
    upload = draft(season, staff, rows)
    assert len(services.publish_blockers(upload)) == 2
    services.leave_out(upload.rows.get(number=7), staff)
    services.leave_out(upload.rows.get(last_name="Young"), staff)
    assert services.publish_blockers(upload) == []
    services.publish_upload(upload, staff)
    assert Runner.objects.filter(season=season).count() == len(FIELD)


def test_an_added_row_is_removed_not_left_out(season, staff):
    upload = draft(season, staff)
    values = {
        "name": ["Finn", "Fraser"],
        "bib": "6",
        "category": "M40",
        "club": "",
        "time": "00:21:30",
    }
    with pytest.raises(ImportProblem):
        services.leave_out(services.add_row(upload, values, staff), staff)


def test_a_number_too_long_for_the_site_blocks_publishing(season, staff):
    upload = draft(
        season, staff, [("Ann", "Archer", "", "FS", "Bellahouston Harriers", 1200.0)]
    )
    (problems,) = services.blocking_problems(upload).values()
    assert "longer than 10 characters" in problems[0]
    with pytest.raises(ImportProblem):
        services.publish_upload(upload, staff)


# ---------------------------------------------------------------- publish


def test_publishing_matches_the_old_form_given_the_converted_file(
    staff_client, season, staff
):
    rows = [
        ("mark", "Bailkoski", "Club A", "MS", 1, 1260.4),
        ("Ann", "Archer", "Club A", "FS", 2, 1260.6),
        ("Cat", "Cooper", None, "F40", 3, 1260.5),
        ("Dan", "Dixon", "Club B", "M40", 4, 1300.2),
        ("Eve", "Ellis", "Club B", "FS", 5, "DNF"),
    ]
    upload = draft(season, staff, rows)
    converted = services.converted_workbook(upload)
    services.publish_upload(upload, staff)

    staff_client.post(
        reverse("races:new"),
        {
            "name": "King's Park",
            "season_start_year": 2025,
            "race_file": SimpleUploadedFile("kings.xlsx", converted, content_type=XLSX),
        },
    )

    def picture(year):
        return [
            (
                r.runner.first_name,
                r.runner.last_name,
                r.runner.club,
                r.runner.category,
                str(r.runner.participant_number),
                r.time,
                r.general_position,
                r.gender_position,
                r.category_position,
            )
            for r in Result.objects.filter(race__season_start_year=year)
            .select_related("runner")
            .order_by("general_position")
        ]

    assert len(picture(2026)) == 5
    assert picture(2026) == picture(2025)
    assert [p[1] for p in picture(2026)] == [
        "Bailkoski",
        "Cooper",
        "Archer",
        "Dixon",
        "Ellis",
    ]
    assert Runner.objects.get(last_name="Cooper", season=season).club == "Unaffiliated"


def test_published_rows_are_linked_to_their_results(season, staff):
    upload = publish(season, staff)
    assert upload.race.slug == "kings-park-2026"
    assert len(upload.created_runner_ids) == 5
    for row in upload.rows.all():
        assert row.runner.last_name == row.last_name
        assert row.result.race_id == upload.race_id


def test_a_runner_already_known_this_season_keeps_their_record(season, staff):
    publish(season, staff)
    rows = [
        ("ann", "ARCHER", "Club Z", "FS", 77, 1190.0),
        ("New", "Runner", "", "MS", 8, 1250.0),
    ]
    upload = draft(season, staff, rows, race_name="Linn Park")
    differences = services.record_differences(upload)
    assert [(d["field"], d["on_record"], d["in_file"]) for d in differences] == [
        ("club", "Club A", "Club Z"),
        ("bib", "1", "77"),
    ]
    services.publish_upload(upload, staff)
    ann = Runner.objects.get(first_name="Ann", last_name="Archer", season=season)
    assert (ann.club, ann.participant_number) == ("Club A", "1")
    assert ann.result_set.count() == 2
    assert upload.rows.get(number=2).runner == ann


def test_the_files_club_can_replace_the_record_and_be_put_back(season, staff):
    publish(season, staff)
    upload = draft(
        season, staff, [("Ann", "Archer", "Club Z", "FS", 1, 1190.0)], "Linn Park"
    )
    services.use_file_value(upload.rows.get(), "club", staff)
    upload = services.publish_upload(upload, staff)
    ann = Runner.objects.get(first_name="Ann", season=season)
    assert ann.club == "Club Z"

    services.revert_upload(upload, staff)
    ann.refresh_from_db()
    assert ann.club == "Club A"


# ----------------------------------------------------------------- revert


def test_reverting_puts_the_site_back_exactly(season, staff):
    publish(season, staff, FIELD, "King's Park")
    publish(season, staff, FIELD[:4], "Linn Park")
    before = site_state()

    # A third race makes the season re-rank every race for the standings.
    third = FIELD + [("Fay", "Fisher", "Club C", "FS", 6, 1100.0)]
    upload = publish(season, staff, third, "Rouken Glen")
    during = site_state()
    assert len(during["Race"]) == 3
    assert len(during["RaceVersion"]) > len(before["RaceVersion"]) + 1
    assert len(during["Runner"]) == len(before["Runner"]) + 1

    services.revert_upload(upload, staff)
    assert site_state() == before
    upload.refresh_from_db()
    assert upload.status == ResultsUpload.REVERTED
    assert upload.rows.count() == 6
    assert upload.rows.filter(runner__isnull=False).count() == 0


def test_only_the_seasons_latest_race_can_be_reverted(staff_client, season, staff):
    first = publish(season, staff, FIELD, "King's Park")
    publish(season, staff, FIELD, "Linn Park")
    with pytest.raises(ImportProblem) as problem:
        services.revert_upload(first, staff)
    assert "Linn Park" in str(problem.value)

    response = staff_client.post(reverse("results_import:revert", args=[first.pk]))
    assert response.status_code == 302
    first.refresh_from_db()
    assert first.status == ResultsUpload.PUBLISHED
    assert Race.objects.count() == 2


def test_a_reverted_upload_reopens_with_its_decisions(season, staff):
    Runner.objects.create(
        first_name="B",
        last_name="B",
        category="FS",
        club="Migo Run Club",
        season=Season.objects.get(season_start_year=2025),
    )
    upload = draft(season, staff, FIELD + [("James", "Young", "MIGO", "MS", 9, 1500.0)])
    services.decide(RowChange.objects.get(status="pending"), 0, staff)
    services.edit_row(upload.rows.get(number=2), "club", "Club Edited", staff)
    upload = services.publish_upload(upload, staff)
    services.revert_upload(upload, staff)

    again = services.reopen_as_draft(upload, staff)
    assert again.status == ResultsUpload.DRAFT
    assert again.reopened_from == upload
    assert again.rows.get(number=7).club == "Migo Run Club"
    assert again.rows.get(number=2).club == "Club Edited"
    assert services.publish_blockers(again) == []
    assert services.publish_upload(again, staff).race.result_set.count() == 6


def test_publishing_again_can_replace_a_race(staff_client, season, staff):
    first = publish(season, staff)
    second = draft(season, staff, FIELD[:3])

    staff_client.post(reverse("results_import:publish", args=[second.pk]))
    second.refresh_from_db()
    assert second.status == ResultsUpload.DRAFT

    staff_client.post(
        reverse("results_import:publish", args=[second.pk]), {"replace": "1"}
    )
    first.refresh_from_db()
    second.refresh_from_db()
    assert (first.status, second.status) == ("reverted", "published")
    assert Race.objects.count() == 1
    assert Result.objects.count() == 3
    assert Runner.objects.filter(season=season).count() == 3


# --------------------------------------------------------- other seasons


def old_runner(first, last, year=2025, club=""):
    return Runner.objects.create(
        first_name=first,
        last_name=last,
        category="MS",
        club=club,
        season=Season.objects.get(season_start_year=year),
    )


def test_a_spelling_can_be_corrected_in_earlier_seasons_and_put_back(season, staff):
    old = old_runner("Liam", "McGregor")
    upload = draft(season, staff, [("Liam", "Mcgregor", "", "MS", 1, 1200.0)])
    change = RowChange.objects.get()
    everywhere = [o["scope"] for o in change.options].index("all")
    services.decide(change, everywhere, staff)
    upload = services.publish_upload(upload, staff)

    old.refresh_from_db()
    change.refresh_from_db()
    assert old.last_name == "Mcgregor"
    assert change.affected == [
        {
            "runner_id": old.id,
            "field": "name",
            "old": ["Liam", "McGregor"],
            "new": ["Liam", "Mcgregor"],
            "season": 2025,
        }
    ]

    services.revert_change(change, staff)
    old.refresh_from_db()
    assert old.last_name == "McGregor"
    assert Runner.objects.get(season=season).last_name == "Mcgregor"


def test_reverting_the_upload_also_puts_earlier_seasons_back(season, staff):
    old = old_runner("Liam", "McGregor")
    upload = draft(season, staff, [("Liam", "Mcgregor", "", "MS", 1, 1200.0)])
    services.decide(RowChange.objects.get(), 2, staff)
    upload = services.publish_upload(upload, staff)
    services.revert_upload(upload, staff)
    old.refresh_from_db()
    assert old.last_name == "McGregor"
    assert Runner.objects.filter(season=season).count() == 0


def test_this_season_only_leaves_earlier_seasons_alone(season, staff):
    old = old_runner("Liam", "McGregor")
    upload = draft(season, staff, [("Liam", "Mcgregor", "", "MS", 1, 1200.0)])
    services.decide(RowChange.objects.get(), 1, staff)
    services.publish_upload(upload, staff)
    old.refresh_from_db()
    assert old.last_name == "McGregor"


def test_a_rename_that_would_merge_two_runners_is_skipped_and_noted(season, staff):
    one = old_runner("Liam", "McGregor")
    two = old_runner("Liam", "Mc Gregor")
    upload = draft(season, staff, [("Liam", "Mcgregor", "", "MS", 1, 1200.0)])
    change = RowChange.objects.get()
    everywhere = [o["scope"] for o in change.options].index("all")
    services.decide(change, everywhere, staff)
    services.publish_upload(upload, staff)

    change.refresh_from_db()
    names = sorted(
        Runner.objects.filter(pk__in=[one.pk, two.pk]).values_list(
            "last_name", flat=True
        )
    )
    assert names == ["Mc Gregor", "Mcgregor"] or names == ["McGregor", "Mcgregor"]
    assert len(change.affected) == 1
    assert "not renamed" in change.note


def test_a_near_miss_can_rename_this_seasons_runner(season, staff):
    publish(season, staff, [("Gary", "McIndoe", "", "MS", 1, 1200.0)])
    upload = draft(
        season, staff, [("Gary", "MacIndoe", "", "MS", 1, 1210.0)], "Linn Park"
    )
    change = RowChange.objects.get(status="pending")
    assert change.rule == "near_match"
    services.decide(change, 1, staff)  # same person, use the file's spelling
    services.publish_upload(upload, staff)

    gary = Runner.objects.get(season=season)
    assert gary.last_name == "MacIndoe"
    assert gary.result_set.count() == 2


def test_different_people_are_remembered(season, staff):
    publish(season, staff, [("Gary", "McIndoe", "", "MS", 1, 1200.0)])
    upload = draft(
        season, staff, [("Gary", "MacIndoe", "", "MS", 2, 1210.0)], "Linn Park"
    )
    change = RowChange.objects.get(status="pending")
    services.decide(change, len(change.options) - 1, staff)
    services.publish_upload(upload, staff)
    assert Runner.objects.filter(season=season).count() == 2

    third = draft(
        season, staff, [("Gary", "MacIndoe", "", "MS", 2, 1220.0)], "Rouken Glen"
    )
    assert not RowChange.objects.filter(row__upload=third).exists()


# ------------------------------------------------- changes after publishing


def test_a_name_fix_can_be_reverted_on_the_live_site(season, staff):
    upload = publish(season, staff, [("mark", "Bailkoski", "", "MS", 1, 1200.0)])
    change = RowChange.objects.get()
    services.revert_change(change, staff)
    assert Runner.objects.get().first_name == "mark"
    change.refresh_from_db()
    services.reapply_change(change, staff)
    assert Runner.objects.get().first_name == "Mark"
    assert upload.rows.get().first_name == "Mark"


def test_a_live_revert_that_would_merge_two_runners_is_refused(
    staff_client, season, staff
):
    upload = publish(season, staff, [("mark", "Bailkoski", "", "MS", 1, 1200.0)])
    Runner.objects.create(
        first_name="mark", last_name="Bailkoski", category="MS", season=season
    )
    change = RowChange.objects.get()
    with pytest.raises(ImportProblem):
        services.revert_change(change, staff)

    response = staff_client.post(
        reverse("results_import:change_revert", args=[upload.pk, change.pk])
    )
    assert response.status_code == 302
    change.refresh_from_db()
    assert change.status == "applied"
    assert Runner.objects.filter(first_name="Mark").count() == 1


def test_times_and_categories_are_not_changed_singly_on_the_live_site(season, staff):
    upload = draft(season, staff, [("Ann", "Archer", "", "fs", 1, 1200.0)])
    services.publish_upload(upload, staff)
    change = RowChange.objects.get(field="category")
    with pytest.raises(ImportProblem) as problem:
        services.revert_change(change, staff)
    assert "reopen" in str(problem.value)
    assert Runner.objects.get().category == "FS"


def test_a_closed_upload_cannot_be_edited(season, staff):
    upload = draft(season, staff, [("mark", "Bailkoski", "", "MS", 1, 1200.0)])
    services.discard_draft(upload, staff)
    with pytest.raises(ImportProblem):
        services.revert_change(RowChange.objects.get(), staff)
    with pytest.raises(ImportProblem):
        services.edit_row(upload.rows.get(), "club", "X", staff)
    with pytest.raises(ImportProblem):
        services.publish_upload(upload, staff)
