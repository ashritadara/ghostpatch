"""Legacy tests are intentionally missing the age-65 policy boundary."""
import pytest
from claims import evaluate_claim


def test_older_applicant():
    assert evaluate_claim({"age": 70, "amount": "10"}) == {"decision": "approved", "reason": "eligible", "payable": "10.00"}


def test_younger_applicant():
    assert evaluate_claim({"age": 60, "amount": "10"})["decision"] == "rejected"


def test_duplicate():
    assert evaluate_claim({"age": 70, "amount": "10", "duplicate": True})["reason"] == "duplicate"


def test_rounding():
    assert evaluate_claim({"age": 70, "amount": "2.345"})["payable"] == "2.35"


def test_review():
    assert evaluate_claim({"age": 70, "amount": "501"})["decision"] == "review"


def test_negative_amount():
    with pytest.raises(ValueError):
        evaluate_claim({"age": 70, "amount": "-1"})
