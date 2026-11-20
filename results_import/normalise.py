"""Turn the organiser's results spreadsheet into the site's format.

Pure Python on purpose: no Django and no pandas, so every rule can be unit
tested and nothing here can touch the database or the uploaded file.

The steps, in the order the import uses them:

1. ``read_sheet``   reads the first sheet's cells exactly as stored.
2. ``parse_time``   gives each time as Excel displays it (whole seconds).
3. ``assign_tie_suffixes`` adds " 1", " 2" to runners sharing a second.
4. ``propose``      cleans names and clubs and matches them to known ones,
                    returning every change it made or needs a decision on.
5. ``check_rows``   lists what still blocks publishing.
"""

from __future__ import annotations

import difflib
import posixpath
import re
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from io import BytesIO

# ---------------------------------------------------------------- reading

MAIN_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
DOC_REL_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
PKG_REL_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"

MAX_PART_BYTES = 20 * 1024 * 1024

# Column headers, compared with everything but letters removed.
HEADER_FIELDS = {
    "forename": "first_name",
    "firstname": "first_name",
    "surname": "last_name",
    "lastname": "last_name",
    "number": "bib",
    "participantnumber": "bib",
    "racenumber": "bib",
    "bib": "bib",
    "agecat": "category",
    "agecategory": "category",
    "category": "category",
    "club": "club",
    "time": "time",
}
REQUIRED_FIELDS = ("first_name", "last_name", "bib", "category", "club", "time")
FIELD_LABELS = {
    "first_name": "First Name (or Forename)",
    "last_name": "Last Name (or Surname)",
    "bib": "Participant Number (or Number)",
    "category": "Category (or Age Cat)",
    "club": "Club",
    "time": "Time",
}


class SheetError(Exception):
    """The file can't be read as a results sheet. The message is for the user."""


@dataclass
class Cell:
    """One cell as stored: text, or the number exactly as written in the file."""

    text: str | None = None
    number: str | None = None

    @property
    def is_blank(self):
        return self.number is None and not (self.text or "").strip()

    def as_text(self):
        if self.number is not None:
            try:
                value = float(self.number)
            except ValueError:
                return self.number
            if value.is_integer():
                return str(int(value))
            return repr(value)
        return self.text or ""


@dataclass
class RawRow:
    number: int  # the spreadsheet row, as Excel numbers it
    first_name: str
    last_name: str
    bib: str
    category: str
    club: str
    time: Cell


@dataclass
class Sheet:
    headers: list  # every header in the file, in order
    ignored_headers: list  # headers the import doesn't use
    rows: list  # RawRow


def _column_index(ref):
    index = 0
    for ch in ref:
        if ch.isalpha():
            index = index * 26 + (ord(ch.upper()) - 64)
        else:
            break
    return index - 1


def _read_part(archive, name):
    try:
        info = archive.getinfo(name)
    except KeyError:
        raise SheetError("This doesn't look like an Excel .xlsx file.")
    if info.file_size > MAX_PART_BYTES:
        raise SheetError("This file is too large to be a results sheet.")
    return ET.fromstring(archive.read(info))


def _text_of(node):
    # Phonetic guides (rPh) hold a reading of the text, not the text itself.
    parts = []
    for child in node.iter():
        if child.tag == MAIN_NS + "rPh":
            continue
        if child.tag == MAIN_NS + "t":
            parts.append(child.text or "")
    return "".join(parts)


def _shared_strings(archive):
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = _read_part(archive, "xl/sharedStrings.xml")
    strings = []
    for item in root.findall(MAIN_NS + "si"):
        text = []
        for child in item:
            if child.tag == MAIN_NS + "t":
                text.append(child.text or "")
            elif child.tag == MAIN_NS + "r":
                text.append(_text_of(child))
        strings.append("".join(text))
    return strings


