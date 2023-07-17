import pandas as pd
import random
from faker import Faker

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