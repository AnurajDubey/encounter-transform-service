"""Claim -> CMS-1500: the projection half of the pipeline.

Nothing here decides anything about money or medicine — it rearranges an
already-decided Claim into the form's geometry: at most 6 service lines per
form, at most 12 diagnoses in Box 21, and per-form letters replacing
claim-wide sequences.

Pure function. The split is presentation-driven pagination; the README covers
why that is a known simplification (real multi-form claims have submission
semantics, not just layout).
"""

from decimal import Decimal

from app.models.claim import Claim, ClaimItem
from app.models.cms1500 import CMS1500Form, FormDiagnosis, FormServiceLine
from app.models.diagnostics import Diagnostic, Severity

LINES_PER_FORM = 6       # Box 24 rows
DIAGNOSES_PER_FORM = 12  # Box 21 slots
LETTERS = "ABCDEFGHIJKL"


def _letter_map(chunk: list[ClaimItem]) -> tuple[dict[int, str], list[int]]:
    """Assign one form's Box 21 letters.

    Letters are a property of the form, not the claim. Each form letters only
    the diagnoses its own lines actually reference, starting at "A", in order
    of first appearance while walking that form's lines. The same claim
    diagnosis can therefore be "C" on form 1 and "A" on form 2 — correct and
    intentional, because a Box 24E pointer resolves against Box 21 of the same
    physical form.

    Returns (sequence -> letter, sequences that did not fit in 12 slots).
    """
    letters: dict[int, str] = {}
    overflow: list[int] = []
    for item in chunk:
        for sequence in item.diagnosis_sequences:
            if sequence in letters or sequence in overflow:
                continue
            if len(letters) < DIAGNOSES_PER_FORM:
                letters[sequence] = LETTERS[len(letters)]
            else:
                overflow.append(sequence)
    return letters, overflow


def claim_to_cms1500(claim: Claim) -> tuple[list[CMS1500Form], list[Diagnostic]]:
    """Render a Claim to one or more CMS-1500-style forms. Always returns a list."""
    diagnostics: list[Diagnostic] = []
    chunks = [
        claim.items[start : start + LINES_PER_FORM]
        for start in range(0, len(claim.items), LINES_PER_FORM)
    ]
    code_for = {d.sequence: d.code for d in claim.diagnoses}

    forms: list[CMS1500Form] = []
    for form_index, chunk in enumerate(chunks, start=1):
        letters, overflow = _letter_map(chunk)

        if overflow:
            diagnostics.append(
                Diagnostic(
                    severity=Severity.ERROR,
                    code="DIAGNOSIS_LIMIT_EXCEEDED",
                    message=(
                        f"form {form_index} references {len(letters) + len(overflow)} "
                        f"distinct diagnoses but Box 21 holds {DIAGNOSES_PER_FORM}; "
                        f"dropped sequences {overflow} and their pointers"
                    ),
                    path=f"cms1500[{form_index - 1}].diagnoses",
                )
            )

        service_lines = [
            FormServiceLine(
                line=row,
                date_from=item.service_date,
                place_of_service=item.place_of_service,
                cpt=item.cpt,
                modifiers=list(item.modifiers),
                diagnosis_pointers="".join(
                    letters[s] for s in item.diagnosis_sequences if s in letters
                ),
                charges=item.net_charge,
                units=item.units,
                rendering_npi=claim.rendering_provider.npi,
            )
            for row, item in enumerate(chunk, start=1)
        ]

        forms.append(
            CMS1500Form(
                form_index=form_index,
                form_count=len(chunks),
                insured_id=claim.coverage.member_id,
                patient_name=(
                    f"{claim.patient.last_name.upper()}, {claim.patient.first_name.upper()}"
                ),
                patient_dob=claim.patient.dob,
                diagnoses=[
                    FormDiagnosis(label=letter, code=code_for[sequence])
                    for sequence, letter in letters.items()
                ],
                service_lines=service_lines,
                # Each form totals its own lines, not the claim.
                total_charge=sum((line.charges for line in service_lines), Decimal("0.00")),
                billing_npi=claim.billing_entity.npi,
                tax_id=claim.billing_entity.tax_id,
            )
        )

    if len(forms) > 1:
        diagnostics.append(
            Diagnostic(
                severity=Severity.WARNING,
                code="SERVICE_LINES_SPLIT",
                message=(
                    f"{len(claim.items)} service lines exceed the {LINES_PER_FORM} rows "
                    f"of Box 24; claim rendered as {len(forms)} forms — verify the payer "
                    "accepts multi-form submission for this claim"
                ),
                path="cms1500",
            )
        )

    return forms, diagnostics