def _first_sheet_path(archive):
    workbook = _read_part(archive, "xl/workbook.xml")
    sheets = workbook.find(MAIN_NS + "sheets")
    if sheets is None or not len(sheets):
        raise SheetError("This workbook has no sheets.")
    rel_id = sheets[0].get(DOC_REL_NS + "id")
    rels = _read_part(archive, "xl/_rels/workbook.xml.rels")
    for rel in rels.findall(PKG_REL_NS + "Relationship"):
        if rel.get("Id") == rel_id:
            target = rel.get("Target")
            if target.startswith("/"):
                return target.lstrip("/")
            return posixpath.normpath(posixpath.join("xl", target))
    raise SheetError("This workbook's first sheet can't be found.")


def read_cells(data):
    """Rows of the first sheet as ``(row_number, [Cell or None, ...])``."""
    try:
        archive = zipfile.ZipFile(BytesIO(data))
    except zipfile.BadZipFile:
        raise SheetError(
            "This isn't an Excel .xlsx file. If it is an older .xls or a .csv, "
            "open it in Excel and save a copy as .xlsx."
        )
    with archive:
        try:
            strings = _shared_strings(archive)
            sheet = _read_part(archive, _first_sheet_path(archive))
        except ET.ParseError:
            raise SheetError("This Excel file is damaged and can't be read.")
        data_node = sheet.find(MAIN_NS + "sheetData")
        rows = []
        next_row = 1
        for row in data_node if data_node is not None else []:
            row_number = int(row.get("r") or next_row)
            next_row = row_number + 1
            cells = []
            next_col = 0
            for c in row.findall(MAIN_NS + "c"):
                ref = c.get("r")
                col = _column_index(ref) if ref else next_col
                next_col = col + 1
                kind = c.get("t")
                value = c.find(MAIN_NS + "v")
                cell = None
                if kind == "inlineStr":
                    inline = c.find(MAIN_NS + "is")
                    cell = Cell(text=_text_of(inline) if inline is not None else "")
                elif value is not None and value.text is not None:
                    if kind == "s":
                        cell = Cell(text=strings[int(value.text)])
                    elif kind in ("str", "e"):
                        cell = Cell(text=value.text)
                    elif kind == "b":
                        cell = Cell(text="TRUE" if value.text == "1" else "FALSE")
                    else:
                        cell = Cell(number=value.text)
                while len(cells) <= col:
                    cells.append(None)
                cells[col] = cell
            rows.append((row_number, cells))
    return rows


def header_key(text):
    return re.sub(r"[^a-z]", "", (text or "").casefold())


def read_sheet(data):
    """Read an uploaded results file. Raises ``SheetError`` with a message
    for the user when the file can't be used."""
    rows = [
        (n, cells)
        for n, cells in read_cells(data)
        if any(c is not None and not c.is_blank for c in cells)
    ]
    if not rows:
        raise SheetError("The first sheet of this file is empty.")
    _, header_cells = rows[0]
    headers = [c.as_text().strip() if c is not None else "" for c in header_cells]

    columns = {}
    ignored = []
    for index, header in enumerate(headers):
        if not header:
            continue
        mapped = HEADER_FIELDS.get(header_key(header))
        if mapped is None:
            ignored.append(header)
        elif mapped in columns:
            other = headers[columns[mapped]]
            raise SheetError(
                f'Two columns look like {FIELD_LABELS[mapped]}: "{other}" and '
                f'"{header}". Remove or rename one of them in a copy of the file.'
            )
        else:
            columns[mapped] = index

    missing = [FIELD_LABELS[f] for f in REQUIRED_FIELDS if f not in columns]
    if missing:
        found = ", ".join(h for h in headers if h) or "none"
        raise SheetError(
            "The first row should hold the column headers, and these are missing: "
            + "; ".join(missing)
            + f". Headers found: {found}."
        )

    def cell_at(cells, name):
        index = columns[name]
        if index < len(cells) and cells[index] is not None:
            return cells[index]
        return Cell(text="")

    out = []
    for row_number, cells in rows[1:]:
        picked = {name: cell_at(cells, name) for name in REQUIRED_FIELDS}
        if all(cell.is_blank for cell in picked.values()):
            continue
        out.append(
            RawRow(
                number=row_number,
                first_name=picked["first_name"].as_text(),
                last_name=picked["last_name"].as_text(),
                bib=picked["bib"].as_text().strip(),
                category=picked["category"].as_text(),
                club=picked["club"].as_text(),
                time=picked["time"],
            )
        )
    if not out:
        raise SheetError("This file has column headers but no results under them.")
    return Sheet(headers=[h for h in headers if h], ignored_headers=ignored, rows=out)


