"""Fixed theme taxonomy for Groww review classification (Phase 3.2).

At most 5 themes. Each theme has a strict description and assignment
criteria so identical issues receive consistent labels across batches.

Used by both the Gemini classification prompt (n8n) and the deterministic
JavaScript validation node (n8n Code node).
"""

from __future__ import annotations

# Theme taxonomy: id -> {name, description, assignment_criteria, examples, counter_examples}
THEME_TAXONOMY = {
    "T1": {
        "name": "High Fees",
        "description": "Complaints about charges, brokerage, AMC fees, transaction costs, "
                       "hidden fees, or unexpected deductions. Distinguishes brokerage "
                       "complaints (explicitly about brokerage) from unspecified charges "
                       "(general fee complaints without specifying brokerage).",
        "assignment_criteria": (
            "Assign when the review mentions money being charged, deducted, or taken, "
            "including brokerage, AMC, transaction fees, DP charges, or hidden costs. "
            "If the review explicitly says 'brokerage', tag as fee-brokerage. "
            "If it mentions charges/fees without saying 'brokerage', tag as fee-other. "
            "A review can carry both fee-brokerage and fee-other if it mentions both."
        ),
        "examples": [
            "Charged rs2000/- for SIP",
            "brokerage 20 per order is too high",
            "High fees and hidden charges",
            "Unexpected deduction from account",
            "Groww Brokerage is eating my profits"
        ],
        "counter_examples": [
            "The app is slow",
            "Good customer support",
            "Please add SWP feature"
        ],
        "subtypes": ["fee-brokerage", "fee-other"],
    },
    "T2": {
        "name": "Technical Issues",
        "description": "App crashes, bugs, glitches, slow performance, login problems, "
                       "feature not working, UI/UX problems, update issues.",
        "assignment_criteria": (
            "Assign when the review reports the app not working, crashing, being slow, "
            "login/authentication problems, buttons/features not responding, or update-related "
            "breakage. Does not include complaints about fees or customer support quality."
        ),
        "examples": [
            "App crashes every time I open it",
            "Login not working after update",
            "Scrolling is very laggy",
            "Chart IQ not loading",
            "App freezes during trade execution"
        ],
        "counter_examples": [
            "Charged too much brokerage",
            "Support team is rude",
            "Add mutual fund SIP"
        ],
        "subtypes": None,
    },
    "T3": {
        "name": "Poor Customer Support",
        "description": "Complaints about customer service quality, unhelpful support, "
                       "slow response, unresolved tickets, rude behavior, or ticket ID issues.",
        "assignment_criteria": (
            "Assign when the review complains about support team behavior, response time, "
            "unresolved complaint/ticket IDs, or inability to reach support. Mentions of "
            "ticket numbers or complaint IDs in the context of support (not just as reference) "
            "fall here."
        ),
        "examples": [
            "Support team is rude and unhelpful",
            "Ticket not resolved for 2 weeks",
            "Cannot reach customer care",
            "Support ignored my complaint",
            "Poor customer service experience"
        ],
        "counter_examples": [
            "App is slow",
            "Charged hidden fees",
            "Add more mutual funds"
        ],
        "subtypes": None,
    },
    "T4": {
        "name": "Feature Requests",
        "description": "Requests for new features, missing functionality, or enhancements "
                       "to existing features (e.g., SWP, STP, chart tools, more mutual funds).",
        "assignment_criteria": (
            "Assign when the review asks for something the app doesn't currently do, or "
            "requests an enhancement to an existing feature. Does not include complaints "
            "about something that is broken (that's Technical Issues)."
        ),
        "examples": [
            "Please add SWP feature",
            "Add more mutual fund options",
            "Need chart IQ improvements",
            "Please add IPO investment",
            "Add dark mode to app"
        ],
        "counter_examples": [
            "Chart IQ not loading",
            "Charged brokerage fees",
            "Support is rude"
        ],
        "subtypes": None,
    },
    "T5": {
        "name": "General Satisfaction",
        "description": "Positive feedback, praise, thank you, good experience, or general "
                       "appreciation without a specific complaint or request.",
        "assignment_criteria": (
            "Assign when the review is purely positive with no complaint, fee issue, "
            "technical problem, support complaint, or feature request. Short praise like "
            "'good', 'nice', 'excellent' falls here."
        ),
        "examples": [
            "Good app",
            "Nice experience",
            "Thank you Groww",
            "Excellent broker",
            "Very happy with service"
        ],
        "counter_examples": [
            "App crashes",
            "Charged hidden fees",
            "Support is rude",
            "Please add SWP"
        ],
        "subtypes": None,
    },
}

# Valid sentiment values
VALID_SENTIMENTS = {"positive", "negative", "neutral"}

# Valid fee topic values (for fee-related reviews)
VALID_FEE_TOPICS = {"fee-brokerage", "fee-other", "none"}

# All valid theme IDs
VALID_THEME_IDS = set(THEME_TAXONOMY.keys())

# Maximum themes per review
MAX_THEMES_PER_REVIEW = 2

# Default batch configuration
BATCH_SIZE = 25
MAX_BATCHES_FOR_INITIAL_TEST = 4  # 4 x 25 = 100 reviews
MAX_REVIEWS_FOR_INITIAL_TEST = MAX_BATCHES_FOR_INITIAL_TEST * BATCH_SIZE  # 100

# Gemini retry configuration
MAX_GEMINI_RETRIES = 3
RETRY_BACKOFF_SECONDS = [5, 10, 20]


def get_theme_name(theme_id: str) -> str:
    """Return the display name for a theme ID."""
    return THEME_TAXONOMY[theme_id]["name"] if theme_id in THEME_TAXONOMY else "Unknown"


def validate_theme_ids(theme_ids) -> bool:
    """Check that all theme IDs are valid."""
    if not isinstance(theme_ids, list):
        return False
    return all(tid in VALID_THEME_IDS for tid in theme_ids)


def validate_sentiment(sentiment) -> bool:
    """Check that sentiment is valid."""
    return sentiment in VALID_SENTIMENTS


def validate_fee_topic(fee_topic) -> bool:
    """Check that fee topic is valid."""
    return fee_topic in VALID_FEE_TOPICS


def is_fee_related(themes) -> bool:
    """Check if any assigned theme is fee-related."""
    return "T1" in themes


def get_taxonomy_json() -> str:
    """Return the taxonomy as a JSON string for inclusion in prompts."""
    import json
    return json.dumps(THEME_TAXONOMY, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    import json
    print(json.dumps(THEME_TAXONOMY, indent=2, ensure_ascii=False))
