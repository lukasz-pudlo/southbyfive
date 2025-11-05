from datetime import datetime

import pandas as pd
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

race_files_location = f"{settings.BASE_DIR.parent}/races/race_files"


class Command(BaseCommand):
    help = "Formats the supplied Excel file"

    def add_arguments(self, parser):
        parser.add_argument("filenames", nargs="+", help="List of files to process")

    def handle(self, *args, **options):
        for filename in options["filenames"]:
            try:
                df = pd.read_excel(f"{race_files_location}/{filename}.xlsx")
                print(f"The types of data of {filename} are as follows: {df.dtypes}")
                df = df.rename(
                    columns={
                        "Number": "Paricipant Number",
                        "Forename": "First Name",
                        "Surname": "Last Name",
                        "Age_on_Race_Day": "Category",
                    }
                )
                print(f"The import Excel data as pandas dataframe: {df}")
                # df['Time'] = df['Time'].dt.strftime('%H:%M:%S')
                # print(f"The df after time formatting: {df}")
                df.to_excel(f"{race_files_location}/kings.xlsx")
            except Exception as e:
                raise CommandError(f"There was an error processing {filename}: {e}")
