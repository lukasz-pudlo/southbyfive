"""The conversion rules of the results import, without a database."""

import io

import openpyxl
import pytest

from results_import import normalise as n

RAW_HEADERS = [
    "Forename",
    "Surname",
    "gender",
    "Club",
    "Age Cat",
    "Number",
    "Time",
    "Pos",
]
SITE_HEADERS = [
    "First Name",
    "Last Name",
    "Participant Number",
    "Category",
    "Club",
    "Time",
]

# Stored cell value -> what Excel itself showed, read from Excel for the 2026
# King's Park and Linn Park exports. Every one ends in exactly half a second,
# where ordinary rounding rules get some of them wrong.
EXCEL_HALF_SECONDS = [
    ("1.3061342592592593E-2", "00:18:48"),
    ("1.4207175925925925E-2", "00:20:27"),
    ("1.5873842592592592E-2", "00:22:51"),
    ("1.6140046296296295E-2", "00:23:14"),
    ("1.6718750000000001E-2", "00:24:05"),
    ("1.7413194444444443E-2", "00:25:04"),
    ("2.0943287037037038E-2", "00:30:09"),
    ("2.1313657407407406E-2", "00:30:41"),
    ("2.1475694444444443E-2", "00:30:56"),
    ("2.1741898148148149E-2", "00:31:18"),
    ("2.222800925925926E-2", "00:32:00"),
    ("2.3813657407407408E-2", "00:34:17"),
    ("2.4565972222222222E-2", "00:35:22"),
    ("2.4577546296296295E-2", "00:35:23"),
    ("2.4635416666666667E-2", "00:35:29"),
    ("1.8223379629629631E-2", "00:26:15"),
    ("1.9461805555555555E-2", "00:28:01"),
    ("2.1059027777777777E-2", "00:30:19"),
    ("2.1163194444444443E-2", "00:30:28"),
    ("2.1336805555555557E-2", "00:30:44"),
    ("2.2285879629629631E-2", "00:32:06"),
    ("2.3755787037037037E-2", "00:34:13"),
    ("2.7019675925925926E-2", "00:38:55"),
    ("2.9797453703703704E-2", "00:42:54"),
    ("3.0873842592592592E-2", "00:44:27"),
    ("3.0885416666666665E-2", "00:44:29"),
    ("3.0931712962962963E-2", "00:44:32"),
    ("3.1464120370370371E-2", "00:45:19"),
    ("3.9415509259259261E-2", "00:56:46"),
]


def workbook_bytes(headers, rows):
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append(headers)
    for row in rows:
        sheet.append(row)
    out = io.BytesIO()
    workbook.save(out)
    return out.getvalue()


def raw_file(rows):
    """Rows of (forename, surname, club, category, number, seconds or text)."""
    return workbook_bytes(
        RAW_HEADERS,
        [
            [
                first,
                last,
                "Female",
                club,
                cat,
                number,
                time / 86400 if isinstance(time, (int, float)) else time,
                index,
            ]
            for index, (first, last, club, cat, number, time) in enumerate(rows, 1)
        ],
    )


def proposals(rows, known=(), season=2026, rules=None):
    sheet = n.read_sheet(raw_file(rows))
    return n.propose(sheet, n.Reference(list(known), season, rules))


def known(*runners):
    return [
        n.KnownRunner(index, first, last, season, club)
        for index, (first, last, season, club) in enumerate(runners, 1)
    ]


# ------------------------------------------------------------------ times


@pytest.mark.parametrize("stored, shown", EXCEL_HALF_SECONDS)
def test_half_second_times_match_excel(stored, shown):
    assert n.parse_time(n.Cell(number=stored)).text == shown


def test_ordinary_times_round_to_the_nearest_second():
    assert n.parse_time(n.Cell(number=repr(1363.3 / 86400))).text == "00:22:43"
    assert n.parse_time(n.Cell(number=repr(1525.9 / 86400))).text == "00:25:26"
    assert n.parse_time(n.Cell(number=repr(3600.0 / 86400))).text == "01:00:00"


def test_text_times_are_kept_as_written():
    assert n.parse_time(n.Cell(text="00:21:53")).text == "00:21:53"
    assert n.parse_time(n.Cell(text="00:21:53 2")).text == "00:21:53 2"
    assert n.parse_time(n.Cell(text=" dnf ")).text == "DNF"


@pytest.mark.parametrize("bad", ["", "23:45", "fast", "00:61:00", "00:21:53.4"])
def test_unreadable_times_are_reported_not_guessed(bad):
    parsed = n.parse_time(n.Cell(text=bad))
    assert parsed.text == ""
    assert parsed.error


