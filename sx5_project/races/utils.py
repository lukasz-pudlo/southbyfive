import pandas as pd
import random
from faker import Faker

from races.models import Race, Result, Runner, Classification, ClassificationResult
from race_versions.models import ResultVersion, RaceVersion
from collections import Counter, defaultdict


def generate_test_results():
    fake = Faker()

    # Categories for runners with corresponding base times (in minutes)
    categories = {
        'MS': (15, 20), 'FS': (16, 21),
        'M40': (18, 23), 'F40': (19, 24),
        'M50': (20, 25), 'F50': (21, 26),
        'M60': (25, 30), 'F60': (26, 31),
        'M70': (30, 35), 'F70': (31, 36)
    }

    races = ['kings', 'linn', 'rouken', 'pollok', 'bellahouston', 'queens']

    # Function to generate random time

    def generate_time(base_time):
        minutes = str(random.randint(*base_time)).zfill(2)
        seconds = str(random.randint(0, 59)).zfill(2)
        return f'00:{minutes}:{seconds}'

    # Generate data for runners
    runners = {}
    for _ in range(100):
        first_name = fake.first_name()
        middle_name = fake.first_name()
        last_name = fake.last_name()
        category, base_time = random.choice(list(categories.items()))
        # Store each runner's category and base time
        time = generate_time(base_time)
        runners[(first_name, middle_name, last_name, category)] = time

    # 65% of participants will take part in all races
    all_races_runners = random.sample(list(runners.keys()), 65)

    # Generate results for each race
    for race in races:
        # All runners participate
        participants = all_races_runners.copy()

        # Add some random runners from the remaining 35% pool
        remaining_runners = [r for r in runners if r not in all_races_runners]
        participants.extend(random.sample(
            remaining_runners, random.randint(0, 35)))

        data = []
        for participant in participants:
            # Slight variation in each runner's time for each race
            time_variation = random.randint(-2, 2)
            base_time_minutes, base_time_seconds = runners[participant].split(':')[
                1:]
            new_time_minutes = max(
                15, min(35, int(base_time_minutes) + time_variation))
            time = f'00:{str(new_time_minutes).zfill(2)}:{base_time_seconds}'

            data.append(list(participant) + [time])

        # Convert data to DataFrame
        df = pd.DataFrame(
            data, columns=['First Name', 'Middle Name', 'Last Name', 'Category', 'Time'])

        # Define text format for Excel
        writer = pd.ExcelWriter(f'{race}.xlsx', engine='xlsxwriter')

        # Write dataframe to excel
        df.to_excel(writer, index=False)

        # Get xlsxwriter workbook and worksheet objects to apply text format
        workbook = writer.book
        worksheet = writer.sheets['Sheet1']

        # Define cell format for text
        cell_format = workbook.add_format()
        cell_format.set_num_format('@')

        # Apply cell format to range of data
        worksheet.set_column('A:E', None, cell_format)

        # Save the Excel file
        writer.close()


def create_result_versions(new_race):
    """
    Create a ResultVersion instance for each Result of a Race.
    """

    total_races = Race.objects.count()

    # Step 1: Create initial RaceVersion and its ResultVersions for the new race
    race_version = RaceVersion.objects.create(race=new_race, version_number=1)
    for result in new_race.result_set.all():
        ResultVersion.objects.create(
            result=result,
            race_version=race_version,
            version=1,
            general_points=result.general_position,
            gender_points=result.gender_position,
            category_points=result.category_position
        )

    # If there are only 2 races or less, we stop here
    if total_races <= 2:
        create_classification(new_race)
        return

    # Get runners who have participated in n-1 races
    all_race_results = Result.objects.all().values('runner_id')
    runner_participation_counts = Counter(
        entry['runner_id'] for entry in all_race_results)
    qualifying_runner_ids = [runner_id for runner_id,
                             count in runner_participation_counts.items() if count >= total_races - 1]

    # For each existing Race (including the new one), create an additional RaceVersion
    for race in Race.objects.all():
        current_version_number = RaceVersion.objects.filter(race=race).count()
        new_version_number = current_version_number + 1
        race_version = RaceVersion.objects.create(
            race=race, version_number=new_version_number)

        revised_results = race.result_set.filter(
            runner_id__in=qualifying_runner_ids).all()
        general_positions, gender_positions_mapping, category_positions_mapping = recalculate_positions(
            revised_results)

        for result in revised_results:
            runner_id = result.runner_id
            gender = get_gender_from_category(result.runner.category)

            ResultVersion.objects.create(
                result=result,
                race_version=race_version,
                version=new_version_number,
                general_points=general_positions.get(runner_id, 0),
                gender_points=gender_positions_mapping.get(
                    runner_id, {}).get(gender, 0),
                category_points=category_positions_mapping.get(
                    runner_id, {}).get(result.runner.category, 0)
            )

    create_classification(new_race)


def recalculate_positions(results):
    sorted_results = sorted(results, key=lambda x: x.time)

    general_positions = {}
    gender_positions = defaultdict(int)
    category_positions = defaultdict(int)
    gender_positions_mapping = defaultdict(dict)
    category_positions_mapping = defaultdict(dict)

    for index, result in enumerate(sorted_results, 1):
        runner_id = result.runner_id
        gender = get_gender_from_category(result.runner.category)

        general_positions[runner_id] = index
        gender_positions[gender] += 1
        category_positions[result.runner.category] += 1

        gender_positions_mapping[runner_id][gender] = gender_positions[gender]
        category_positions_mapping[runner_id][result.runner.category] = category_positions[result.runner.category]

    return general_positions, gender_positions_mapping, category_positions_mapping


def get_gender_from_category(category):
    if category.startswith('F'):
        return 'Female'
    elif category.startswith('M'):
        return 'Male'
    else:
        raise ValueError(f"Invalid category: {category}")


def create_classification_entries(new_race, current_race_version_number):
    # Create the Classification object
    classification, _ = Classification.objects.get_or_create(
        race=new_race,
        version_number=current_race_version_number
    )

    # Fetch all race versions up to the current version
    race_versions = RaceVersion.objects.filter(
        race=new_race,
        version_number__lte=current_race_version_number
    )

    # Fetch only runners that have participated in at least one race
    runners_with_results = Runner.objects.filter(
        result__race__in=Race.objects.all()).distinct()

    for runner in runners_with_results:
        # For each runner, sum up the points from associated result versions
        result_versions = ResultVersion.objects.filter(
            result__runner=runner,
            race_version__in=race_versions
        )

        total_general_points = sum(rv.general_points for rv in result_versions)
        total_gender_points = sum(rv.gender_points for rv in result_versions)
        total_category_points = sum(rv.category_points for rv in result_versions)

        ClassificationResult.objects.update_or_create(
            runner=runner,
            classification=classification,
            defaults={
                'general_points': total_general_points,
                'gender_points': total_gender_points,
                'category_points': total_category_points
            }
        )

def create_classification(new_race):
    total_races = Race.objects.count()

    if total_races <= 2:
        create_classification_entries(new_race, 1)
    else:
        for current_race_version_number in range(1, total_races + 1):
            create_classification_entries(new_race, current_race_version_number)
