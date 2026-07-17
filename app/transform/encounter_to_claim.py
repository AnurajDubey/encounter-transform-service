"""Encounter -> Claim: the decision-making half of the pipeline.

Everything opinionated happens here — what a service costs, and which
diagnoses justify it. Rendering concerns (letters, boxes, page splits) happen
later and cannot influence anything in this file.

Pure function: claim_id and created_at are injected by the caller, so
identical inputs produce identical claims and tests can assert exact outputs.
"""

from datetime import datetime
from decimal import Decimal

from app.models.claim import Claim, ClaimDiagnosis, ClaimItem
from app.models.diagnostics import Diagnostic, Severity
from app.models.encounter import Encounter
from app.reference.charge_master import lookup

ZERO = Decimal("0.00")


def encounter_to_claim(
    encounter: Encounter, claim_id: str, created_at: datetime
) -> tuple[Claim, list[Diagnostic]]:
    diagnostics: list[Diagnostic] = []

    diagnoses = [
        ClaimDiagnosis(sequence=index + 1, code=code)
        for index, code in enumerate(encounter.diagnoses)
    ]
    all_sequences = [d.sequence for d in diagnoses]

    items: list[ClaimItem] = []
    for index, procedure in enumerate(encounter.procedures):
        if procedure.diagnosis_refs is None:
            # The source didn't say which diagnoses justify this service.
            # Defaulting to all of them is convenient and medically
            # presumptuous, so it is flagged (see README, "pointer defaulting").
            sequences = list(all_sequences)
            diagnostics.append(
                Diagnostic(
                    severity=Severity.INFO,
                    code="DX_POINTER_DEFAULTED",
                    message=(
                        f"CPT {procedure.cpt}: encounter did not link diagnoses to this "
                        f"procedure; defaulted to all {len(all_sequences)} diagnoses"
                    ),
                    path=f"claim.items[{index}]",
                )
            )
        else:
            # 0-based encounter refs -> 1-based claim sequences.
            sequences = [ref + 1 for ref in procedure.diagnosis_refs]

        unit_charge = lookup(procedure.cpt)
        if unit_charge is None:
            unit_charge = ZERO
            diagnostics.append(
                Diagnostic(
                    severity=Severity.WARNING,
                    code="CPT_NOT_PRICED",
                    message=(
                        f"CPT {procedure.cpt} is not in the charge master; billed at "
                        "0.00 — price it before submission"
                    ),
                    path=f"claim.items[{index}]",
                )
            )

        items.append(
            ClaimItem(
                sequence=index + 1,
                cpt=procedure.cpt,
                modifiers=list(procedure.modifiers),
                units=procedure.units,
                unit_charge=unit_charge,
                net_charge=unit_charge * procedure.units,
                diagnosis_sequences=sequences,
                service_date=encounter.date_of_service,
                place_of_service=encounter.place_of_service,
            )
        )

    claim = Claim(
        claim_id=claim_id,
        created_at=created_at,
        patient=encounter.patient,
        coverage=encounter.coverage,
        rendering_provider=encounter.rendering_provider,
        billing_entity=encounter.billing_entity,
        diagnoses=diagnoses,
        items=items,
        total_charge=sum((item.net_charge for item in items), ZERO),
    )
    return claim, diagnostics