# ------------------------------------------------------------------ times

TIME_RE = re.compile(r"^(\d{1,2}):(\d{2}):(\d{2})(?:\s+(\d+))?$")
DNF = "DNF"


def excel_display_hms(fraction):
    """Hours, minutes and seconds as Excel shows a time cell in h:mm:ss.

    Excel adds half a second and then cuts off hours, minutes and seconds one
    after the other, in ordinary double arithmetic. For a time that ends in
    exactly half a second the leftover rounding error decides which way it
    goes, so this has to repeat Excel's steps rather than round. Checked
    against Excel's own display for every row of the 2026 King's Park and
    Linn Park exports (284 times, 29 of them on a half second).
    """
    x = fraction + 1 / 172800
    hours = int(x * 24)
    x = x * 24 - hours
    minutes = int(x * 60)
    x = x * 60 - minutes
    seconds = int(x * 60)
    return hours, minutes, seconds


@dataclass
class ParsedTime:
    base: str = ""  # "00:22:43", "DNF", or "" when unreadable
    suffix: int | None = None  # tie-break number
    precise: float | None = None  # seconds, when the file had a real time cell
    in_file: str = ""  # the file's value, for showing beside the result
    error: str = ""

    @property
    def text(self):
        if self.base and self.suffix is not None:
            return f"{self.base} {self.suffix}"
        return self.base


def _format_precise(seconds):
    whole = int(seconds)
    frac = f"{seconds - whole:.3f}"[1:].rstrip("0").rstrip(".")
    hours, rest = divmod(whole, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}{frac}"


def parse_time(cell):
    if cell.number is not None:
        try:
            fraction = float(cell.number)
        except ValueError:
            return ParsedTime(in_file=cell.number, error="This time can't be read.")
        if not 0 <= fraction < 1:
            return ParsedTime(
                in_file=cell.number, error="This number isn't a time of day."
            )
        hours, minutes, seconds = excel_display_hms(fraction)
        precise = round(fraction * 86400, 3)
        return ParsedTime(
            base=f"{hours:02d}:{minutes:02d}:{seconds:02d}",
            precise=precise,
            in_file=_format_precise(precise),
        )
    return parse_time_text(cell.text or "")


def parse_time_text(text):
    shown = " ".join(text.split())
    if not shown:
        return ParsedTime(error="There is no time for this runner.")
    if shown.upper() == DNF:
        return ParsedTime(base=DNF, in_file=shown)
    match = TIME_RE.match(shown)
    if not match or int(match[2]) > 59 or int(match[3]) > 59:
        return ParsedTime(
            in_file=shown,
            error='This time isn\'t in the form 00:23:45 (or "DNF").',
        )
    return ParsedTime(
        base=f"{int(match[1]):02d}:{match[2]}:{match[3]}",
        suffix=int(match[4]) if match[4] else None,
        in_file=shown,
    )


def is_valid_time_text(text):
    parsed = parse_time_text(text or "")
    return not parsed.error and parsed.text == text


