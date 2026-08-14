# Genetic flags and interpretation

Genetic flags are stored on a patient's record at intake (or when a result arrives) and **change how a biomarker trend should be read**.

## Known flags in this platform

- **`elevated_cardiovascular_risk`** (e.g. APOB variant) — applies extra weight to **LDL and HDL** trend interpretation.
- **`hba1c_family_history`** (family history of type 2 diabetes) — applies extra weight to **HbA1c** trend interpretation.

## How to use them

- When a flag affects a biomarker that has a trend, the summary should note: *"With [flag] on file, this [biomarker] trajectory carries more significance than it would in an unselected patient."*
- Flags do not change the measured values — they change the **interpretive weight**.
- A flagged patient's threshold crossing matters more than the same crossing in an unselected patient.

## Example

- LDL 110 → 160 mg/dL over a year in a patient with `elevated_cardiovascular_risk` → higher concern than the identical trend without the flag.
