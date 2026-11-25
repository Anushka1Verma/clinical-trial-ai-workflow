# clinical-trial-ai-workflow
AgenticX 2026 AI Summit

Team Tara · AgenticX 2026 · Track 1

Clinical trial teams use the protocol to define what the study will measure and the statistical analysis plan to define how those measurements will be used. The case report form and lab feed specifications describe what data the team will actually receive. This proof of concept checks whether those documents agree before the trial starts.

## Run the proof of concept

Use Python 3.10 or newer. The local demo uses only the Python standard library and runs without an API key. From the repository root in PowerShell:

```powershell
cd proof-of-concept
py -3 -m poc.run --case data/demo --out out
py -3 -m unittest discover -s tests -v
```

If your terminal uses `python`, substitute it for `py -3`. The run prints the findings and saves `out/report.md` and `out/trace.json`. You can also open the [saved demo report](proof-of-concept/demo-output/report.md) and [decision trace](proof-of-concept/demo-output/trace.json).

## What the demo shows

The tool reads four [synthetic study files](proof-of-concept/data/demo): a draft protocol, a case report form (CRF) field list, a lab feed specification, and a statistical analysis plan (SAP).

| Protocol requirement | Evidence checked | Final finding |
| --- | --- | --- |
| HbA1c at baseline and Week 24 | The CRF has neither field, so the workflow provisionally suggests adding them. The lab feed supplies both measurements with the shared participant identifier. | **Covered.** The workflow withdraws its initial recommendation. |
| Fasting glucose at Week 24 | The CRF supplies a baseline field. Neither supplied specification contains the required Week 24 field. | **Gap in supplied specifications.** The report cites the files checked. |
| A required source is unavailable | Removing the lab specification leaves the workflow without enough evidence to resolve an uncovered visit. | **Unknown.** |

The report cites the exact file and line for each requirement and matching field. The JSON trace records the search, provisional recommendation, reviewer decision, and final result.

## Current stage

The verified prototype is a **local, rules-based Python CLI** using structured Markdown and CSV fixtures. The code includes an Adaption API adapter for model-backed investigator and reviewer decisions. A live run is the next milestone once `ADAPTION_API_KEY` is configured locally. The Python controller still checks the permitted actions and derives findings from the evidence it actually reads.

The proof of concept uses study design specifications and synthetic data. See the [prototype README](proof-of-concept/README.md) for the input format, model-mode instructions, and a way to test the effect of changing the lab specification.