def assign_tie_suffixes(times):
    """Give runners who share a displayed second " 1", " 2", ... in finishing
    order: by the precise time where the file has one, then by file order.
    Groups that already carry suffixes are left alone."""
    groups = defaultdict(list)
    for index, parsed in enumerate(times):
        if parsed.base and parsed.base != DNF:
            groups[parsed.base].append(index)
    for indexes in groups.values():
        if len(indexes) < 2:
            continue
        if any(times[i].suffix is not None for i in indexes):
            continue
        ordered = sorted(
            indexes,
            key=lambda i: (
                times[i].precise if times[i].precise is not None else 0.0,
                i,
            ),
        )
        if any(times[i].precise is None for i in indexes):
            ordered = indexes
        for place, i in enumerate(ordered, start=1):
            times[i].suffix = place
    return times


# ------------------------------------------------------- names and clubs

# Words that are normally written in lowercase inside a surname.
PARTICLES = {
    "de", "da", "del", "della", "di", "du", "dos", "das", "van", "von", "der",
    "den", "ter", "la", "le", "bin", "ibn", "al", "y",
}  # fmt: skip


def squeeze_spaces(text):
    return " ".join((text or "").split())


def repair_encoding(text):
    """Undo UTF-8 text that was read as Windows-1252 ("Ã\\x81ine" -> "Áine").
    Text that isn't that kind of damage comes back unchanged."""
    if not text or all(ord(ch) < 128 for ch in text):
        return text
    raw = bytearray()
    for ch in text:
        try:
            raw += ch.encode("cp1252")
        except UnicodeEncodeError:
            if ord(ch) < 256:
                raw.append(ord(ch))
            else:
                return text
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return text


def _letters(text):
    return [ch for ch in text if ch.isalpha()]


def has_no_casing(text):
    """True when the text is all lowercase or all capitals, so it says nothing
    about how the name should be capitalised."""
    letters = _letters(text)
    if len(letters) < 2:
        return False
    return all(ch.islower() for ch in letters) or all(ch.isupper() for ch in letters)


def _capitalise(word):
    return word[:1].upper() + word[1:].lower()


def clean_name_part(text):
    """Tidy a first name or a last name. Returns ``(cleaned, reasons)``.

    Only obvious slips are fixed: all-lowercase words, ALL-CAPS names and the
    second half of a hyphenated name. A word that already mixes cases
    (McDade, MacIndoe, O'Leary) is the runner's own spelling and is kept.
    """
    reasons = []
    repaired = repair_encoding(text or "")
    if repaired != (text or ""):
        reasons.append("encoding")
    squeezed = squeeze_spaces(repaired)
    if squeezed != repaired:
        reasons.append("spaces")

    shouting = len(_letters(squeezed)) >= 2 and all(
        ch.isupper() for ch in _letters(squeezed)
    )
    tokens = re.split(r"([ \-'’])", squeezed)
    words = [t for t in tokens[::2] if t]
    out = []
    for index, token in enumerate(tokens):
        if index % 2 or not token:
            out.append(token)
            continue
        if shouting:
            out.append(_capitalise(token))
        elif token.islower():
            if token in PARTICLES and len(words) > 1 and token != words[-1]:
                out.append(token)
            else:
                out.append(_capitalise(token))
        elif token.isupper() and len(token) >= 3:
            out.append(_capitalise(token))
        elif token[:1].islower():
            out.append(token[:1].upper() + token[1:])
        else:
            out.append(token)
    cleaned = "".join(out)
    if cleaned != squeezed:
        reasons.append("capitals")
    return cleaned, reasons


MC_RE = re.compile(r"^(mc[a-z]{3,}|mac[a-z]{4,})$")


def mc_alternative(raw, cleaned):
    """For a surname typed without usable capitals that starts Mc or Mac,
    the other common way to write it (Mcleod -> McLeod), else ``None``."""
    if not has_no_casing(raw):
        return None
    tokens = re.split(r"([ \-])", cleaned)
    changed = False
    for index in range(0, len(tokens), 2):
        word = tokens[index]
        if MC_RE.match(word.casefold()):
            cut = 2 if word.casefold().startswith("mc") else 3
            tokens[index] = word[:cut] + word[cut : cut + 1].upper() + word[cut + 1 :]
            changed = True
    return "".join(tokens) if changed else None


