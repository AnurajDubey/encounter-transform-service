"""Encounter-like ingest payload.

"Encounter-like", not FHIR: a real FHIR Encounter carries no CPT codes —
procedures are separate resources that reference the encounter. This payload
fuses them because the exercise input is one document (see README, "Not
FHIR").

Field selection rule: every field here must trace to a Claim field or a form
box. Anything that wouldn't end up on a claim doesn't belong on the input.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated

from pydantic import BaseModel, Field, model_validator

from app.models.common import CPT, ICD10, BillingEntity, Coverage, Patient, Provider


class ProcedurePerformed(BaseModel):
    """A performed service.

    Deliberately has no price field: an EHR records what was done, not what it
    costs. Pricing enters downstream, from the practice's charge master.
    """

    cpt: CPT
    units: int = Field(default=1, ge=1)
    modifiers: list[str] = Field(default_factory=list)
    # 0-based indexes into Encounter.diagnoses. None means the source system
    # didn't say which diagnoses justify this service; the transform then
    # defaults to all of them and flags that it guessed.
    diagnosis_refs: Annotated[list[int], Field(min_length=1)] | None = None


class Encounter(BaseModel):
    encounter_id: str
    patient: Patient
    coverage: Coverage
    rendering_provider: Provider
    # Really per-practice tenant config, not per-encounter data; carried on the
    # payload here to avoid building a tenancy layer (see README).
    billing_entity: BillingEntity
    date_of_service: date
    place_of_service: str = Field(default="11", pattern=r"^\d{2}$")
    diagnoses: list[ICD10] = Field(min_length=1)
    procedures: list[ProcedurePerformed] = Field(min_length=1)

    @model_validator(mode="after")
    def _diagnosis_refs_in_range(self) -> Encounter:
        highest = len(self.diagnoses) - 1
        for index, procedure in enumerate(self.procedures):
            for ref in procedure.diagnosis_refs or []:
                if not 0 <= ref <= highest:
                    raise ValueError(
                        f"procedures[{index}].diagnosis_refs contains {ref}; valid "
                        f"range is 0..{highest} (0-based index into diagnoses)"
                    )
        return self
