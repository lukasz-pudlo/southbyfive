from datetime import datetime

import pandas as pd
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

race_files_location = f"{settings.BASE_DIR.parent}/races/race_files"


class Command(BaseCommand):
    help = "Formats the supplied Excel file"

    def add_arguments(self, parser):
        parser.add_argument("filenames", nargs="+",
                            help="List of files to process")

    def handle(self, *args, **options):
        for filename in options["filenames"]:
            try:
                df = pd.read_excel(f"{race_files_location}/{filename}.xlsx")
                print(
                    f"The types of data of {filename} are as follows: {df.dtypes}")
                df = df.rename(
                    columns={
                        "Number": "Participant Number",
                        "Forename": "First Name",
                        "Surname": "Last Name",
                        "Age_on_Race_Day": "Category",
                    }
                )
                print(f"The import Excel data as pandas dataframe: {df}")

                # Convert Time column to string format HH:MM:SS
                def format_time(x):
                    if x == "DNF" or pd.isna(x):
                        return x
                    # Convert time to timedelta, round to nearest second, then format
                    td = pd.Timedelta(
                        hours=x.hour, minutes=x.minute, seconds=x.second, microseconds=x.microsecond)
                    td_rounded = td.round('s')
                    total_seconds = int(td_rounded.total_seconds())
                    hours = total_seconds // 3600
                    minutes = (total_seconds % 3600) // 60
                    seconds = total_seconds % 60
                    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

                df['Time'] = df['Time'].apply(format_time)
                df = df[['First Name', 'Last Name',
                         'Participant Number', 'Category', 'Club', 'Time']]
                print(f"The df after time formatting: {df}")

                df.to_excel(f"{race_files_location}/kings.xlsx", index=False)
            except Exception as e:
                raise CommandError(
                    f"There was an error processing {filename}: {e}")
