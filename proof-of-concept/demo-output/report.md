# Protocol-to-data coverage check

Mode: **Local rules mode**

This report checks supplied design specifications for a synthetic study.

## E1 · HbA1c · Baseline, Week 24

- **Requirement:** `protocol.md:6` and `sap.md:6`
- **First recommendation:** Provisionally add a CRF field for Baseline, Week 24 if no other source covers it.
- **Search:** `crf_fields.csv:1` inspected in full. No rows matched the measurement.
- **Search:** `lab_feed.csv:2` (Baseline, LAB_A1C_BL, participant_id), `lab_feed.csv:3` (Week 24, LAB_A1C_W24, participant_id).
- **Reviewer:** accept.
- **Final finding:** Covered. Withdraw the proposed CRF addition. The checked specifications cover all required visits.

## E2 · Fasting glucose · Week 24

- **Requirement:** `protocol.md:7` and `sap.md:7`
- **First recommendation:** Provisionally add a CRF field for Week 24 if no other source covers it.
- **Search:** `crf_fields.csv:2` (Baseline, FPG_BASE, participant_id).
- **Search:** `lab_feed.csv:1` inspected in full. No rows matched the measurement.
- **Reviewer:** accept.
- **Final finding:** Gap in supplied specifications. Confirm how Fasting glucose will be collected at Week 24.