def match_key(text):
    """Letters and digits only, no accents, no case: what makes two spellings
    'the same name written differently'."""
    plain = unicodedata.normalize("NFKD", text or "")
    plain = plain.encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", plain.casefold())


def name_key(first, last):
    return f"{match_key(first)}|{match_key(last)}"


def name_rule_key(first, last):
    """Key for a remembered name decision: the spelling as typed, without
    case or extra spaces."""
    return f"{squeeze_spaces(first).casefold()}|{squeeze_spaces(last).casefold()}"


def is_blank_club(text):
    return match_key(text) in ("", "unaffiliated")


def season_label(year):
    return f"{year}/{(year + 1) % 100:02d}"


def full_name(pair):
    return " ".join(part for part in pair if part)


@dataclass(frozen=True)
class KnownRunner:
    id: int
    first: str
    last: str
    season: int
    club: str = ""

    @property
    def pair(self):
        return (self.first, self.last)


@dataclass
class Rules:
    """Decisions remembered from earlier uploads."""

    names: dict = field(default_factory=dict)  # name_rule_key -> (first, last)
    clubs: dict = field(default_factory=dict)  # match_key(club) -> spelling
    different: set = field(default_factory=set)  # frozenset of two name keys


class Reference:
    """What the site already knows: runners of every season, their clubs."""

    def __init__(self, runners, season, rules=None):
        self.season = season
        self.rules = rules or Rules()
        self.current_exact = {}
        self.current_by_key = defaultdict(list)
        self.other_by_key = defaultdict(list)
        self.by_joined = defaultdict(list)
        club_counts = defaultdict(Counter)
        for runner in runners:
            key = name_key(runner.first, runner.last)
            if runner.season == season:
                self.current_exact[runner.pair] = runner
                self.current_by_key[key].append(runner)
            else:
                self.other_by_key[key].append(runner)
            self.by_joined[key.replace("|", "")].append(runner)
            if not is_blank_club(runner.club):
                club_counts[match_key(runner.club)][(runner.season, runner.club)] += 1
        self.clubs = {}
        for key, counts in club_counts.items():
            latest = max(season_ for season_, _ in counts)
            spellings = sorted(
                (
                    (n, club)
                    for (season_, club), n in counts.items()
                    if season_ == latest
                ),
                key=lambda item: (-item[0], item[1]),
            )
            self.clubs[key] = spellings[0][1]

    def other_spellings(self, key):
        """Spellings used in other seasons, most recent season first."""
        seen = {}
        for runner in sorted(self.other_by_key.get(key, []), key=lambda r: -r.season):
            seen.setdefault(runner.pair, runner.season)
        return list(seen.items())

    def similar_clubs(self, key):
        found = []
        for known_key, spelling in self.clubs.items():
            contained = min(len(key), len(known_key)) >= 4 and (
                key in known_key or known_key in key
            )
            close = difflib.SequenceMatcher(None, key, known_key).ratio() >= 0.82
            if contained or close:
                found.append(spelling)
        return sorted(found)[:4]

    def near_runners(self, first, last, taken_keys):
        """Known runners whose name is nearly this one. ``taken_keys`` are the
        names of other rows in the same file: a known runner who is also in
        this race under their own name is clearly someone else."""
        key = name_key(first, last)
        joined = key.replace("|", "")
        first_key, last_key = key.split("|")
        found = {}
        for other_joined, runners in self.by_joined.items():
            if other_joined == joined:
                continue
            other = runners[0]
            other_key = name_key(other.first, other.last)
            if other_key in taken_keys:
                continue
            if frozenset((key, other_key)) in self.rules.different:
                continue
            other_first, other_last = other_key.split("|")
            matcher = difflib.SequenceMatcher(None, joined, other_joined)
            close = (
                matcher.real_quick_ratio() >= 0.88
                and matcher.quick_ratio() >= 0.88
                and matcher.ratio() >= 0.88
            )
            short_form = (
                last_key == other_last
                and min(len(first_key), len(other_first)) >= 3
                and (
                    first_key.startswith(other_first)
                    or other_first.startswith(first_key)
                )
            )
            if not (close or short_form):
                continue
            best = max(runners, key=lambda r: (r.season == self.season, r.season))
            found[other_key] = (matcher.ratio(), best, runners)
        ranked = sorted(found.values(), key=lambda item: -item[0])
        return [(best, runners) for _, best, runners in ranked[:3]]


