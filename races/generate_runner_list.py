import os
import sys
import django
from collections import Counter

# Add your Django project's directory to the Python path
project_path = "/home/lukasz/projects/southbyfive"
sys.path.append(project_path)

# Setup Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sx5_project.settings")
django.setup()


def get_models():
    from races.models import Result, Runner, Race
    return Result, Runner, Race


def generate_all_races_runners_list():
    Result, Runner, Race = get_models()
    total_races = Race.objects.count()
    # Count the participation of each runner
    all_race_results = Result.objects.all().values('runner_id')
    runner_participation_counts = Counter(
        entry['runner_id'] for entry in all_race_results)

    # Filter runner IDs that have participated in 6 races. This can be changed to any number between 1 - 6 or to total_races
    six_races_runner_ids = [
        runner_id for runner_id, count in runner_participation_counts.items() if count == 6
    ]

    six_races_runners = Runner.objects.filter(id__in=six_races_runner_ids)

    # Filter runner IDs that have participated in 5 races
    five_races_runner_ids = [
        runner_id for runner_id, count in runner_participation_counts.items() if count == 5
    ]

    five_races_runners = Runner.objects.filter(id__in=five_races_runner_ids)

    # Prepare the list of runner names
    six_races_runner_names = [runner.__str__() for runner in six_races_runners]

    # Prepare the list of runner names
    five_races_runner_names = [runner.__str__()
                               for runner in five_races_runners]

    # Write the lists to a text file
    with open('six_races_runner_list.txt', 'w') as file:
        file.write(
            f"{len(six_races_runner_names)} participated in six races\n")
        for name in six_races_runner_names:
            file.write(name + '\n')

    print("List of runners who participated in six races generated.")

    with open('five_races_runner_list.txt', 'w') as file:
        file.write(
            f"{len(five_races_runner_names)} participated in five races\n")
        for name in five_races_runner_names:
            file.write(name + '\n')

    print("List of runners who participated in five races generated.")


if __name__ == "__main__":
    generate_all_races_runners_list()
