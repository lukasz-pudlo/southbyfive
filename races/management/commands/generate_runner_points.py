import pandas as pd
from django.core.management.base import BaseCommand
from django.db.models import Max
from races.models import Race, Runner
from race_versions.models import ResultVersion
from classifications.models import ClassificationResult


class Command(BaseCommand):
    help = 'Generate an Excel file with runners and their points for a specified season, and validate classification points based on the most recent ResultVersion.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--runner-ids',
            nargs='+',
            type=int,
            help='List of runner IDs to validate and generate the Excel file for',
        )
        parser.add_argument(
            '--season-start-year',
            type=int,
            required=True,
            help='Specify the season start year to fetch relevant data',
        )

    def handle(self, *args, **kwargs):
        runner_ids = kwargs.get('runner_ids')
        season_start_year = kwargs.get('season_start_year')

        # Create an empty DataFrame to store the results
        results_data = []
        validation_errors = []

        # Fetch runners based on runner_ids if provided
        if runner_ids:
            runners = Runner.objects.filter(id__in=runner_ids)
        else:
            runners = Runner.objects.all()

        # Fetch races for the specified season
        races = Race.objects.filter(season_start_year=season_start_year)

        if not races.exists():
            self.stdout.write(self.style.ERROR(
                f"No races found for the season start year {season_start_year}"))
            return

        # Prepare column headers
        column_headers = ['Runner Name', 'Total General Points',
                          'Total Gender Points', 'Validation Status']
        for race in races:
            column_headers.append(f"{race.name} - General Points")

        for runner in runners:
            # Start with the runner's name
            row = [f"{runner.first_name} {runner.last_name}"]

            total_general_points = 0
            total_gender_points = 0
            race_points = []

            for race in races:
                # Get the most recent version of the result for this runner and race
                most_recent_result_version = ResultVersion.objects.filter(
                    result__runner=runner, result__race=race
                ).order_by('-version').first()

                if most_recent_result_version:
                    race_points.append(
                        most_recent_result_version.general_points or 0)
                    total_general_points += most_recent_result_version.general_points or 0
                    total_gender_points += most_recent_result_version.gender_points or 0
                else:
                    # If no ResultVersion exists for this race, log as missing
                    race_points.append(None)

            # If the runner participated in all races, drop the worst result
            if len([p for p in race_points if p is not None]) == races.count():
                total_general_points -= min(filter(None,
                                            race_points), default=0)

            row.extend(race_points)
            row.insert(1, total_general_points)
            row.insert(2, total_gender_points)

            # Validate classification points
            try:
                classifications = ClassificationResult.objects.filter(
                    runner=runner, classification__race__season_start_year=season_start_year
                )
                if classifications.exists():
                    classification_result = classifications.first()
                    if classification_result.general_points != total_general_points:
                        validation_errors.append(
                            f"Mismatch for {runner.first_name} {runner.last_name}: "
                            f"Expected {classification_result.general_points}, Calculated {total_general_points}"
                        )
                        row.append('Error')
                    else:
                        row.append('Valid')
                else:
                    validation_errors.append(
                        f"No classification result found for {runner.first_name} {runner.last_name}")
                    row.append('Missing')
            except ClassificationResult.DoesNotExist:
                validation_errors.append(
                    f"No classification result found for {runner.first_name} {runner.last_name}")
                row.append('Missing')

            results_data.append(row)

        # Convert the results data to a DataFrame
        df = pd.DataFrame(results_data, columns=column_headers)

        # Save the DataFrame to an Excel file
        excel_file = f'runner_points_validation_{season_start_year}.xlsx'
        df.to_excel(excel_file, index=False)

        self.stdout.write(self.style.SUCCESS(
            f"Excel file '{excel_file}' generated successfully!"
        ))

        if validation_errors:
            self.stdout.write(self.style.ERROR("Validation Errors:"))
            for error in validation_errors:
                self.stdout.write(self.style.ERROR(f"  - {error}"))
        else:
            self.stdout.write(self.style.SUCCESS(
                "All classification points are valid!"))
