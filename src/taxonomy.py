"""Fixed theme taxonomy for Groww review classification (Phase 3.2).

At most 5 themes. Each theme has strict descriptions and assignment criteria
so identical issues receive consistent labels across batches.

Key rules:
- Unclear, gibberish, or genuinely ambiguous feedback is NOT forced into T5.
- An empty themes array [] is valid for unclassified reviews.
- Sentiments: positive, negative, neutral, unclear, mixed.
- Fee topics: brokerage, dp_charges, other_fee, unspecified_fee, none, unclear.
- Fee subtype assigned ONLY when clearly supported by customer's words.
- Maximum 2 themes per review.

Used by both the Gemini classification prompt (n8n) and the deterministic
JavaScript validation node (n8n Code node).
"""

from __future__ import annotations

# Theme taxonomy: id -> {name, description, assignment_criteria, examples, counter_examples}
THEME_TAXONOMY = {
    "T1": {
        "name": "High Fees",
        "description": "Complaints about charges, brokerage, DP charges, AMC fees, "
                       "transaction costs, hidden fees, or unexpected deductions.",
        "assignment_criteria": (
            "Assign when the review explicitly mentions money being charged, deducted, "
            "or taken, including brokerage, DP charges, AMC, transaction fees, or hidden costs. "
            "Do NOT assign for general dissatisfaction without any mention of money/fees."
        ),
        "examples": [
            "Charged rs2000/- for SIP",
            "brokerage 20 per order is too high",
            "DP charges are excessive",
            "High fees and hidden charges",
            "Unexpected deduction from account"
        ],
        "counter_examples": [
            "The app is slow",
            "Good customer support",
            "Please add SWP feature",
            "I don't understand this app"
        ],
        "subtypes": ["brokerage", "dp_charges", "other_fee", "unspecified_fee"],
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
            "Add mutual fund SIP",
            "asdfghjkl random keys"
        ],
        "subtypes": None,
    },
    "T3": {
        "name": "Poor Customer Support",
        "description": "Complaints about customer service quality, unhelpful support, "
                       "slow response, unresolved tickets, rude behavior, or ticket ID issues.",
        "assignment_criteria": (
            "Assign when the review complains about support team behavior, response time, "
            "unresolved complaint/ticket IDs, or inability to reach support."
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
            "Add more mutual funds",
            "blah blah blah nonsense"
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
            "Support is rude",
            "sdfsdf unclear text"
        ],
        "subtypes": None,
    },
    "T5": {
        "name": "General Satisfaction",
        "description": "Positive feedback, praise, thank you, good experience, or general "
                       "appreciation without a specific complaint or request.",
        "assignment_criteria": (
            "Assign ONLY when the review is clearly positive with no complaint, fee issue, "
            "technical problem, support complaint, or feature request. Short praise like "
            "'good', 'nice', 'excellent' falls here. "
            "Do NOT assign T5 to unclear, gibberish, or ambiguous feedback — "
            "leave themes empty [] for those."
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
            "Please add SWP",
            "asdf unclear gibberish",
            "blah blah nonsense"
        ],
        "subtypes": None,
    },
}

# Valid sentiment values — includes unclear and mixed
VALID_SENTIMENTS = {"positive", "negative", "neutral", "unclear", "mixed"}

# Valid fee topic values
VALID_FEE_TOPICS = {"brokerage", "dp_charges", "other_fee", "unspecified_fee", "none", "unclear"}

# All valid theme IDs
VALID_THEME_IDS = set(THEME_TAXONOMY.keys())

# Maximum themes per review (empty array allowed for unclassified)
MAX_THEMES_PER_REVIEW = 2

# Default batch configuration
BATCH_SIZE = 25
MAX_BATCHES_FOR_INITIAL_TEST = 4  # 4 x 25 = 100 reviews
MAX_REVIEWS_FOR_INITIAL_TEST = MAX_BATCHES_FOR_INITIAL_TEST * BATCH_SIZE  # 100

# Gemini retry configuration
MAX_GEMINI_RETRIES = 3
RETRY_BACKOFF_SECONDS = [5, 10, 20]

# Deterministic selection seed for the 100-review test
DETERMINISTIC_SEED = 42


def get_theme_name(theme_id: str) -> str:
    """Return the display name for a theme ID."""
    return THEME_TAXONOMY[theme_id]["name"] if theme_id in THEME_TAXONOMY else "Unknown"


def validate_theme_ids(theme_ids) -> bool:
    """Check that all theme IDs are valid. Empty list is valid (unclassified)."""
    if not isinstance(theme_ids, list):
        return False
    return all(tid in VALID_THEME_IDS for tid in theme_ids)


def validate_sentiment(sentiment) -> bool:
    """Check that sentiment is valid (includes unclear, mixed)."""
    return sentiment in VALID_SENTIMENTS


def validate_fee_topic(fee_topic) -> bool:
    """Check that fee topic is valid."""
    return fee_topic in VALID_FEE_TOPICS


def is_fee_related(themes) -> bool:
    """Check if any assigned theme is fee-related (T1)."""
    return "T1" in themes


def is_fee_questionable(result: dict) -> bool:
    """Flag reviews where fee-topic claim is questionable for manual review.

    Questionable when:
    - T1 assigned but fee_topic is none/unclear
    - T1 not assigned but fee_topic is brokerage/dp_charges/other_fee/unspecified_fee
    """
    themes = result.get("themes", [])
    fee_topic = result.get("fee_topic", "none")
    is_fee = "T1" in themes
    has_fee_subtype = fee_topic in ("brokerage", "dp_charges", "other_fee", "unspecified_fee")
    return is_fee != has_fee_subtype


def get_taxonomy_json() -> str:
    """Return the taxonomy as a JSON string for inclusion in prompts."""
    import json
    return json.dumps(THEME_TAXONOMY, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    import json
    print(json.dumps(THEME_TAXONOMY, indent=2, ensure_ascii=False))
