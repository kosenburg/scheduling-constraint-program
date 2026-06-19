from ortools.sat.python import cp_model

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
        header = "          " + " ".join([f"Day {d+1}" for d in days])
        print(header)
        for n in nurses:
            is_additional = n >= base_num_nurses
            nurse_label = f"Nurse {n+1:2}" if not is_additional else f"Extra {n-base_num_nurses+1:2}"
            nurse_name = f"{nurse_label} ({nurse_work_days[n]}d)"
            row = []
            actual_days = 0
            for d in days:
                if solver.Value(shifts[(n, d)]):
                    row.append("  X   ")
                    actual_days += 1
                else:
                    row.append("  -   ")
            print(f"{nurse_name}: {' '.join(row)} (Total: {actual_days})")
        
        print("\nVerification:")
        for d in days:
            count = sum(solver.Value(shifts[(n, d)]) for n in nurses)
            print(f"Day {d+1}: {count} nurses")
        
        print(f"\nFinal count of new nurses required: {additional_nurses_count}")
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
