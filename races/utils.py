import pandas as pd
import random
from faker import Faker
from django.db.models import Max

from races.models import Race, Result, Runner
from race_versions.models import ResultVersion, RaceVersion
from classifications.models import Classification, ClassificationResult
from collections import Counter, defaultdict
from django.db.models import Count


def generate_test_results():
    fake = Faker()

    # Categories for runners with corresponding base times (in minutes)
    categories = {
        'MS': (15, 20), 'FS': (16, 21), 'NBS': (15, 20),
        'M40': (18, 23), 'F40': (19, 24), 'NB40': (19, 24),
        'M50': (20, 25), 'F50': (21, 26), 'NB50': (21, 26),
        'M60': (25, 30), 'F60': (26, 31), 'NB60': (26, 31),
        'M70': (30, 35), 'F70': (31, 36), 'NB70': (31, 36),
        'M80': (35, 40), 'F80': (37, 42), 'NB80': (45, 50),
    }

    races = ['kings', 'linn', 'rouken', 'pollok', 'bellahouston', 'queens']

    # Function to generate random time

    def generate_time(base_time):
        minutes = str(random.randint(*base_time)).zfill(2)
        seconds = str(random.randint(0, 59)).zfill(2)
        return f'00:{minutes}:{seconds}'

    # Generate data for runners
    runners = {}
    # Generate a list of fake clubs
    clubs = [fake.company() for _ in range(10)]

    for i in range(100):
        first_name = fake.first_name()
        last_name = fake.last_name()
        participant_number = str(i+1)
        category, base_time = random.choice(list(categories.items()))

        # 85% chance to assign a club, 15% to leave it empty
        club = random.choice(clubs) if random.random() < 0.85 else ""

        # Store each runner's category and base time
        time = generate_time(base_time)
        runners[(first_name, last_name, participant_number, category, club)] = time

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
            data, columns=['First Name', 'Last Name', 'Participant Number', 'Category', 'Club', 'Time'])

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
        worksheet.set_column('A:F', None, cell_format)

        # Save the Excel file
        writer.close()


def create_result_versions(new_race):
    # Update Result positions for the new_race
    new_race.calculate_positions()

    # Create initial RaceVersion and its ResultVersions for the new race
    create_initial_race_version(new_race)

    total_races = Race.objects.count()

    # When we have more than two races, we need to recalculate versions
    if total_races > 2:
        recalculate_race_versions()

    # Create or update the Classification
    create_classification_entries(new_race)


def create_initial_race_version(new_race):
    print(f"Debug: In create_initial_race_version, race id: {new_race.id}")

    initial_exists = RaceVersion.objects.filter(
        race=new_race, version_number=1).exists()
    print(f"Debug: Initial version exists: {initial_exists}")

    if not initial_exists:
        print("Debug: Creating new RaceVersion object")
        race_version = RaceVersion.objects.create(
            race=new_race, version_number=1)

        for result in new_race.result_set.all():
            print(f"Debug: Creating ResultVersion for result id: {result.id}")
            ResultVersion.objects.create(
                result=result,
                race_version=race_version,
                version=1,
                general_points=result.general_position,
                gender_points=result.gender_position,
                category_points=result.category_position,
            )


def recalculate_race_versions():
    total_races = Race.objects.count()
    all_race_results = Result.objects.all().values('runner_id')
    runner_participation_counts = Counter(
        entry['runner_id'] for entry in all_race_results)
    qualifying_runner_ids = [runner_id for runner_id,
                             count in runner_participation_counts.items() if count >= total_races - 1]

    for race in Race.objects.all():
        current_version_number = RaceVersion.objects.filter(race=race).aggregate(
            Max('version_number'))['version_number__max'] or 0
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


def create_classification_entries(new_race):
    total_races = Race.objects.count()

    # Determine qualifying runners
    all_race_results = Result.objects.all().values('runner_id')
    runner_participation_counts = Counter(
        entry['runner_id'] for entry in all_race_results)
    qualifying_runner_ids = set(
        runner_id for runner_id, count in runner_participation_counts.items() if count >= total_races - 1)

    highest_version = RaceVersion.objects.aggregate(Max('version_number'))[
        'version_number__max'] or 0
    print(highest_version)

    classification, _ = Classification.objects.get_or_create(
        race=new_race, version_number=highest_version)

    race_versions = RaceVersion.objects.filter(
        race__in=Race.objects.all()).order_by('race', 'version_number')
    latest_race_versions = {rv.race_id: rv for rv in race_versions}
    print('Printing race_versions')
    print(race_versions)
    print('Printing latest_race_versions')
    for race_id, race_version in latest_race_versions.items():
        print(f"Race ID: {race_id}, Race Version: {race_version}")

    runners_with_results = Runner.objects.filter(
        id__in=qualifying_runner_ids).distinct()
    print(runners_with_results)

    for runner in runners_with_results:
        print(
            f"Debug: Creating ClassificationResult for runner id: {runner.id}")

        result_versions = list(ResultVersion.objects.filter(
            result__runner=runner,
            race_version__in=latest_race_versions.values()
        ))

        # If the runner has participated in all n races, consider only the best n-1 results
        if total_races > 1 and len(result_versions) == total_races:
            result_versions = sorted(
                result_versions, key=lambda x: x.general_points)[:-1]

        total_general_points = sum(rv.general_points for rv in result_versions)
        total_gender_points = sum(rv.gender_points for rv in result_versions)
        total_category_points = sum(
            rv.category_points for rv in result_versions)

        ClassificationResult.objects.update_or_create(
            runner=runner,
            classification=classification,
            defaults={
                'general_points': total_general_points,
                'gender_points': total_gender_points,
                'category_points': total_category_points,
            }
        )


def recalculate_positions(results):
    sorted_results = sorted(
        [result for result in results],
        key=lambda x: x.time or pd.Timedelta.max
    )

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
    elif category.startswith('N'):
        return 'Non-binary'
    else:
        raise ValueError(f"Invalid category: {category}")


def get_list_of_runners_who_completed_five_races():
    runners = Runner.objects.annotate(
        num_races=Count('result')).filter(num_races=5)
    return runners
