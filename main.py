"""
Nurse and Tech Scheduling System.
Uses CP-SAT solver to assign staff to shifts based on daily requirements.
"""
import json
import sys
from ortools.sat.python import cp_model
import pandas as pd


def export_to_excel(nurse_data, tech_data, requirements_df, filename="staff_schedule.xlsx"):
    """Exports nurse and tech data to an Excel file with separate sheets."""
    with pd.ExcelWriter(filename, engine='openpyxl') as writer:
        # Requirements Sheet
        requirements_df.to_excel(writer, sheet_name='Requirements', index=False)

        # Nurses Sheet
        nurse_data['schedule'].to_excel(writer, sheet_name='Nurse Schedule', index=False)

        # Techs Sheet
        tech_data['schedule'].to_excel(writer, sheet_name='Tech Schedule', index=False)

        # Summary Sheet
        # Nurse Comparison
        nurse_data['comparison'].to_excel(writer, sheet_name='Summary', index=False, startrow=0)
        start_row = len(nurse_data['comparison']) + 2

        # Tech Comparison
        tech_data['comparison'].to_excel(
            writer, sheet_name='Summary', index=False, startrow=start_row
        )
        start_row += len(tech_data['comparison']) + 2

        # Extra Hires (Combined)
        extra_hires = pd.concat(
            [nurse_data['extra_hires'], tech_data['extra_hires']], ignore_index=True
        )
        extra_hires.to_excel(writer, sheet_name='Summary', index=False, startrow=start_row)
        start_row += len(extra_hires) + 2

        # Daily Staffing (Combined)
        nurse_summary = nurse_data['summary'].copy()
        nurse_summary.columns = ["Day", "Req Nurses", "Act Nurses"]
        tech_summary = tech_data['summary'].copy()
        tech_summary.columns = ["Day", "Req Techs", "Act Techs"]

        combined_summary = pd.merge(nurse_summary, tech_summary, on="Day")
        combined_summary.to_excel(writer, sheet_name='Summary', index=False, startrow=start_row)

    print(f"Results exported to {filename}")


def create_schedule_model(required_per_day, base_staff_data, staff_type, additional_count):
    """Creates the CP-SAT model for scheduling."""
    model = cp_model.CpModel()

    # Base Staff information
    work_days = [staff["required_days"] for staff in base_staff_data]
    names = [f"{staff['first_name']} {staff['last_name']}" for staff in base_staff_data]
    base_num = len(base_staff_data)

    # Add additional staff
    if additional_count > 0:
        for i in range(additional_count):
            work_days.append(4)
            names.append(f"Extra {staff_type} {i + 1}")

    staff_range = range(len(work_days))
    days = range(len(required_per_day))

    shifts = {}
    for s in staff_range:
        for d in days:
            shifts[(s, d)] = model.NewBoolVar(f'shift_s{s}_d{d}')

    # Constraint 1: Daily requirement
    for d in days:
        model.Add(sum(shifts[(s, d)] for s in staff_range) == required_per_day[d])

    # Constraint 2: Work days per staff
    for s in staff_range:
        if s < base_num:
            model.Add(sum(shifts[(s, d)] for d in days) == work_days[s])
        else:
            model.Add(sum(shifts[(s, d)] for d in days) <= 4)
            model.Add(sum(shifts[(s, d)] for d in days) >= 1)

    return model, shifts, names, work_days, base_num


def get_nurse_role(s_idx, d_idx, solver, shifts, staff_range):
    """Calculates the specific role for a nurse on a given day."""
    day_staff = [i for i in staff_range if solver.Value(shifts[(i, d_idx)])]
    pos = day_staff.index(s_idx)
    if pos == 0:
        return "Float"
    if pos == 1:
        return "Lunch"
    return f"Room {((pos - 2) // 2) + 1}"


def get_staff_stats(s_idx, solver_data, days):
    """Extracts stats for a single staff member."""
    solver = solver_data["solver"]
    shifts = solver_data["shifts"]
    names = solver_data["names"]
    work_days = solver_data["work_days"]
    base_num = solver_data["base_num"]

    is_additional = s_idx >= base_num
    st_type = "Base" if not is_additional else "Extra"
    name = names[s_idx]
    actual_days = sum(solver.Value(shifts[(s_idx, d_idx)]) for d_idx in days)
    required = work_days[s_idx] if not is_additional else "1-4 (Max 4)"
    return st_type, name, actual_days, required