# --------------------------------------------------------------- proposals

AUTOMATIC, REMEMBERED, DECIDED, MANUAL = "automatic", "remembered", "decided", "manual"
APPLIED, PENDING, REVERTED = "applied", "pending", "reverted"

REASONS = {
    "encoding": "broken characters repaired",
    "spaces": "extra spaces removed",
    "capitals": "capital letters fixed",
}


@dataclass
class Change:
    field: str  # "name", "club" or "category"
    before: object  # [first, last] for a name, text otherwise
    after: object = None
    rule: str = ""
    reason: str = ""
    source: str = AUTOMATIC
    status: str = APPLIED
    options: list = field(default_factory=list)


@dataclass
class RowProposal:
    number: int
    raw: dict
    first_name: str
    last_name: str
    bib: str
    category: str
    club: str
    time_text: str
    changes: list = field(default_factory=list)


def _sentence(parts):
    text = "; ".join(p for p in parts if p)
    return text[:1].upper() + text[1:] if text else ""


def _propose_name(row, reference, taken_keys):
    raw = [row.first_name, row.last_name]
    changes = []

    remembered = reference.rules.names.get(name_rule_key(*raw))
    if remembered and list(remembered) != raw:
        changes.append(
            Change(
                "name",
                raw,
                list(remembered),
                "remembered",
                "Remembered from an earlier upload",
                source=REMEMBERED,
            )
        )
        return list(remembered), changes

    first, first_reasons = clean_name_part(row.first_name)
    last, last_reasons = clean_name_part(row.last_name)
    current = [first, last]
    reasons = [REASONS[r] for r in dict.fromkeys(first_reasons + last_reasons)]
    key = name_key(first, last)
    decision = None

    if tuple(current) in reference.current_exact:
        pass
    elif key in reference.current_by_key:
        current = list(reference.current_by_key[key][0].pair)
        reasons.append("matches this runner's name earlier this season")
    elif key in reference.other_by_key:
        spellings = reference.other_spellings(key)
        if tuple(current) not in [pair for pair, _ in spellings]:
            pair, year = spellings[0]
            if has_no_casing(full_name(raw)):
                current = list(pair)
                reasons.append(f"spelled as in {season_label(year)}")
            else:
                seasons = ", ".join(season_label(y) for _, y in spellings)
                options = [
                    {
                        "label": f'Use "{full_name(p)}", as in {season_label(y)}',
                        "value": list(p),
                        "scope": "row",
                    }
                    for p, y in spellings
                ]
                options.append(
                    {
                        "label": f'Use "{full_name(current)}" for this season only',
                        "value": current,
                        "scope": "row",
                    }
                )
                options.append(
                    {
                        "label": f'Use "{full_name(current)}" everywhere '
                        f"(also renames this runner in {seasons})",
                        "value": current,
                        "scope": "all",
                        "rename_key": key,
                    }
                )
                decision = Change(
                    "name",
                    current,
                    None,
                    "earlier_spelling",
                    f"This runner was spelled differently in {seasons}",
                    source=DECIDED,
                    status=PENDING,
                    options=options,
                )
    else:
        near = reference.near_runners(first, last, taken_keys)
        alternative = mc_alternative(row.last_name, last)
        if near:
            options = []
            for best, runners in near:
                other_key = name_key(best.first, best.last)
                where = (
                    "this season"
                    if best.season == reference.season
                    else season_label(best.season)
                )
                options.append(
                    {
                        "label": f'Same person as "{full_name(best.pair)}" ({where}): '
                        f'use "{full_name(best.pair)}"',
                        "value": list(best.pair),
                        "scope": "row",
                        "remember_name": True,
                    }
                )
                this_season = [r.id for r in runners if r.season == reference.season]
                options.append(
                    {
                        "label": f'Same person as "{full_name(best.pair)}": '
                        f'use "{full_name(current)}" for this season',
                        "value": current,
                        "scope": "season" if this_season else "row",
                        "rename_key": other_key,
                    }
                )
                if any(r.season != reference.season for r in runners):
                    options.append(
                        {
                            "label": f'Same person as "{full_name(best.pair)}": '
                            f'use "{full_name(current)}" everywhere',
                            "value": current,
                            "scope": "all",
                            "rename_key": other_key,
                        }
                    )
            options.append(
                {
                    "label": "Different people: keep "
                    f'"{full_name(current)}" as a new runner',
                    "value": current,
                    "scope": "row",
                    "different_from": [name_key(b.first, b.last) for b, _ in near],
                }
            )
            names = ", ".join(f'"{full_name(b.pair)}"' for b, _ in near)
            decision = Change(
                "name",
                current,
                None,
                "near_match",
                f"Very close to a known runner: {names}",
                source=DECIDED,
                status=PENDING,
                options=options,
            )
        elif alternative and alternative != last:
            decision = Change(
                "name",
                current,
                None,
                "mc_capitals",
                "The file doesn't show how this surname is capitalised",
                source=DECIDED,
                status=PENDING,
                options=[
                    {
                        "label": f'Use "{full_name(current)}"',
                        "value": current,
                        "scope": "row",
                    },
                    {
                        "label": f'Use "{full_name([first, alternative])}"',
                        "value": [first, alternative],
                        "scope": "row",
                    },
                ],
            )

    if current != raw:
        changes.append(Change("name", raw, current, "cleaned", _sentence(reasons)))
    if decision is not None:
        decision.before = current
        changes.append(decision)
    return current, changes


