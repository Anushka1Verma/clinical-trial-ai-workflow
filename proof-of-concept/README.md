# Team Tara protocol-to-data proof of concept

The command-line prototype reads a synthetic draft protocol, case report form (CRF) field list, lab feed specification, and statistical analysis plan (SAP). It checks whether each specified measurement is collected for the required visit and can be linked using the study participant identifier. It reads design specifications and runs without participant records.

## Run the demo

Use Python 3.10 or newer. No packages are required. Run from this directory.

```powershell
python -m poc.run --case data/demo --out out
python -m unittest discover -s tests -v
```

The run prints a report and writes `out/report.md` and `out/trace.json`. The checked-in `demo-output/` contains an actual local rules-mode run.

## What happens in the sample

1. The HbA1c check finds no CRF field, so the investigator provisionally proposes adding one. The lab specification has baseline and Week 24 fields for the same study participant key. The reviewer inspects the evidence context, and the controller withdraws the proposed CRF addition.
2. The fasting glucose check finds a baseline CRF field but no linked Week 24 field in either supplied specification. It returns a gap in the supplied specifications.
3. To try a counterfactual, copy `data/demo` to a new case folder. Add `LAB_FPG_W24,Fasting plasma glucose,Week 24,participant_id` to its lab feed and rerun. The Week 24 finding should become covered. Removing the lab feed makes an otherwise uncovered finding unknown.

## Model-backed mode

Set `ADAPTION_API_KEY` in your local environment using your own credential. The optional `ADAPTION_MODEL` defaults to `qwen3.5-397b`.

```powershell
python -m poc.run --mode adaption --case data/demo --out out/adaption
```

This mode sends synthetic evidence summaries to the [Adaption Responses API](https://docs.adaptionlabs.ai/api/resources/responses/methods/create) for investigator and reviewer decisions. The Python controller controls file access, validates allowed actions, and computes final findings from cited rows. The model-backed mode requires a credential and a live service check. The saved demo is a rules-mode run. Use synthetic files in either mode.

## Input contract

- `protocol.md` and `sap.md` use `- outcome ID | measurement | visit; visit` definition lines. Ordinary prose can appear beside those lines. The parser uses the definition lines, so use this format for additional outcomes.
- Source CSV files use `field_id,measurement,visit,participant_key`. One row defines one field at one visit. Use `participant_id` only when the source declares that it supplies the shared study participant identifier. A small alias dictionary recognizes the demonstration’s lab terminology.
- Both specifications must be available to conclude that an unmatched requirement is a gap. Missing or conflicting evidence produces an unknown result. Reports cite file names and source line numbers, and the JSON trace records the evidence and decision sequence.
