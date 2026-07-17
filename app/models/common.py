"""Shared primitives used by every layer.

This module exists so that ``claim.py`` never has to import the ingest or
rendering models: identity types live here, at the bottom of the dependency
graph, and everything else points inward toward them.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, StringConstraints

from app.validation.codes import CPT_PATTERN, ICD10_PATTERN, NPI_PATTERN, validate_npi

ICD10 = Annotated[str, StringConstraints(pattern=ICD10_PATTERN)]
CPT = Annotated[str, StringConstraints(pattern=CPT_PATTERN)]
NPI = Annotated[str, StringConstraints(pattern=NPI_PATTERN), AfterValidator(validate_npi)]


class Patient(BaseModel):
    first_name: str
    last_name: str
    dob: date
    sex: Literal["M", "F", "U"] = "U"


class Coverage(BaseModel):
    payer_name: str
    member_id: str
    relationship: Literal["self", "spouse", "child", "other"] = "self"
    subscriber: Patient | None = None  # None: the patient is the subscriber


class Provider(BaseModel):
    """An individual clinician — the person who rendered care."""

    npi: NPI
    first_name: str
    last_name: str


class BillingEntity(BaseModel):
    """The organization that gets paid — distinct from whoever rendered care."""

    npi: NPI
    name: str
    tax_id: str
