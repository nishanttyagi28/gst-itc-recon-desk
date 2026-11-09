from decimal import Decimal

import pytest

from recon.rules import decide, load_config


def result(category, tax_diff="0.00"):
    return {"category": category, "invoice_no": "INV-001",
            "supplier_gstin": "27AAECS1234F1Z5",
            "tax_diff": Decimal(tax_diff)}


@pytest.fixture
def config():
    return load_config()


def test_matched_is_allowed(config):
    decision = decide(result("MATCHED"), config)
    assert decision["decision"] == "ALLOW"


def test_small_tax_difference_goes_to_review(config):
    decision = decide(result("AMOUNT_MISMATCH", tax_diff="3.20"), config)
    assert decision == {"decision": "REVIEW",
                        "reason": "Tax differs by 3.20, within the 10.00 review limit"}


def test_large_tax_difference_is_blocked(config):
    decision = decide(result("AMOUNT_MISMATCH", tax_diff="25.00"), config)
    assert decision == {"decision": "BLOCK",
                        "reason": "Tax differs by 25.00, above the 10.00 review limit"}


def test_missing_in_2b_is_blocked(config):
    decision = decide(result("MISSING_IN_2B"), config)
    assert decision["decision"] == "BLOCK"


def test_missing_in_books_goes_to_review(config):
    decision = decide(result("MISSING_IN_BOOKS"), config)
    assert decision["decision"] == "REVIEW"


def test_gstin_mismatch_goes_to_review(config):
    decision = decide(result("GSTIN_MISMATCH"), config)
    assert decision["decision"] == "REVIEW"


def test_threshold_is_taken_from_config():
    # an accountant raising the limit turns a large diff into REVIEW
    config = {"review_max_tax_diff": "100.00",
              "actions": {"AMOUNT_MISMATCH": "threshold"}}
    decision = decide(result("AMOUNT_MISMATCH", tax_diff="25.00"), config)
    assert decision["decision"] == "REVIEW"


def test_accountant_can_block_missing_in_books():
    # the config drives the action for a category
    config = {"review_max_tax_diff": "10.00",
              "actions": {"MISSING_IN_BOOKS": "BLOCK"}}
    decision = decide(result("MISSING_IN_BOOKS"), config)
    assert decision["decision"] == "BLOCK"


def test_unknown_action_raises():
    config = {"review_max_tax_diff": "10.00", "actions": {"MATCHED": "MAYBE"}}
    with pytest.raises(ValueError, match="unknown action"):
        decide(result("MATCHED"), config)
