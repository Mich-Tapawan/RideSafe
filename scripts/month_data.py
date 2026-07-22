from scripts.repository import get_month_totals


def generate_month_list(year, month):
    totals = get_month_totals(year)
    monthly_totals = totals["monthly_totals"]
    yearly_total = totals["yearly_total"]

    month_total_offenses = int(monthly_totals.get(month, 0))

    if yearly_total > 0:
        percentage = (month_total_offenses / yearly_total) * 100
    else:
        percentage = 0

    return {
        "totalAccidents": month_total_offenses,
        "percentage": round(percentage, 2),
    }
