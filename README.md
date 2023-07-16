# South by Five Running Race Series Project

## Overview

The project's main goal is to manage a running race series consisting of six races and to calculate a general classification based on runners' performances across all races.

# Race Series Points Calculation - Requirements

This document outlines the specific requirements for a series of races, with a focus on the process of assigning and recalculating points based on runner participation and finishing positions.

## Points Calculation Overview

- We are organizing a series of races, with a total of six races in the series.
- We are keeping track of the runners and their results in each race using an existing model structure (`Race`, `Runner`, `Result`).
- For each race, we want to assign points to the runners based on their finishing positions. Points are assigned separately for runners in male and female categories.
- The category of a runner can be identified by the first letter of their category string ("M" for male, "F" for female).

## Specific Requirements

1. **Initial Points Calculation**: After the first two races, points are calculated normally for all participants.
   
2. **Modified Points Calculation**: Starting from the third race, a runner's points will not be calculated if they haven't participated in at least (n-1) races, where n is the current total number of races.

3. **Subsequent Races**: The logic from the previous point applies for subsequent races. For instance:
   - After four races, a runner's points won't be calculated if they haven't participated in at least three races.
   - After five races, runners would need to have participated in at least four.
   - After all six races, runners would need to have participated in at least five to have their points calculated.

4. **Automatic Recalculation**: This process of recalculating points and adjusting runner participation requirements should happen automatically each time a new race is added.

5. **Data Integrity**: We want to keep the original results of each race intact. The updated points calculations and adjustments to runner participation requirements should be stored in a way that does not modify the original `Race`, `Runner`, and `Result` models.
