# Nurse and Tech Scheduling System
[![Python Application CI](https://github.com/kosenburg/scheduling-constraint-program/actions/workflows/python-app.yml/badge.svg)](https://github.com/kosenburg/scheduling-constraint-program/actions/workflows/python-app.yml)

This project is a scheduling tool that uses constraint optimization to assign nurses and surgical technicians to shifts based on daily requirements and staff availability.

## Overview

The system uses Google OR-Tools (CP-SAT Solver) to find an optimal schedule that satisfies all constraints, including:
- Minimum/Maximum work days per staff member.
- Daily staffing requirements based on the number of Operating Rooms (OR) and Scope Rooms.
- Automatic calculation of additional staff needed if the current pool is insufficient.

## Project Structure

- `main.py`: The core script that calculates requirements, solves the scheduling problem, and exports results.
- `staff.json`: Input file containing the list of available nurses and technicians and their required work days.
- `schedule-parameters.json`: Input file defining the facility requirements for each day (OR rooms, Scope rooms, etc.).
- `staff_schedule.xlsx`: (Generated) The final output containing the calculated schedule.

## Installation

Ensure you have Python installed. Then, install the required dependencies:

```bash
pip install ortools pandas openpyxl
```

## Configuration

### 1. Staff Data (`staff.json`)
Define your available staff and how many days they are required to work per week.
```json
{
    "nurses": [
        {"first_name": "Alice", "last_name": "Smith", "required_days": 3},
        ...
    ],
    "techs": [
        {"first_name": "Sam", "last_name": "Wilson", "required_days": 4},
        ...
    ]
}
```

### 2. Schedule Parameters (`schedule-parameters.json`)
Define the daily requirements for the facility.
```json
{
    "days": [
        {
            "day": 1,
            "num_or_rooms": 3,
            "num_scope_rooms": 1,
            "num_float_nurses": 1,
            "num_lunch_relief_nurses": 1
        },
        ...
    ]
}
```

## Calculation Logic

The system automatically calculates daily staffing needs using the following formulas:

### Nurse Requirements:
- **(Number of OR Rooms × 2)** + **Float Nurses** + **Lunch Relief Nurses**

### Tech Requirements:
- **(Number of OR Rooms × 1)** + **(Number of Scope Rooms × 2)** + **Extra Tech** (if OR rooms > 3)

## Usage

Run the main script to generate the schedule:

```bash
python main.py
```

The script will:
1. Print the calculated requirements for each day.
2. Attempt to solve the schedule with the existing staff.
3. If no solution is found, it will incrementally add "Extra" staff until a valid schedule is generated.
4. Export the final schedule to `staff_schedule.xlsx`.

## Output

The generated Excel file includes:
- **Nurse Schedule**: Detailed daily assignments (Float, Lunch, or Room assignment).
- **Tech Schedule**: Daily assignments for technicians.
- **Summary**: Comparison of required vs. actual staffing and extra hires needed.
