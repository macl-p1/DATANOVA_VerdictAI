"""Shared test fixtures for building extraction payloads."""

# Every fact the rule engine relies on, scored above the default threshold.
# Tests that care about the confidence gate override individual entries.
CONFIDENT_FACTS = ("sections", "arrest_date", "release_date",
                   "first_time_offender", "other_pending_cases", "accused_name", "in_custody")


def confident_evidence(confidence: float = 0.95, **overrides):
    """Evidence block where everything is well-supported unless overridden.

    `confident_evidence(arrest_date=0.2)` lowers just that score;
    `confident_evidence(arrest_date=None)` removes the entry entirely.
    """
    block = {
        name: {"value": name, "source_quote": f"the document states {name}", "confidence": confidence}
        for name in CONFIDENT_FACTS
    }
    for name, score in overrides.items():
        if score is None:
            block.pop(name, None)
        else:
            block[name] = {"value": name, "source_quote": f"the document states {name}",
                           "confidence": score}
    return block
