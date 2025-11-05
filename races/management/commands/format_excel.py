import pandas as pd
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Formats the supplied Excel file"

    def add_arguments(self, parser):
        parser.add_argument("filenames", nargs="+",
                            help="List of files to process")

    def handle(self, *args, **options):
        for filename in options["filenames"]:
            try:
                df = pd.read_excel(
                    f"{settings.BASE_DIR.parent}/races/race_files/{filename}.xlsx")
                print(f"The import Excel data as pandas dataframe: {df}")
            except Exception as e:
                raise CommandError(
                    f"There was an error processing {filename}: {e}")
