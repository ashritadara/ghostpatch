"""Fictional departmental expense reporting; all amounts are synthetic."""
from decimal import Decimal


def summarize(rows):
    totals = {}
    counts = {}
    for row in rows:
        department = row["department"]
        if department not in totals:
            totals[department] = 0
            counts[department] = 0
        totals[department] = totals[department] + Decimal(row["amount"])
        counts[department] = counts[department] + 1
    result = []
    for department in sorted(totals):
        result.append({"department": department,
                       "total": format(totals[department], ".2f"),
                       "count": counts[department]})
    return result
