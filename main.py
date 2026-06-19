from ortools.sat.python import cp_model
import pandas as pd
import json

def export_to_excel(nurse_data, tech_data, req_df, filename="staff_schedule.xlsx"):
    """Exports nurse and tech data to an Excel file with separate sheets."""
    with pd.ExcelWriter(filename, engine='openpyxl') as writer:
        # Requirements Sheet
        req_df.to_excel(writer, sheet_name='Requirements', index=False)
        
        # Nurses Sheet
        nurse_data['schedule'].to_excel(writer, sheet_name='Nurse Schedule', index=False)
        
        # Techs Sheet
        tech_data['schedule'].to_excel(writer, sheet_name='Tech Schedule', index=False)
        
        # Summary Sheet
        # Nurse Comparison
        nurse_data['comparison'].to_excel(writer, sheet_name='Summary', index=False, startrow=0)
        start_row = len(nurse_data['comparison']) + 2
        
        # Tech Comparison
        tech_data['comparison'].to_excel(writer, sheet_name='Summary', index=False, startrow=start_row)
        start_row += len(tech_data['comparison']) + 2
        
        # Extra Hires (Combined)
        extra_hires = pd.concat([nurse_data['extra_hires'], tech_data['extra_hires']], ignore_index=True)
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

def solve_scheduling(staff_type, required_per_day, base_staff_data, additional_count=0):
    model = cp_model.CpModel()
    num_days = len(required_per_day)
    
    # Base Staff information
    work_days = [staff["required_days"] for staff in base_staff_data]
    names = [f"{staff['first_name']} {staff['last_name']}" for staff in base_staff_data]
    base_num = len(base_staff_data)
    
    # Add additional staff
    if additional_count > 0:
        for i in range(additional_count):
            work_days.append(4)
            names.append(f"Extra {staff_type} {i+1}")
    
    num_staff = len(work_days)
    staff_range = range(num_staff)
    days = range(num_days)
    
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

    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        # Prepare DataFrames
        schedule_cols = ["Type", "Name"] + [f"Day {d+1}" for d in days] + ["Total"]
        schedule_rows = []
        comparison_rows = []
        extra_hires_rows = []
        
        for s in staff_range:
            is_additional = s >= base_num
            st_type = "Base" if not is_additional else "Extra"
            name = names[s]
            actual_days = sum(solver.Value(shifts[(s, d)]) for d in days)
            required = work_days[s] if not is_additional else "1-4 (Max 4)"
            
            row = [st_type, name]
            for d in days:
                if solver.Value(shifts[(s, d)]):
                    if staff_type == "Nurse":
                        day_staff = [i for i in staff_range if solver.Value(shifts[(i, d)])]
                        pos = day_staff.index(s)
                        if pos == 0: role = "Float"
                        elif pos == 1: role = "Lunch"
                        else: role = f"Room {((pos - 2) // 2) + 1}"
                        row.append(role)
                    else:
                        row.append("X")
                else:
                    row.append("-")
            row.append(actual_days)
            schedule_rows.append(row)
            comparison_rows.append([staff_type, st_type, name, required, actual_days])
            if is_additional:
                extra_hires_rows.append([name, actual_days])

        summary_rows = []
        for d in days:
            count = sum(solver.Value(shifts[(s, d)]) for s in staff_range)
            summary_rows.append([f"Day {d+1}", required_per_day[d], count])
            
        return {
            "schedule": pd.DataFrame(schedule_rows, columns=schedule_cols),
            "comparison": pd.DataFrame(comparison_rows, columns=["Staff Type", "Type", "Name", "Required Days", "Scheduled Days"]),
            "extra_hires": pd.DataFrame(extra_hires_rows, columns=[f"Extra {staff_type} Name", "Scheduled Days"]),
            "summary": pd.DataFrame(summary_rows, columns=["Day", "Required", "Actual"]),
            "additional_count": additional_count
        }
    return None

if __name__ == '__main__':
    try:
        with open('staff.json', 'r') as f:
            staff_data = json.load(f)
        with open('schedule-parameters.json', 'r') as f:
            schedule_params = json.load(f)
    except FileNotFoundError as e:
        print(f"Error: {e.filename} not found.")
        exit(1)

    # Calculate requirements per day from schedule-parameters.json
    nurse_requirements = []
    tech_requirements = []
    
    for day_config in schedule_params["days"]:
        # Calculate Nurse requirements per day
        # Formula: (OR rooms * 2) + float nurses + lunch relief nurses
        daily_nurse_req = (day_config["num_or_rooms"] * 2) + \
                          day_config["num_float_nurses"] + \
                          day_config["num_lunch_relief_nurses"]
        nurse_requirements.append(daily_nurse_req)
        # Calculate Tech requirements per day
        # Formula: (OR rooms * 1) + (scope rooms * 2) + (1 if OR rooms > 3 else 0)
        extra_tech = 1 if day_config["num_or_rooms"] > 3 else 0
        daily_tech_req = (day_config["num_or_rooms"] * 1) + \
                         (day_config["num_scope_rooms"] * 2) + \
                         extra_tech
        tech_requirements.append(daily_tech_req)

    # Solve for Nurses
    nurse_added = 0
    nurse_results = None
    while nurse_added <= 20:
        nurse_results = solve_scheduling("Nurse", nurse_requirements, staff_data["nurses"], nurse_added)
        if nurse_results: break
        nurse_added += 1
    
    if not nurse_results:
        print("no solution possible for nurses")
        exit(1)

    # Solve for Techs
    tech_added = 0
    tech_results = None
    while tech_added <= 20:
        tech_results = solve_scheduling("Tech", tech_requirements, staff_data["techs"], tech_added)
        if tech_results: break
        tech_added += 1
        
    if not tech_results:
        print("no solution possible for techs")
        exit(1)

    # Display requirements used
    print("Calculated Daily Requirements:")
    req_df = pd.DataFrame({
        "Day": [f"Day {i+1}" for i in range(len(nurse_requirements))],
        "OR Rooms": [d["num_or_rooms"] for d in schedule_params["days"]],
        "Scope Rooms": [d["num_scope_rooms"] for d in schedule_params["days"]],
        "Nurse Req": nurse_requirements,
        "Tech Req": tech_requirements
    })
    print(req_df.to_string(index=False))
    print("")

    # Display results
    print(f"Nurse Solution found with {nurse_added} extra nurses.")
    print(nurse_results["schedule"].to_string(index=False))
    print(f"\nTech Solution found with {tech_added} extra techs.")
    print(tech_results["schedule"].to_string(index=False))
    
    print("\nStaff Work Comparison:")
    print(nurse_results["comparison"].to_string(index=False))
    print(tech_results["comparison"].to_string(index=False))
    
    export_to_excel(nurse_results, tech_results, req_df)
