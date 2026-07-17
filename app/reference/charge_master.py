"""The practice's charge master: billed charge per CPT, payer-agnostic.

Charge master, not fee schedule — the distinction matters. The billed charge
is what the practice asks for on the claim: one number per code, the same for
every payer. Contracted rates are per-payer and belong in a separate table
that remittances get compared against — they are not what goes in Box 24F.

Hardcoded and tiny on purpose. In production this is per-practice data with
effective dates, modifier-based adjustments, and an audit trail.
"""

from decimal import Decimal

CHARGE_MASTER: dict[str, Decimal] = {
    "99203": Decimal("175.00"),  # office visit, new patient, low complexity
    "99213": Decimal("125.00"),  # office visit, established, low complexity
    "99214": Decimal("185.00"),  # office visit, established, moderate complexity
    "99215": Decimal("245.00"),  # office visit, established, high complexity
    "36415": Decimal("15.00"),   # venipuncture
    "80053": Decimal("60.00"),   # comprehensive metabolic panel
    "85025": Decimal("45.00"),   # CBC with differential
    "93000": Decimal("75.00"),   # 12-lead ECG with interpretation
    "90471": Decimal("30.00"),   # immunization administration, first vaccine
    "90686": Decimal("28.00"),   # influenza vaccine, quadrivalent
    "90834": Decimal("150.00"),  # psychotherapy, 45 minutes
    "99406": Decimal("35.00"),   # tobacco cessation counseling, 3-10 minutes
}


def lookup(cpt: str) -> Decimal | None:
    """None is a real answer: this practice has no price for that code."""
    return CHARGE_MASTER.get(cpt)