def _propose_club(row, reference):
    raw = row.club
    changes = []
    repaired = repair_encoding(raw)
    club = squeeze_spaces(repaired)
    reasons = []
    if repaired != raw:
        reasons.append(REASONS["encoding"])
    if club != repaired:
        reasons.append(REASONS["spaces"])
    if not club:
        return "", changes

    key = match_key(club)
    remembered = reference.rules.clubs.get(key)
    if remembered is not None:
        if remembered != raw:
            changes.append(
                Change(
                    "club",
                    raw,
                    remembered,
                    "remembered",
                    "Remembered from an earlier upload",
                    source=REMEMBERED,
                )
            )
        return remembered, changes

    decision = None
    if key in reference.clubs:
        if reference.clubs[key] != club:
            club = reference.clubs[key]
            reasons.append("spelled as this club already is on the site")
    else:
        similar = reference.similar_clubs(key)
        if similar:
            options = [
                {
                    "label": f'Same club as "{s}": use "{s}"',
                    "value": s,
                    "scope": "row",
                    "remember_club": True,
                }
                for s in similar
            ]
            options.append(
                {
                    "label": f'A different club: keep "{club}"',
                    "value": club,
                    "scope": "row",
                    "remember_club": True,
                }
            )
            decision = Change(
                "club",
                club,
                None,
                "similar_club",
                "This club isn't on the site yet, but a similar one is",
                source=DECIDED,
                status=PENDING,
                options=options,
            )
        elif has_no_casing(club) and len(_letters(club)) >= 4:
            titled = " ".join(_capitalise(w) for w in club.split(" "))
            options = [
                {
                    "label": f'Use "{titled}"',
                    "value": titled,
                    "scope": "row",
                    "remember_club": True,
                },
                {
                    "label": f'Keep "{club}"',
                    "value": club,
                    "scope": "row",
                    "remember_club": True,
                },
            ]
            if titled != club:
                decision = Change(
                    "club",
                    club,
                    None,
                    "club_capitals",
                    "A new club, and the file doesn't show how it is capitalised",
                    source=DECIDED,
                    status=PENDING,
                    options=options,
                )

    if club != raw:
        changes.append(Change("club", raw, club, "cleaned", _sentence(reasons)))
    if decision is not None:
        changes.append(decision)
    return club, changes


