# Encounter → Claim → CMS-1500

A small, stateless FastAPI service. POST an Encounter-like payload; get back:

1. the **Claim** built from it — the canonical object,
2. the **CMS-1500-style form(s)** projected from that Claim,
3. **diagnostics** — a machine-readable list of every default taken and flag raised along the way.

## Run

From the repo root, start the service:

```bash
uv run uvicorn app.main:app --port 8000
```

Run the tests (5 tests over the same example payloads):

```bash
uv run pytest
```

- **http://localhost:8000/docs** — Swagger UI; the request body has all five examples in a labeled dropdown.
- **http://localhost:8000/** — throwaway HTML harness; renders multiple forms side by side so the per-form diagnosis re-lettering is visible.

No Docker, no database, no config. `uv` resolves everything, including the Python version.

## Exercise it

```bash
curl -s -X POST http://localhost:8000/v1/encounters/transform \
  -H 'Content-Type: application/json' \
  -d @examples/03_exceeds_six_lines.json | jq
```

| file | demonstrates | expect |
|---|---|---|
| `examples/01_simple_visit.json` | happy path — 1 dx, 1 CPT; omits `diagnosis_refs` | 200; 1 form; INFO `DX_POINTER_DEFAULTED` |
| `examples/02_multi_dx_pointers.json` | 3 dx, 2 lines, different pointer set per line | 200; pointers `ABC` vs `B` |
| `examples/03_exceeds_six_lines.json` | 8 procedures → 2 forms, re-lettered per form | 200; `Z23` is **E** on form 1, **A** on form 2; WARNING `SERVICE_LINES_SPLIT` |
| `examples/04_unpriced_cpt.json` | CPT `97110` not in charge master | 200; line billed `0.00`; WARNING `CPT_NOT_PRICED` |
| `examples/05_bad_npi_checksum.json` | rendering NPI fails its Luhn check digit | **422** — structural, not business |

The same five files are the pytest fixtures and the /docs examples — one source of truth.

## Design

- Pipeline: **Encounter → Claim → CMS-1500**, two pure functions. IDs and timestamps are injected by the route, so identical inputs produce identical outputs and tests assert exact values.
- The **Claim is canonical**: it knows nothing about where it came from or what it becomes. `app/models/claim.py` imports only `common` and stdlib — no box numbers, no letters, no capacity limits. Dependencies point inward toward it.
- **Encounter → Claim is a set of decisions**: what's billable, what it costs (charge master lookup), which diagnosis justifies which line (0-based refs → 1-based sequences).
- **Claim → CMS-1500 is a projection**: rearrange into boxes; sequences become per-form letters; ≤6 lines and ≤12 diagnoses per form, enforced by the output types themselves (`max_length`), so a buggy splitter fails at construction — caught by Pydantic, not the payer.
- CMS-1500 is **a renderer, not the model**. A clearinghouse JSON payload or an 837P would be sibling renderers off the same Claim — that is why `claim.py` contains no box concepts.
- **Validation split** is a contract decision: structural problems (bad types, malformed codes, an NPI failing its checksum) are 422s from Pydantic — an NPI with a wrong check digit is not an NPI. Business problems (unpriced CPT, defaulted pointers, capacity overflow) are 200s with diagnostics — we can still build the claim; a human needs to see the flag.
- **Money is `Decimal` end to end**, never float, and serializes to JSON as strings (`"473.00"`). `sum()` of floats produces `247.85000000000002` and breaks the invariant that the form total equals the sum of its line charges. Payers check this.

## Assumptions & simplifications

- **Money is absent from the input.** An EHR doesn't know the practice's charge master. Prices enter at the transform, from a hardcoded dict (`app/reference/charge_master.py`) — charge master, not fee schedule: what goes on the claim is the practice's billed charge (payer-agnostic), not the contracted rate (per-payer).
- **The dx↔CPT linkage is optional on the input.** Two flat lists don't encode which diagnosis justifies which service; in reality a coder creates that link, or the EHR's charge-capture screen does. I made it an optional `diagnosis_refs` field per procedure and default to all-diagnoses with an INFO diagnostic when absent.
- **One NPI in, two provider slots out.** Box 24J is who rendered the service; Box 33a is who gets paid. For an NP practice these differ and it's economically load-bearing — Medicare pays NPs 85% of the physician fee schedule when billing under the NP's own NPI. Both are modeled explicitly rather than collapsed.
- **`billing_entity` on the encounter is wrong.** It's per-practice tenant config, identical across every encounter from that practice. It belongs in configuration; it's on the payload to avoid building a tenancy layer for this exercise.
- **Patient ≠ subscriber is modeled but not exercised.** `Coverage.subscriber` exists; the transform assumes self.
- **Box 1 insurance type is not inferred.** Deriving it from a payer-name string is a heuristic that will be wrong.

