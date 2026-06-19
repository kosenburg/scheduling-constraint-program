from ortools.sat.python import cp_model

import pandas as pd

def export_to_excel(schedule_df, comparison_df, extra_hires_df, summary_df, filename="nurse_schedule.xlsx"):
    """Exports data to a standard Excel file using pandas."""
    # Export to Excel with multiple sheets
    with pd.ExcelWriter(filename, engine='openpyxl') as writer:
        schedule_df.to_excel(writer, sheet_name='Schedule', index=False)
        
        # Summary sheet with multiple tables
        comparison_df.to_excel(writer, sheet_name='Summary', index=False, startrow=0)
        
        # Add Extra Hires table if it exists
        start_row = len(comparison_df) + 3
        extra_hires_df.to_excel(writer, sheet_name='Summary', index=False, startrow=start_row)
        
        # Add Daily Staffing summary
        start_row += len(extra_hires_df) + 3
        summary_df.to_excel(writer, sheet_name='Summary', index=False, startrow=start_row)
        
    print(f"Results exported to {filename}")

def solve_nurse_scheduling(nurses_per_day_list, additional_nurses_count=0):
    model = cp_model.CpModel()

    # Data
    base_num_nurses = 11
    num_days = len(nurses_per_day_list)
    
    # Base Nurse constraints: (number of nurses, days they work)
    # 8 nurses work 3 days
    # 2 nurses work 4 days
    # 1 nurse works 2 days
    base_nurse_work_days = [3] * 8 + [4] * 2 + [2] * 1
    nurse_work_days = list(base_nurse_work_days)
    
    # Add additional nurses who work UP TO 4 days each
    if additional_nurses_count > 0:
        for i in range(additional_nurses_count):
            nurse_work_days.append(4)
    
    num_nurses = len(nurse_work_days)
    nurses = range(num_nurses)
    days = range(num_days)
    
    # Variables: shifts[n, d] is true if nurse n works on day d
    shifts = {}
    for n in nurses:
        for d in days:
            shifts[(n, d)] = model.NewBoolVar(f'shift_n{n}_d{d}')

    # Constraint 1: Each day must have the required number of nurses
    for d in days:
        model.Add(sum(shifts[(n, d)] for n in nurses) == nurses_per_day_list[d])

    # Constraint 2: Each nurse works their specified number of days
    for n in nurses:
        if n < base_num_nurses:
            # Original nurses MUST work exactly their days
            model.Add(sum(shifts[(n, d)] for d in days) == nurse_work_days[n])
        else:
            # Additional nurses can work UP TO 4 days
            model.Add(sum(shifts[(n, d)] for d in days) <= 4)
            # Ensure additional nurses are actually used (at least 1 day)
            model.Add(sum(shifts[(n, d)] for d in days) >= 1)

    # Solve
    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        print(f"Solution found with {additional_nurses_count} additional nurses:\n")
        
        # 1. Prepare Schedule DataFrame
        schedule_cols = ["Nurse Type", "Nurse ID"] + [f"Day {d+1}" for d in days] + ["Total Scheduled"]
        schedule_rows = []
        
        # 2. Prepare Comparison DataFrame
        comparison_rows = []
        
        # 3. Prepare Extra Hires DataFrame
        extra_hires_rows = []
        
        for n in nurses:
            is_additional = n >= base_num_nurses
            nurse_type = "Base" if not is_additional else "Extra"
            nurse_id = n + 1 if not is_additional else n - base_num_nurses + 1
            
            actual_days = sum(solver.Value(shifts[(n, d)]) for d in days)
            required_days = nurse_work_days[n] if not is_additional else f"1-4 (Max 4)"
            
            # Schedule row
            row = [nurse_type, nurse_id]
            for d in days:
                row.append("X" if solver.Value(shifts[(n, d)]) else "-")
            row.append(actual_days)
            schedule_rows.append(row)
            
            # Comparison row
            comparison_rows.append([nurse_type, nurse_id, required_days, actual_days])
            
            # Extra Hire row
            if is_additional:
                extra_hires_rows.append([nurse_id, actual_days])

        df_schedule = pd.DataFrame(schedule_rows, columns=schedule_cols)
        df_comparison = pd.DataFrame(comparison_rows, columns=["Nurse Type", "Nurse ID", "Required Days", "Scheduled Days"])
        df_extra_hires = pd.DataFrame(extra_hires_rows, columns=["Extra Nurse ID", "Scheduled Days"])
        
        # 4. Daily Summary DataFrame
        summary_rows = []
        for d in days:
            count = sum(solver.Value(shifts[(n, d)]) for n in nurses)
            summary_rows.append([f"Day {d+1}", nurses_per_day_list[d], count])
        df_summary = pd.DataFrame(summary_rows, columns=["Day", "Required Staffing", "Actual Staffing"])

        # Console Output
        print("Schedule:")
        print(df_schedule.to_string(index=False))
        print("\nNurse Work Comparison:")
        print(df_comparison.to_string(index=False))
        print("\nExtra Hires Summary:")
        if not df_extra_hires.empty:
            print(df_extra_hires.to_string(index=False))
        else:
            print("No extra hires required.")
        print("\nDaily Staffing Summary:")
        print(df_summary.to_string(index=False))
        print(f"\nTotal extra nurses required: {additional_nurses_count}")
        
        export_to_excel(df_schedule, df_comparison, df_extra_hires, df_summary)
        return True
    else:
        return False

if __name__ == '__main__':
    # Example requirement: Day 1 needs 6 nurses, other 4 days need 8 nurses
    requirements = [6, 8, 8, 8, 8]
    
    added = 0
    while not solve_nurse_scheduling(requirements, added):
        print(f"Attempt with {added} additional nurses failed...")
        added += 1
        # Safety break to avoid infinite loop if something is logically wrong
        if added > 20:
            print("no solution possible")
            break
