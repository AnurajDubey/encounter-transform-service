"""Place-of-service codes (CMS POS code set, heavily abridged).

Reference data only: the transform passes POS through untouched and nothing
rejects a code missing from this map — the real set has ~50 entries and this
is not it. This module is the natural home for POS/modifier coupling rules
(telehealth POS 10/02 expects modifier 95), which are deliberately
unimplemented — see README, "What I wouldn't trust in production".
"""

POS_CODES: dict[str, str] = {
    "11": "Office",
    "10": "Telehealth provided in patient's home",
    "02": "Telehealth provided other than in patient's home",
    "21": "Inpatient hospital",
}


def describe(pos: str) -> str | None:
    return POS_CODES.get(pos)