def test_a_number_that_is_not_a_time_of_day_is_an_error():
    assert n.parse_time(n.Cell(number="45000.5")).error


def test_ties_are_numbered_in_finishing_order():
    result = proposals(
        [
            ("Ann", "Slow", "", "FS", 1, 1526.4),
            ("Bea", "Fast", "", "FS", 2, 1525.9),
            ("Cat", "Alone", "", "FS", 3, 1600.0),
        ]
    )
    assert [p.time_text for p in result] == ["00:25:26 2", "00:25:26 1", "00:26:40"]


def test_identical_precise_times_keep_file_order():
    result = proposals(
        [
            ("Richard", "Johnstone", "", "MS", 1, 1872.4),
            ("Julie", "Laird", "", "FS", 2, 1872.4),
            ("Robbie", "Martin", "", "MS", 3, 1872.4),
        ]
    )
    assert [p.time_text for p in result] == [
        "00:31:12 1",
        "00:31:12 2",
        "00:31:12 3",
    ]


def test_dnf_rows_are_never_treated_as_tied():
    result = proposals(
        [("Ann", "One", "", "FS", 1, "DNF"), ("Bea", "Two", "", "FS", 2, "DNF")]
    )
    assert [p.time_text for p in result] == ["DNF", "DNF"]


# ---------------------------------------------------------------- reading


def test_both_file_formats_are_read():
    raw = n.read_sheet(raw_file([("Ann", "One", "Club A", "FS", 12, 1200.0)]))
    site = n.read_sheet(
        workbook_bytes(SITE_HEADERS, [["Ann", "One", 12, "FS", "Club A", "00:20:00"]])
    )
    for sheet in (raw, site):
        row = sheet.rows[0]
        assert (row.first_name, row.last_name, row.bib, row.category, row.club) == (
            "Ann",
            "One",
            "12",
            "FS",
            "Club A",
        )
        assert n.parse_time(row.time).text == "00:20:00"
    assert raw.ignored_headers == ["gender", "Pos"]
    assert raw.rows[0].number == 2


def test_a_missing_column_is_named():
    data = workbook_bytes(
        ["First Name", "Last Name", "Club", "Time"], [["A", "B", "", "DNF"]]
    )
    with pytest.raises(n.SheetError) as error:
        n.read_sheet(data)
    assert "Participant Number" in str(error.value)
    assert "Category" in str(error.value)


def test_two_columns_for_the_same_thing_are_refused():
    data = workbook_bytes(
        SITE_HEADERS + ["Age Cat"], [["A", "B", 1, "FS", "", "DNF", "FS"]]
    )
    with pytest.raises(n.SheetError):
        n.read_sheet(data)


def test_something_that_is_not_a_workbook_is_refused():
    with pytest.raises(n.SheetError):
        n.read_sheet(b"First Name,Last Name\nA,B\n")


def test_blank_rows_are_skipped_and_blank_cells_read_as_empty():
    data = raw_file([("Ann", "One", None, "FS", 1, 1200.0)])
    workbook = openpyxl.load_workbook(io.BytesIO(data))
    workbook.active.append([None] * 8)
    workbook.active.append(["Bea", "Two", "Female", None, "FS", None, "DNF", None])
    out = io.BytesIO()
    workbook.save(out)
    sheet = n.read_sheet(out.getvalue())
    assert [(r.number, r.first_name, r.club, r.bib) for r in sheet.rows] == [
        (2, "Ann", "", "1"),
        (4, "Bea", "", ""),
    ]


# ------------------------------------------------------------------ names


@pytest.mark.parametrize(
    "typed, cleaned",
    [
        ("mark", "Mark"),
        ("DAVID", "David"),
        ("RIACH", "Riach"),
        ("Fraser-hopewell", "Fraser-Hopewell"),
        ("Mary sharon", "Mary Sharon"),
        ("mackie", "Mackie"),
        ("Ã\x81ine", "Áine"),
        ("  Gordon ", "Gordon"),
        ("Cameron  Winton", "Cameron Winton"),
        ("o'leary", "O'Leary"),
        ("ANNE-MARIE", "Anne-Marie"),
    ],
)
def test_obvious_slips_in_names_are_fixed(typed, cleaned):
    assert n.clean_name_part(typed)[0] == cleaned


@pytest.mark.parametrize(
    "name",
    [
        "McDade",
        "MacIndoe",
        "O'Leary",
        "Mchugh",
        "Mcleod",
        "Áine",
        "Zoë",
        "Achard Brown",
        "Layla-Roxanne",
        "van der Berg",
        "J",
    ],
)
def test_names_with_their_own_capitals_are_left_alone(name):
    assert n.clean_name_part(name) == (name, [])


