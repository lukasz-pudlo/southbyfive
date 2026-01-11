# South by Five Running Race Series Project

## Overview

The project's main goal is to manage a running race series consisting of six races and to calculate a general classification based on runners' performances across all races.

# Race Series Points Calculation - Requirements

This document outlines the specific requirements for a series of races, with a focus on the process of assigning and recalculating points based on runner participation and finishing positions.

## Points Calculation Overview

- There are six races in the series.
- We are keeping track of the runners and their results in each race using an existing model structure (`Race`, `Runner`, `Result`).
- For each race, we want to assign points to the runners based on their finishing positions. Points are assigned separately for runners in male, female, and non-binary categories.
- The category of a runner can be identified by the first letter of their category string ("M" for male, "F" for female, "N" for Non-binary).

## Race Results File Format

A python management command has been added to help with the formatting of the Excel file with race results. The file needs to be placed in the race_files directly. Please ensure that the columns have the following headers:

- Forename
- Surname
- Gender
- Club
- Category (it will likely be "Age Category" in the file you receive from the race organiser)
- Participant Number (will likely be "Number")
- Time

If there are any additional columns, they will be ignored. 

Once the file with the correct headers is in the race_file directory, run the below command:

`python manage.py format_excel "{filename}"`

## Specific Requirements

1. **Initial Points Calculation**: After the first two races, points are calculated normally for all participants.
   
2. **Modified Points Calculation**: Starting from the third race, a runner's points will not be calculated if they haven't participated in at least (n-1) races, where n is the current total number of races.

3. **Subsequent Races**: The logic from the previous point applies for subsequent races. For instance:
   - After four races, a runner's points won't be calculated if they haven't participated in at least three races.
   - After five races, runners would need to have participated in at least four.
   - After all six races, runners would need to have participated in at least five to have their points calculated.

4. **Automatic Recalculation**: The process of recalculating points and adjusting runner participation requirements happens automatically each time a new race is added.

5. **Data Integrity**: We want to keep the original results of each race intact. The updated points calculations and adjustments to runner participation requirements should be stored in a way that does not modify the original `Race`, `Runner`, and `Result` models.

6. **Configuration**: After cloning the repository, add a .env file with the following configuration:
   - DJANGO_SECRET_KEY
   - DEBUG
   - DJANGO_ALLOWED_HOSTS
   - DATABASE_ENGINE
   - DATABASE_NAME
   - DATABASE_USERNAME
   - DATABASE_PASSWORD
   - DATABASE_HOST
   - DATABASE_PORT

7. **Docker Commands**: To run the project locally, use the following Docker commands: 

   docker compose build
   docker compose up -d
   docker compose exec web python manage.py migrate
   docker compose exec web python manage.py createsuperuser

8. **Sevalla Deployment**

Currently, the project is hosted on Sevalla. The selected project type is Django, with a build from Dockerfile. An instance of postgres database has been created. Sevalla provides a DB_URL variable, which is used by this project in production. 

For the time being, the migrations need to be run manually from the terminal on Sevalla. 