## What's real vs. faked

**Real:**

- The Claim's structure and pointer semantics — FHIR models the diagnosis↔service linkage the same way.
- Box semantics; the 12-diagnosis and 6-service-line capacity limits; the ICD indicator `0` (ICD-10-CM).
- The format regexes for ICD-10 / CPT / NPI shapes.
- The NPI Luhn checksum (computed over `80840` + NPI, per the CMS standard). This is genuinely verifiable offline.

**Faked:**

- The charge master — hardcoded, no contracts, no modifier-based adjustment, no effective dates.
- Code *validity* — a well-formed ICD-10 code is not a real one.
- Payer routing, eligibility, credentialing: absent entirely.
- NPI *existence* — the checksum is real; an NPPES registry lookup is not. That contrast is the clearest example of the boundary: I can prove an NPI is well-formed; I cannot prove it belongs to anyone.

## Not FHIR

A real FHIR Encounter does not contain CPT codes — procedures are separate `Procedure` resources that reference the Encounter. This model fuses them into one payload. The brief says "Encounter-like" for exactly this reason; claiming FHIR compliance here would be false.

## What I wouldn't trust in production

- **Code validity.** The regexes check shape, not existence — `Z99.999` is well-formed and meaningless. The ICD-10 regex also excludes the `U` block (the classic pre-2020 convention), so `U07.1` — COVID-19 — fails format validation. Production needs a licensed code set with effective dates: ICD-10 and CPT are revised annually, and billing a retired code is an automatic denial.
- **Pointer defaulting.** "Every diagnosis justifies every service" is precisely what triggers medical-necessity denials. It's convenient, not correct. Production should probably refuse to build the claim rather than guess.
- **The split's semantics.** My split is presentation-driven — the form ran out of rows. But each resulting form is separately adjudicated and may need a shared reference so the payer knows they're related. I've treated a billing consequence as a rendering concern. The honest fix is a submission-planning step between the Claim and the renderer that decides form count and line allocation, leaving the renderer purely mechanical. The abstraction leaks and I know where.
- **The letter re-assignment on split.** I believe it's correct per the form's semantics — pointers must resolve against the same physical form's Box 21. I have not verified it against any payer's companion guide, and companion guides are where "standard" formats go to die.
- **Idempotency.** POSTing the same encounter twice yields two claims with different IDs. Payers flag duplicate claims; duplicates are a real operational failure. Production needs an idempotency key or a natural key on `(encounter_id, version)`.
- **Rounding policy.** `Decimal` is correct but no quantization policy is set. Half-up vs. banker's rounding on a multi-unit line is a real disagreement with a payer waiting to happen.
- **Modifier/POS coupling.** Telehealth requires POS `10`/`02` and modifier `95`. Nothing enforces the pairing; both are pass-through.
- **No credentialing check.** A well-formed claim for a payer the provider isn't enrolled with is a guaranteed denial that looks like a clean success here.

## What I'd build next

- **A clearinghouse renderer** as a sibling of the CMS-1500 renderer — new module, zero changes to the transform. That's the test of whether the Claim abstraction actually holds.
- **Persist Claims, not forms.** The Claim is the record; forms are derived and disposable. "What did we send in March?" is answered by re-rendering, not by fetching a stored artifact.
- **Async, for the right reason.** Not transform latency — the transform is microseconds. Submission is a multi-week state machine: the clearinghouse acks receipt, then EDI syntax validates, then the payer acknowledges the claim, then weeks later a remittance arrives with the money or the denial. Four failure points, arriving out of band. That's what needs decoupling.
- **A per-payer rules layer.** Companion guides mean the "standard" has hundreds of dialects.
- **Contracted-rate table + underpayment detection.** Distinct from the charge master. Knowing the contracted rate lets you catch a payer paying $80 when the contract says $95 — real money, and something only the biller can catch.
