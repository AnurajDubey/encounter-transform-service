"""Code-format validation primitives.

Everything in this module checks *shape*, not existence. A string that matches
ICD10_PATTERN is well-formed; whether it is a real, currently-billable code is
a question for a licensed code set with effective dates (see README).

The one genuinely verifiable thing here is the NPI check digit: NPIs carry a
real Luhn checksum, computed over the number prefixed with "80840" (the ISO
7812 issuer prefix for US health identifiers). A checksum-valid NPI still says
nothing about whether it is registered to anyone — that would be an NPPES
lookup. That contrast is the boundary between "provable offline" and "faked".
"""

ICD10_PATTERN = r"^[A-TV-Z][0-9][0-9AB](\.[0-9A-TV-Z]{1,4})?$"
CPT_PATTERN = r"^\d{5}$"
NPI_PATTERN = r"^\d{10}$"

_NPI_PREFIX = "80840"


def npi_checksum_ok(npi: str) -> bool:
    """Luhn check over '80840' + the full 10-digit NPI (check digit included)."""
    if len(npi) != 10 or not npi.isdigit():
        return False
    total = 0
    for position, char in enumerate(reversed(_NPI_PREFIX + npi)):
        digit = int(char)
        if position % 2 == 1:  # double every second digit, moving left from the check digit
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


def validate_npi(npi: str) -> str:
    """Pydantic AfterValidator: an NPI with a wrong check digit is not an NPI."""
    if not npi_checksum_ok(npi):
        raise ValueError("NPI fails its Luhn check digit (computed over '80840' + NPI)")
    return npi
