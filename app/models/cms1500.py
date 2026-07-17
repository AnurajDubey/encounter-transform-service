"""CMS-1500-style rendering of a Claim.

Box numbers live in field *descriptions*, never in field names — they surface
in /docs for free and the JSON stays semantic. The form's capacity limits
(12 diagnoses in Box 21, 6 service lines in Box 24) are enforced by the types
themselves: if the splitter misbehaves, Pydantic refuses to construct the
form — we find out, not the payer.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.common import CPT, ICD10, NPI


class FormDiagnosis(BaseModel):
    label: str = Field(pattern=r"^[A-L]$", description="Box 21 — diagnosis letter on this form")
    code: ICD10 = Field(description="Box 21 — ICD-10-CM code")


class FormServiceLine(BaseModel):
    line: int = Field(ge=1, le=6, description="Box 24 — row number on this form")
    date_from: date = Field(description="Box 24A — date of service (from)")
    place_of_service: str = Field(description="Box 24B — place of service code")
    cpt: CPT = Field(description="Box 24D — CPT/HCPCS procedure code")
    modifiers: list[str] = Field(default_factory=list, description="Box 24D — modifiers")
    diagnosis_pointers: str = Field(
        description='Box 24E — letters into this form\'s Box 21, e.g. "AB"'
    )
    charges: Decimal = Field(description="Box 24F — charge for this line")
    units: int = Field(ge=1, description="Box 24G — days or units")
    rendering_npi: NPI = Field(description="Box 24J — rendering provider NPI (who did the work)")


class CMS1500Form(BaseModel):
    form_index: int = Field(ge=1, description="Which physical form this is, 1-based — not a CMS box")
    form_count: int = Field(ge=1, description="How many forms the claim rendered to — not a CMS box")
    insured_id: str = Field(description="Box 1a — insured's ID number (member ID)")
    patient_name: str = Field(description='Box 2 — patient name, "LAST, FIRST"')
    patient_dob: date = Field(description="Box 3 — patient date of birth")
    icd_indicator: str = Field(default="0", description="Box 21 — ICD indicator; 0 = ICD-10-CM")
    diagnoses: list[FormDiagnosis] = Field(
        max_length=12, description="Box 21 — diagnoses A–L, lettered per form"
    )
    service_lines: list[FormServiceLine] = Field(
        max_length=6, description="Box 24 — up to six service lines"
    )
    total_charge: Decimal = Field(
        description="Box 28 — total of *this form's* lines, not the claim total"
    )
    billing_npi: NPI = Field(description="Box 33a — billing provider NPI (who gets paid)")
    tax_id: str = Field(description="Box 25 — federal tax ID (EIN)")
