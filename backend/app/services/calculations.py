from decimal import Decimal, ROUND_HALF_UP

from app.services.common import as_qty


def coefficient_output(input_qty: Decimal, coefficient: Decimal, factor: Decimal) -> Decimal:
    return as_qty(Decimal(str(input_qty)) * Decimal(str(coefficient)) * Decimal(str(factor)))


def deviation(real: Decimal, theoretical: Decimal) -> dict:
    real_q = as_qty(real)
    theoretical_q = as_qty(theoretical)
    difference = as_qty(real_q - theoretical_q)
    if theoretical_q == 0:
        return {
            "absolute_difference": difference,
            "percent_deviation": None,
            "percent_status": "NO_CALCULABLE",
            "review_required": real_q != 0,
        }
    percent = (difference / theoretical_q * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return {
        "absolute_difference": difference,
        "percent_deviation": percent,
        "percent_status": "CALCULADO",
        "review_required": False,
    }
