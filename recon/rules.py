"""Turn match results from recon.matcher into ITC decisions."""
from decimal import Decimal

import yaml

DEFAULT_CONFIG_PATH = "config/itc_rules.yaml"


def load_config(path=DEFAULT_CONFIG_PATH):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _format(amount):
    amount = Decimal(amount)
    return str(amount.quantize(Decimal("0.01")))


def decide(result, config):
    """Return {"decision": ALLOW/REVIEW/BLOCK, "reason": str} for one match result."""
    category = result["category"]
    action = config["actions"][category]

    if action == "threshold":
        tax_diff = abs(result.get("tax_diff", Decimal("0")))
        limit = Decimal(str(config["review_max_tax_diff"]))
        if tax_diff <= limit:
            return {
                "decision": "REVIEW",
                "reason": f"Tax differs by {_format(tax_diff)}, within the "
                          f"{_format(limit)} review limit",
            }
        return {
            "decision": "BLOCK",
            "reason": f"Tax differs by {_format(tax_diff)}, above the "
                      f"{_format(limit)} review limit",
        }

    if action == "ALLOW":
        return {"decision": "ALLOW", "reason": "Invoice matches GSTR-2B"}
    if action == "REVIEW":
        return {"decision": "REVIEW", "reason": f"{category}: check with supplier or books"}
    if action == "BLOCK":
        return {"decision": "BLOCK", "reason": f"{category}: no ITC without a matching 2B record"}
    raise ValueError(f"unknown action {action!r} for category {category!r}")
