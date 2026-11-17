from collections import defaultdict

from django.core.management.base import BaseCommand

from races.models import Result, Runner
from results_import import normalise


class Command(BaseCommand):
    help = (
        "Read-only report on how consistently runners and clubs are spelled: "
        "one person held as two runner records in a season, names that differ "
        "between seasons, and clubs written more than one way. Changes nothing."
    )

    def handle(self, *args, **options):
        runners = list(Runner.objects.select_related("season").order_by("id"))
        races_run = defaultdict(set)
        for runner_id, race_id in Result.objects.values_list("runner_id", "race_id"):
            races_run[runner_id].add(race_id)

        by_season = defaultdict(lambda: defaultdict(list))
        by_key = defaultdict(lambda: defaultdict(set))
        clubs = defaultdict(lambda: defaultdict(set))
        for runner in runners:
            year = runner.season.season_start_year
            key = normalise.name_key(runner.first_name, runner.last_name)
            by_season[year][key].append(runner)
            by_key[key][(runner.first_name, runner.last_name)].add(year)
            if not normalise.is_blank_club(runner.club):
                clubs[normalise.match_key(runner.club)][runner.club].add(year)

        def label(year):
            return normalise.season_label(year)

        def name(runner):
            return f'"{runner.first_name} {runner.last_name}"'

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                "1. One person, two runner records in the same season"
            )
        )
        self.stdout.write(
            "   Correcting one of these to match the other is refused by the import,\n"
            "   because merging records changes who qualifies.\n"
        )
        found = False
        for year in sorted(by_season):
            for same in by_season[year].values():
                if len(same) > 1:
                    found = True
                    parts = ", ".join(
                        f"{name(r)} ({len(races_run[r.id])} races)" for r in same
                    )
                    self.stdout.write(f"   {label(year)}: {parts}")
        if not found:
            self.stdout.write("   None.")

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                "\n2. Nearly the same name in the same season, never in the same race"
            )
        )
        self.stdout.write("   Possibly one person entered two ways. Check by hand.\n")
        found = False
        for year in sorted(by_season):
            reference = normalise.Reference(
                [
                    normalise.KnownRunner(
                        r.id, r.first_name, r.last_name, year, r.club or ""
                    )
                    for same in by_season[year].values()
                    for r in same
                ],
                year,
            )
            seen = set()
            for key, same in by_season[year].items():
                runner = same[0]
                near = reference.near_runners(
                    runner.first_name, runner.last_name, set()
                )
                for other, _ in near:
                    pair = frozenset((runner.id, other.id))
                    if pair in seen or races_run[runner.id] & races_run[other.id]:
                        continue
                    seen.add(pair)
                    found = True
                    self.stdout.write(
                        f"   {label(year)}: {name(runner)} "
                        f"({len(races_run[runner.id])} races) and "
                        f'"{other.first} {other.last}" '
                        f"({len(races_run[other.id])} races)"
                    )
        if not found:
            self.stdout.write("   None.")

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                "\n3. Same name, spelled differently between seasons"
            )
        )
        self.stdout.write(
            '   These are what "use this spelling everywhere" would bring into line.\n'
        )
        found = False
        for spellings in by_key.values():
            if len(spellings) > 1:
                found = True
                parts = "; ".join(
                    f'"{first} {last}" in {", ".join(label(y) for y in sorted(years))}'
                    for (first, last), years in spellings.items()
                )
                self.stdout.write(f"   {parts}")
        if not found:
            self.stdout.write("   None.")

        self.stdout.write(
            self.style.MIGRATE_HEADING("\n4. Clubs written more than one way")
        )
        found = False
        for spellings in clubs.values():
            if len(spellings) > 1:
                found = True
                parts = "; ".join(
                    f'"{club}" in {", ".join(label(y) for y in sorted(years))}'
                    for club, years in spellings.items()
                )
                self.stdout.write(f"   {parts}")
        if not found:
            self.stdout.write("   None.")

        self.stdout.write(
            f"\n{len(runners)} runner records in {len(by_season)} seasons checked. "
            "Nothing was changed."
        )