def process_solver_results(solver_data):
    """Processes the results from the CP-SAT solver into DataFrames."""
    solver = solver_data["solver"]
    shifts = solver_data["shifts"]
    staff_type = solver_data["staff_type"]
    required_per_day = solver_data["required_per_day"]
    base_num = solver_data["base_num"]

    staff_range = range(len(solver_data["names"]))
    days = range(len(required_per_day))

    # Prepare DataFrames
    schedule_cols = ["Type", "Name"] + [f"Day {d + 1}" for d in days] + ["Total"]
    schedule_rows = []
    comparison_rows = []
    extra_hires_rows = []

    for s_idx in staff_range:
        stats = get_staff_stats(s_idx, solver_data, days)
        st_type, name, actual_days, required = stats

        row = [st_type, name]
        for d_idx in days:
            if solver.Value(shifts[(s_idx, d_idx)]):
                if staff_type == "Nurse":
                    row.append(get_nurse_role(s_idx, d_idx, solver, shifts, staff_range))
                else:
                    row.append("X")
            else:
                row.append("-")
        row.append(actual_days)
        schedule_rows.append(row)
        comparison_rows.append([staff_type, st_type, name, required, actual_days])
        if s_idx >= base_num:
            extra_hires_rows.append([name, actual_days])

    summary_rows = []
    for d_idx in days:
        count = sum(solver.Value(shifts[(s_idx, d_idx)]) for s_idx in staff_range)
        summary_rows.append([f"Day {d_idx + 1}", required_per_day[d_idx], count])

    return {
        "schedule": pd.DataFrame(schedule_rows, columns=schedule_cols),
        "comparison": pd.DataFrame(comparison_rows,
                                   columns=["Staff Type", "Type", "Name",
                                            "Req Days", "Sched Days"]),
        "extra_hires": pd.DataFrame(extra_hires_rows,
                                    columns=[f"Ex {staff_type} Name", "Sched Days"]),
        "summary": pd.DataFrame(summary_rows, columns=["Day", "Required", "Actual"]),
        "additional_count": solver_data["additional_count"]
    }


def solve_scheduling(staff_type, required_per_day, base_staff_data, additional_count=0):
    """
    Main function to solve the scheduling problem for a given staff type.
    """
    model, shifts, names, work_days, base_num = create_schedule_model(
        required_per_day, base_staff_data, staff_type, additional_count
    )

    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return process_solver_results({
            "solver": solver,
            "shifts": shifts,
            "names": names,
            "work_days": work_days,
            "base_num": base_num,
            "staff_type": staff_type,
            "required_per_day": required_per_day,
            "additional_count": additional_count
        })
    return None


def calculate_requirements(schedule_params):
    """Calculates daily nurse and tech requirements."""
    nurse_requirements = []
    tech_requirements = []

    for day_config in schedule_params["days"]:
        # Calculate Nurse requirements per day
        # Formula: (OR rooms * 2) + float nurses + lunch relief nurses
        daily_nurse_req = (day_config["num_or_rooms"] * 2) + \
                          day_config["num_float_nurses"] + \
                          day_config["num_lunch_relief_nurses"]
        nurse_requirements.append(daily_nurse_req)

        num_or_rooms = day_config["num_or_rooms"]
        # Updated constraint: always want a dedicated floating tech (1)
        # and no additional constraint on float tech even if more than 3 rooms.
        daily_tech_req = (num_or_rooms * 1) + \
                         (day_config["num_scope_rooms"] * 2) + 1
        tech_requirements.append(daily_tech_req)
    return nurse_requirements, tech_requirements


def main():
    """Main execution function."""
    try:
        with open('staff.json', 'r', encoding='utf-8') as f:
            staff_data = json.load(f)
        with open('schedule-parameters.json', 'r', encoding='utf-8') as f:
            schedule_params = json.load(f)
    except FileNotFoundError as e:
        print(f"Error: {e.filename} not found.")
        sys.exit(1)

    # Calculate requirements per day from schedule-parameters.json
    nurse_requirements, tech_requirements = calculate_requirements(schedule_params)

    # Solve for Nurses
    nurse_added = 0
    nurse_results = None
    while nurse_added <= 20:
        nurse_results = solve_scheduling("Nurse", nurse_requirements, staff_data["nurses"],
                                         nurse_added)
        if nurse_results:
            break
        nurse_added += 1

    if not nurse_results:
        print("no solution possible for nurses")
        sys.exit(1)

    # Solve for Techs
    tech_added = 0
    tech_results = None
    while tech_added <= 20:
        tech_results = solve_scheduling("Tech", tech_requirements, staff_data["techs"], tech_added)
        if tech_results:
            break
        tech_added += 1

    if not tech_results:
        print("no solution possible for techs")
        sys.exit(1)

    # Display requirements used
    print("Calculated Daily Requirements:")
    requirements_summary_df = pd.DataFrame({
        "Day": [f"Day {i + 1}" for i in range(len(nurse_requirements))],
        "OR Rooms": [d["num_or_rooms"] for d in schedule_params["days"]],
        "Scope Rooms": [d["num_scope_rooms"] for d in schedule_params["days"]],
        "Nurse Req": nurse_requirements,
        "Tech Req": tech_requirements
    })
    print(requirements_summary_df.to_string(index=False))
    print("")

    # Display results
    print(f"Nurse Solution found with {nurse_added} extra nurses.")
    print(nurse_results["schedule"].to_string(index=False))
    print(f"\nTech Solution found with {tech_added} extra techs.")
    print(tech_results["schedule"].to_string(index=False))

    print("\nStaff Work Comparison:")
    print(nurse_results["comparison"].to_string(index=False))
    print(tech_results["comparison"].to_string(index=False))

    export_to_excel(nurse_results, tech_results, requirements_summary_df)


if __name__ == '__main__':
    main()