def test_double_names_are_never_hyphenated():
    result = proposals([("Margaux", "achard brown", "", "FS", 1, 1200.0)])
    assert (result[0].first_name, result[0].last_name) == ("Margaux", "Achard Brown")


def test_every_name_change_is_recorded_with_its_original():
    result = proposals([("Ã\x81ine", "byrne", "", "FS", 1, 1200.0)])
    (change,) = result[0].changes
    assert change.before == ["Ã\x81ine", "byrne"]
    assert change.after == ["Áine", "Byrne"]
    assert change.status == n.APPLIED
    assert "Broken characters repaired" in change.reason


def test_a_runner_from_this_season_keeps_this_seasons_spelling():
    result = proposals(
        [
            ("Gayle", "mackie", "", "FS", 1, 1200.0),
            ("beth", "MCHUGH", "", "FS", 2, 1300.0),
        ],
        known(("Gayle", "Mackie", 2026, ""), ("Beth", "Mchugh", 2026, "")),
    )
    assert (result[0].first_name, result[0].last_name) == ("Gayle", "Mackie")
    assert (result[1].first_name, result[1].last_name) == ("Beth", "Mchugh")
    assert all(c.status == n.APPLIED for p in result for c in p.changes)


def test_no_casing_in_the_file_takes_the_earlier_seasons_spelling():
    result = proposals(
        [
            ("claire", "wharton", "", "FS", 1, 1200.0),
            ("LIAM", "MCGREGOR", "", "MS", 2, 1300.0),
        ],
        known(("Claire", "Wharton", 2024, ""), ("Liam", "McGregor", 2025, "")),
    )
    assert (result[0].first_name, result[0].last_name) == ("Claire", "Wharton")
    assert (result[1].first_name, result[1].last_name) == ("Liam", "McGregor")
    assert all(c.status == n.APPLIED for p in result for c in p.changes)


def test_a_different_spelling_from_earlier_seasons_is_a_decision():
    result = proposals(
        [("Liam", "Mcgregor", "", "MS", 1, 1200.0)],
        known(("Liam", "McGregor", 2025, "")),
    )
    (change,) = result[0].changes
    assert change.status == n.PENDING
    assert [(o["value"], o["scope"]) for o in change.options] == [
        (["Liam", "McGregor"], "row"),
        (["Liam", "Mcgregor"], "row"),
        (["Liam", "Mcgregor"], "all"),
    ]


def test_a_near_miss_asks_whether_it_is_the_same_person():
    result = proposals(
        [
            ("Margot", "Brewer", "", "FS", 1, 1200.0),
            ("Gary", "MacIndoe", "", "MS", 2, 1300.0),
        ],
        known(("Margo", "Brewer", 2025, ""), ("Gary", "McIndoe", 2026, "")),
    )
    margot, gary = (p.changes[0] for p in result)
    assert margot.rule == gary.rule == "near_match"
    assert margot.status == gary.status == n.PENDING
    assert [o["scope"] for o in margot.options] == ["row", "row", "all", "row"]
    assert [o["scope"] for o in gary.options] == ["row", "season", "row"]


def test_a_known_runner_who_is_also_in_the_file_is_not_a_near_miss():
    result = proposals(
        [
            ("Alan", "Brown", "", "MS", 1, 1200.0),
            ("Allan", "Brown", "", "MS", 2, 1300.0),
        ],
        known(("Alan", "Brown", 2026, "")),
    )
    assert result[1].changes == []


def test_people_already_told_apart_are_not_asked_about_again():
    rules = n.Rules(different={frozenset(("margot|brewer", "margo|brewer"))})
    result = proposals(
        [("Margot", "Brewer", "", "FS", 1, 1200.0)],
        known(("Margo", "Brewer", 2025, "")),
        rules=rules,
    )
    assert result[0].changes == []


def test_a_remembered_name_is_applied_and_marked_as_remembered():
    rules = n.Rules(names={"micheal|norton": ("Michael", "Norton")})
    result = proposals([("Micheal", "Norton", "", "MS", 1, 1200.0)], rules=rules)
    (change,) = result[0].changes
    assert change.source == n.REMEMBERED
    assert (result[0].first_name, result[0].last_name) == ("Michael", "Norton")


