import os
import sys
from collections import Counter

import django

# Add your Django project's directory to the Python path
project_path = "/home/lukasz/projects/southbyfive"
sys.path.append(project_path)

# Setup Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sx5_project.settings")
django.setup()


def get_models():
    from races.models import Race, Result, Runner

    return Result, Runner, Race


def generate_all_races_runners_list():
    Result, Runner, Race = get_models()
    total_races = Race.objects.count()
    # Count the participation of each runner
    all_race_results = Result.objects.all().values("runner_id")
    runner_participation_counts = Counter(
        entry["runner_id"] for entry in all_race_results
    )

    # Filter runner IDs that have participated in all races
    all_races_runner_ids = [
        runner_id
        for runner_id, count in runner_participation_counts.items()
        if count == total_races
    ]

    all_races_runners = Runner.objects.filter(id__in=all_races_runner_ids)

    # Prepare the list of runner names
    runner_names = [runner.__str__() for runner in all_races_runners]

    # Write the list to a text file
    with open("all_races_runner_list.txt", "w") as file:
        for name in runner_names:
            file.write(name + "\n")

    print("List of runners who participated in all races generated.")


if __name__ == "__main__":
    generate_all_races_runners_list()
