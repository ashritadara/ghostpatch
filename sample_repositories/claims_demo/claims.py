"""Fictional claims eligibility. Synthetic demonstration only."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def evaluate_claim(payload):
    age = payload["age"]
    if isinstance(age, bool) or not isinstance(age, int) or age < 0:
        raise ValueError("age must be a nonnegative integer")
    try:
        amount = Decimal(str(payload["amount"]))
    except InvalidOperation:
        raise ValueError("invalid amount")
    if not amount.is_finite() or amount < 0:
        raise ValueError("amount must be finite and nonnegative")
    if payload.get("duplicate", False):
        return {"decision": "rejected", "reason": "duplicate", "payable": "0.00"}
    if age > 65:
        decision = "review" if amount > 500 else "approved"
        payable = format(amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), ".2f")
        return {"decision": decision, "reason": "eligible", "payable": payable}
    return {"decision": "rejected", "reason": "age_threshold", "payable": "0.00"}
