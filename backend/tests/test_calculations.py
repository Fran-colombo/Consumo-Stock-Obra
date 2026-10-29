from decimal import Decimal

from app.services.calculations import coefficient_output, deviation


def test_coefficient_matches_the_illustrative_example():
    assert coefficient_output(Decimal("10"), Decimal("6"), Decimal("1")) == Decimal("60.0000")


def test_deviation_when_real_is_lower():
    result = deviation(Decimal("55"), Decimal("60"))
    assert result["absolute_difference"] == Decimal("-5.0000")
    assert result["percent_deviation"] == Decimal("-8.33")
    assert result["percent_status"] == "CALCULADO"
    assert result["review_required"] is False


def test_deviation_when_theoretical_is_zero():
    result = deviation(Decimal("4"), Decimal("0"))
    assert result["percent_deviation"] is None
    assert result["percent_status"] == "NO_CALCULABLE"
    assert result["review_required"] is True


def test_positive_deviation_is_only_a_difference():
    result = deviation(Decimal("690"), Decimal("600"))
    assert result["absolute_difference"] == Decimal("90.0000")
    assert result["percent_deviation"] == Decimal("15.00")