def test_a_surname_typed_without_capitals_asks_about_mc():
    result = proposals([("scott", "mcleod", "", "MS", 1, 1200.0)])
    cleaned, question = result[0].changes
    assert cleaned.after == ["Scott", "Mcleod"]
    assert question.status == n.PENDING
    assert [o["value"] for o in question.options] == [
        ["Scott", "Mcleod"],
        ["Scott", "McLeod"],
    ]


# ------------------------------------------------------------------ clubs


def test_clubs_take_the_spelling_already_on_the_site():
    site = known(
        ("A", "A", 2025, "Jog Scotland"),
        ("B", "B", 2025, "Migo Run Club"),
        ("C", "C", 2025, "Bellahouston Road Runners"),
        ("D", "D", 2024, "Victoria Park City of Glasgow"),
        ("E", "E", 2025, "Victoria Park City Of Glasgow"),
    )
    result = proposals(
        [
            ("Ann", "One", "Jog scotland", "FS", 1, 1200.0),
            ("Bea", "Two", "Migo Run  club", "FS", 2, 1300.0),
            ("Cat", "Three", "Bellahouston Roadrunners", "FS", 3, 1400.0),
            ("Dee", "Four", "Victoria Park City of Glasgow", "FS", 4, 1500.0),
            ("Eve", "Five", "JogScotland", "FS", 5, 1600.0),
        ],
        site,
    )
    assert [p.club for p in result] == [
        "Jog Scotland",
        "Migo Run Club",
        "Bellahouston Road Runners",
        "Victoria Park City Of Glasgow",
        "Jog Scotland",
    ]
    assert all(c.status == n.APPLIED for p in result for c in p.changes)


def test_similar_but_separate_clubs_stay_separate():
    site = known(
        ("A", "A", 2025, "Jog Scotland"),
        ("B", "B", 2025, "Carluke Jog Scotland"),
        ("C", "C", 2025, "Jog Scotland East Kilbride"),
        ("D", "D", 2025, "Cumbernauld AAC"),
        ("E", "E", 2025, "Cumbernauld Amateur Athletics Club"),
    )
    clubs = [r.club for r in site]
    result = proposals(
        [
            ("N", f"Runner{i}", club, "FS", i, 1200.0 + i * 10)
            for i, club in enumerate(clubs)
        ],
        site,
    )
    assert [p.club for p in result] == clubs
    assert all(p.changes == [] for p in result)


def test_an_unknown_club_like_a_known_one_is_a_decision():
    result = proposals(
        [("James", "Young", "MIGO", "MS", 1, 1200.0)],
        known(("B", "B", 2025, "Migo Run Club")),
    )
    (change,) = result[0].changes
    assert change.status == n.PENDING
    assert [o["value"] for o in change.options] == ["Migo Run Club", "MIGO"]


def test_club_names_keep_their_small_words():
    result = proposals([("Ann", "One", "Run with Fran", "FS", 1, 1200.0)])
    assert result[0].club == "Run with Fran"
    assert result[0].changes == []


def test_a_remembered_club_is_applied():
    rules = n.Rules(clubs={"migo": "Migo Run Club"})
    result = proposals([("James", "Young", "MIGO", "MS", 1, 1200.0)], rules=rules)
    assert result[0].club == "Migo Run Club"
    assert result[0].changes[0].source == n.REMEMBERED


def test_a_blank_club_stays_blank():
    result = proposals([("Ann", "One", None, "FS", 1, 1200.0)])
    assert result[0].club == ""
    assert result[0].changes == []


# ----------------------------------------------------------------- checks


def check(rows):
    return n.check_rows(
        [
            dict(number=i, first_name=f, last_name=l, category=c, time_text=t)
            for i, (f, l, c, t) in enumerate(rows, 2)
        ],
        {"MS", "FS"},
    )


def test_a_clean_file_has_nothing_blocking():
    assert check([("Ann", "One", "FS", "00:20:00"), ("Bob", "Two", "MS", "DNF")]) == {}


def test_what_blocks_publishing():
    problems = check(
        [
            ("Ann", "One", "FS", "00:20:00"),
            ("ann", "ONE", "FS", "00:21:00"),
            ("Bob", "", "MS", "00:22:00"),
            ("Cal", "Three", "M35", "00:23:00"),
            ("Dan", "Four", "MS", "23:00"),
            ("Eve", "Five", "FS", "00:25:00"),
            ("Fay", "Six", "FS", "00:25:00"),
        ]
    )
    assert set(problems) == {2, 3, 4, 5, 6, 7, 8}
    assert "Same name as row 3" in problems[2][0]
    assert "missing" in problems[4][0]
    assert "M35" in problems[5][0]
    assert "00:23:45" in problems[6][0]
    assert "Same time as row 8" in problems[7][0]
