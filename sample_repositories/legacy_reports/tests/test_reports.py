from decimal import InvalidOperation
import pytest
from reports import summarize


@pytest.mark.parametrize("rows,expected", [
    ([], []),
    ([{"department": "A", "amount": "1.25"}], [{"department": "A", "total": "1.25", "count": 1}]),
    ([{"department": "A", "amount": "0.10"}, {"department": "A", "amount": "0.20"}], [{"department": "A", "total": "0.30", "count": 2}]),
    ([{"department": "Z", "amount": "2"}, {"department": "A", "amount": "3"}], [{"department": "A", "total": "3.00", "count": 1}, {"department": "Z", "total": "2.00", "count": 1}]),
    ([{"department": "A", "amount": "5"}, {"department": "A", "amount": "-2.25"}], [{"department": "A", "total": "2.75", "count": 2}]),
    ([{"department": "", "amount": "0"}], [{"department": "", "total": "0.00", "count": 1}]),
    ([{"department": "0", "amount": "2.345"}], [{"department": "0", "total": "2.34", "count": 1}]),
    ([{"department": "Research", "amount": "2.355"}], [{"department": "Research", "total": "2.36", "count": 1}]),
])
def test_outputs(rows, expected):
    assert summarize(rows) == expected


def test_missing_department_is_not_silently_ignored():
    with pytest.raises(KeyError):
        summarize([{"amount": "1"}])


def test_invalid_amount_is_not_silently_ignored():
    with pytest.raises(InvalidOperation):
        summarize([{"department": "A", "amount": "broken"}])


def test_inputs_unchanged():
    rows = [{"department": "A", "amount": "1"}]
    summarize(rows)
    assert rows == [{"department": "A", "amount": "1"}]


def test_empty_department_is_distinct_from_named_department():
    result = summarize([{"department": "", "amount": "1"}, {"department": "A", "amount": "2"}])
    assert len(result) == 2