def propose(sheet, reference):
    """Work out the site's version of every row and the changes that get
    there. Nothing is decided silently: each difference from the file is a
    ``Change``, either applied (and revertable) or pending a decision."""
    times = assign_tie_suffixes([parse_time(row.time) for row in sheet.rows])

    cleaned_keys = Counter()
    for row in sheet.rows:
        first, _ = clean_name_part(row.first_name)
        last, _ = clean_name_part(row.last_name)
        cleaned_keys[name_key(first, last)] += 1

    proposals = []
    for row, parsed in zip(sheet.rows, times):
        first, _ = clean_name_part(row.first_name)
        last, _ = clean_name_part(row.last_name)
        own_key = name_key(first, last)
        taken = {k for k, n in cleaned_keys.items() if k != own_key or n > 1}

        name, changes = _propose_name(row, reference, taken)
        club, club_changes = _propose_club(row, reference)
        changes += club_changes

        category = squeeze_spaces(row.category).upper()
        if category != row.category:
            changes.append(
                Change(
                    "category",
                    row.category,
                    category,
                    "cleaned",
                    "Written the way the site writes categories",
                )
            )

        proposals.append(
            RowProposal(
                number=row.number,
                raw={
                    "first_name": row.first_name,
                    "last_name": row.last_name,
                    "bib": row.bib,
                    "category": row.category,
                    "club": row.club,
                    "time": parsed.in_file,
                    "time_error": parsed.error,
                    "time_is_precise": parsed.precise is not None,
                },
                first_name=name[0],
                last_name=name[1],
                bib=row.bib,
                category=category,
                club=club,
                time_text=parsed.text,
                changes=changes,
            )
        )
    return proposals


def check_rows(rows, valid_categories):
    """Problems that stop a draft being published, per row number.

    ``rows`` are dicts with number, first_name, last_name, category and
    time_text, holding the values as they currently stand in the draft.
    """
    problems = defaultdict(list)
    names = defaultdict(list)
    times = defaultdict(list)
    for row in rows:
        if not row["first_name"].strip() or not row["last_name"].strip():
            problems[row["number"]].append("The first name or last name is missing.")
        else:
            names[name_key(row["first_name"], row["last_name"])].append(row["number"])
        if row["category"] not in valid_categories:
            shown = row["category"] or "blank"
            problems[row["number"]].append(
                f"\"{shown}\" isn't one of the site's categories."
            )
        if not is_valid_time_text(row["time_text"]):
            problems[row["number"]].append(
                "The time has to look like 00:23:45, 00:23:45 1 or DNF."
            )
        elif row["time_text"] != DNF:
            times[row["time_text"]].append(row["number"])
    for numbers in names.values():
        for number in numbers if len(numbers) > 1 else []:
            others = ", ".join(str(n) for n in numbers if n != number)
            problems[number].append(
                f"Same name as row {others}. The site holds one runner per name "
                "each season, so one of them needs changing."
            )
    for numbers in times.values():
        for number in numbers if len(numbers) > 1 else []:
            others = ", ".join(str(n) for n in numbers if n != number)
            problems[number].append(
                f"Same time as row {others}. Tied times need 1, 2, ... after them."
            )
    return dict(problems)
