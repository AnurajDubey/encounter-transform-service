"""Routes only — business logic lives in app/transform/.

The route owns the impure parts (claim_id, created_at) and injects them into
the pure transforms, then merges their diagnostic lists.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import Body, FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.models.claim import Claim
from app.models.cms1500 import CMS1500Form
from app.models.diagnostics import Diagnostic
from app.models.encounter import Encounter
from app.transform.claim_to_cms1500 import claim_to_cms1500
from app.transform.encounter_to_claim import encounter_to_claim

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES_DIR = ROOT / "examples"

_EXAMPLE_SUMMARIES = {
    "01_simple_visit": "Happy path — 1 diagnosis, 1 procedure (pointers defaulted)",
    "02_multi_dx_pointers": "3 diagnoses, different pointer set per line",
    "03_exceeds_six_lines": "8 procedures — splits into 2 forms, re-lettered",
    "04_unpriced_cpt": "CPT missing from charge master — 200 + WARNING",
    "05_bad_npi_checksum": "NPI fails Luhn checksum — 422",
}


def _load_openapi_examples() -> dict:
    """One source of truth: the same files back curl, pytest, /docs, and the UI."""
    return {
        path.stem: {
            "summary": _EXAMPLE_SUMMARIES.get(path.stem, path.stem),
            "value": json.loads(path.read_text()),
        }
        for path in sorted(EXAMPLES_DIR.glob("*.json"))
    }


OPENAPI_EXAMPLES = _load_openapi_examples()

app = FastAPI(title="Encounter → Claim → CMS-1500 transform service", version="0.1.0")


class TransformResponse(BaseModel):
    claim: Claim
    cms1500: list[CMS1500Form]
    diagnostics: list[Diagnostic]


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/encounters/transform")
def transform_encounter(
    encounter: Annotated[Encounter, Body(openapi_examples=OPENAPI_EXAMPLES)],
) -> TransformResponse:
    claim_id = f"clm_{uuid4().hex[:12]}"
    created_at = datetime.now(timezone.utc)

    claim, claim_diagnostics = encounter_to_claim(
        encounter, claim_id=claim_id, created_at=created_at
    )
    forms, form_diagnostics = claim_to_cms1500(claim)

    return TransformResponse(
        claim=claim,
        cms1500=forms,
        diagnostics=claim_diagnostics + form_diagnostics,
    )


# Mounted last so it can never shadow the API routes above.
app.mount("/", StaticFiles(directory=ROOT / "static", html=True), name="static")
