"""The canonical claim — the pivot the whole service turns on.

Imports ``common`` and the standard library only. A claim knows nothing about
the payload it was built from or the artifacts rendered from it; ingest and
rendering code depend on this module, never the reverse. That inversion is
what makes new renderers (an 837P, a clearinghouse API body) additive instead
of invasive.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.common import CPT, ICD10, BillingEntity, Coverage, Patient, Provider


class ClaimDiagnosis(BaseModel):
    sequence: int = Field(ge=1, description="1-based; stable across the whole claim")
    code: ICD10


class ClaimItem(BaseModel):
    sequence: int = Field(ge=1, description="1-based position on the claim")
    cpt: CPT
    modifiers: list[str] = Field(default_factory=list)
    units: int = Field(ge=1)
    unit_charge: Decimal = Field(description="billed charge per unit, from the charge master")
    net_charge: Decimal = Field(description="unit_charge x units")
    diagnosis_sequences: list[int] = Field(
        description="ClaimDiagnosis.sequence values that justify this item"
    )
    service_date: date
    place_of_service: str


class Claim(BaseModel):
    claim_id: str
    created_at: datetime
    patient: Patient
    coverage: Coverage
    rendering_provider: Provider
    billing_entity: BillingEntity
    diagnoses: list[ClaimDiagnosis]
    items: list[ClaimItem]  # unbounded by design; renderers decide what fits where
    total_charge: Decimal = Field(description="sum of net_charge across all items")
