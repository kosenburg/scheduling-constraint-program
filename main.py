from ortools.sat.python import cp_model

import pandas as pd

def export_to_excel(schedule_rows, summary_rows, filename="nurse_schedule.xlsx"):
    """Exports data to a standard Excel file using pandas."""
    # Create DataFrames
    df_schedule = pd.DataFrame(schedule_rows[1:], columns=schedule_rows[0])
    df_summary = pd.DataFrame(summary_rows[1:], columns=summary_rows[0])
    
    # Export to Excel with multiple sheets
    with pd.ExcelWriter(filename, engine='openpyxl') as writer:
        df_schedule.to_excel(writer, sheet_name='Schedule', index=False)
        df_summary.to_excel(writer, sheet_name='Summary', index=False)
        
    print(f"Results exported to {filename}")

def solve_nurse_scheduling(additional_nurses_count=0):
    model = cp_model.CpModel()

    # Data
    base_num_nurses = 11
    num_days = 5
    
    # Base Nurse constraints: (number of nurses, days they work)
    # 8 nurses work 3 days
    # 2 nurses work 4 days
    # 1 nurse works 2 days
    nurse_work_days = [3] * 8 + [4] * 2 + [2] * 1
    
    # Add additional nurses who work UP TO 4 days each
    if additional_nurses_count > 0:
        for i in range(additional_nurses_count):
            nurse_work_days.append(4)
    
    num_nurses = len(nurse_work_days)
    nurses = range(num_nurses)
    days = range(num_days)
    
    # Requirement: 8 nurses per day
    nurses_per_day = 8

    # Variables: shifts[n, d] is true if nurse n works on day d
    shifts = {}
    for n in nurses:
        for d in days:
            shifts[(n, d)] = model.NewBoolVar(f'shift_n{n}_d{d}')

    # Constraint 1: Each day must have exactly 8 nurses
    for d in days:
        model.Add(sum(shifts[(n, d)] for n in nurses) == nurses_per_day)

    # Constraint 2: Each nurse works their specified number of days
    for n in nurses:
        if n < base_num_nurses:
            # Original nurses MUST work exactly their days
            model.Add(sum(shifts[(n, d)] for d in days) == nurse_work_days[n])
        else:
            # Additional nurses can work UP TO 4 days
            model.Add(sum(shifts[(n, d)] for d in days) <= 4)
            # Ensure additional nurses are actually used (at least 1 day)
            # otherwise adding them is meaningless
            model.Add(sum(shifts[(n, d)] for d in days) >= 1)

    # Solve
    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        print(f"Solution found with {additional_nurses_count} additional nurses:\n")
        
        # Prepare data for export
        schedule_data = []
        header = ["Nurse", "Day 1", "Day 2", "Day 3", "Day 4", "Day 5", "Total"]
        schedule_data.append(header)
        
        print("          " + " ".join([f"Day {d+1}" for d in days]))
        for n in nurses:
            is_additional = n >= base_num_nurses
            nurse_label = f"Nurse {n+1}" if not is_additional else f"Extra {n-base_num_nurses+1}"
            nurse_display = f"{nurse_label} ({nurse_work_days[n]}d)"
            
            row_display = []
            excel_row = [nurse_display]
            actual_days = 0
            for d in days:
                if solver.Value(shifts[(n, d)]):
                    row_display.append("  X   ")
                    excel_row.append("X")
                    actual_days += 1
                else:
                    row_display.append("  -   ")
                    excel_row.append("-")
            excel_row.append(actual_days)
            schedule_data.append(excel_row)
            print(f"{nurse_display:20}: {' '.join(row_display)} (Total: {actual_days})")
        
        print("\nVerification:")
        summary_data = [["Item", "Value"]]
        for d in days:
            count = sum(solver.Value(shifts[(n, d)]) for n in nurses)
            print(f"Day {d+1}: {count} nurses")
            summary_data.append([f"Day {d+1} Staffing", count])
        
        print(f"\nFinal count of new nurses required: {additional_nurses_count}")
        summary_data.append(["Additional Nurses Added", additional_nurses_count])
        
        export_to_excel(schedule_data, summary_data)
        return True
    else:
        return False

if __name__ == '__main__':
    added = 0
    while not solve_nurse_scheduling(added):
        print(f"Attempt with {added} additional nurses failed...")
        added += 1
        # Safety break to avoid infinite loop if something is logically wrong
        if added > 20:
            print("no solution possible")
            break
