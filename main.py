from ortools.sat.python import cp_model

def solve_nurse_scheduling():
    model = cp_model.CpModel()

    # Data
    num_nurses = 11
    num_days = 5
    nurses = range(num_nurses)
    days = range(num_days)

    # Nurse constraints: (number of nurses, days they work)
    # 8 nurses work 3 days
    # 2 nurses work 4 days
    # 1 nurse works 2 days
    nurse_work_days = [3] * 8 + [4] * 2 + [2] * 1
    
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

    # Constraint 2: Each nurse works exactly their specified number of days
    for n in nurses:
        model.Add(sum(shifts[(n, d)] for d in days) == nurse_work_days[n])

    # Solve
    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        print(f"Solution found:\n")
        header = "          " + " ".join([f"Day {d+1}" for d in days])
        print(header)
        for n in nurses:
            nurse_name = f"Nurse {n+1:2} ({nurse_work_days[n]}d)"
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
    else:
        print("no solution possible")

if __name__ == '__main__':
    solve_nurse_scheduling()
