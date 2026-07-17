"""Five tests, driven by the same example payloads that back curl and /docs."""

import json
from decimal import Decimal
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"


def transform(example_name: str):
    payload = json.loads((EXAMPLES_DIR / example_name).read_text())
    return client.post("/v1/encounters/transform", json=payload)


def test_happy_path_total_equals_line_sum_and_single_form():
    response = transform("01_simple_visit.json")
    assert response.status_code == 200
    body = response.json()

    line_sum = sum(Decimal(str(item["net_charge"])) for item in body["claim"]["items"])
    assert Decimal(str(body["claim"]["total_charge"])) == line_sum

    assert len(body["cms1500"]) == 1
    assert body["cms1500"][0]["form_count"] == 1


def test_zero_based_refs_become_one_based_sequences_then_letters():
    response = transform("02_multi_dx_pointers.json")
    assert response.status_code == 200
    body = response.json()

    # encounter diagnosis_refs [1] (0-based) -> claim diagnosis_sequences [2]
    # (1-based) -> form pointer "B"
    assert body["claim"]["items"][1]["diagnosis_sequences"] == [2]
    assert body["cms1500"][0]["service_lines"][1]["diagnosis_pointers"] == "B"


def test_split_re_letters_each_form_and_totals_per_form():
    response = transform("03_exceeds_six_lines.json")
    assert response.status_code == 200
    body = response.json()

    forms = body["cms1500"]
    assert len(forms) == 2
    assert [len(form["service_lines"]) for form in forms] == [6, 2]

    for form in forms:
        # letters restart at "A" on every form, in order of first appearance
        labels = [d["label"] for d in form["diagnoses"]]
        assert labels == list("ABCDEFGHIJKL"[: len(labels)])
        # every pointer resolves against the same form's own Box 21
        for line in form["service_lines"]:
            assert set(line["diagnosis_pointers"]) <= set(labels)
        # each form totals its own lines, not the claim
        line_sum = sum(Decimal(str(line["charges"])) for line in form["service_lines"])
        assert Decimal(str(form["total_charge"])) == line_sum

    # the same diagnosis carries a different letter on each form
    letter_for = {
        form["form_index"]: {d["code"]: d["label"] for d in form["diagnoses"]}
        for form in forms
    }
    assert letter_for[1]["Z23"] == "E"
    assert letter_for[2]["Z23"] == "A"

    assert any(d["code"] == "SERVICE_LINES_SPLIT" for d in body["diagnostics"])


def test_unpriced_cpt_warns_but_still_builds_the_claim():
    response = transform("04_unpriced_cpt.json")
    assert response.status_code == 200
    body = response.json()

    warnings = [d for d in body["diagnostics"] if d["code"] == "CPT_NOT_PRICED"]
    assert len(warnings) == 1
    assert warnings[0]["severity"] == "warning"

    unpriced = [item for item in body["claim"]["items"] if item["cpt"] == "97110"]
    assert Decimal(str(unpriced[0]["net_charge"])) == Decimal("0.00")
    assert len(body["cms1500"]) == 1  # the claim still renders


def test_bad_npi_checksum_is_rejected_structurally():
    response = transform("05_bad_npi_checksum.json")
    assert response.status_code == 422
    assert "npi" in json.dumps(response.json()).lower()
