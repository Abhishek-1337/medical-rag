# Clinical summary guidelines

AI-drafted clinical summaries in this platform follow strict rules so they are **safe, grounded, and reviewable** by a clinician.

## Rules for drafting

1. **Identify change** — what changed, the direction, and the magnitude (absolute + percent).
2. **Ground every claim** — reference specific values and dates. Cite the exact readings used.
3. **Use genetic context** — note when a flag changes how a trend should be read.
4. **No direct patient instructions** — never say "you should reduce sugar intake". Instead: "consider discussing dietary changes with your doctor" or similar clinician-framed language.
5. **Always draft, never final** — output enters a `pending_review` state and is only shown to the patient after a clinician approves or edits it.

## Citation format

- Trend claims cite the relevant readings (first, last, steepest step pair, threshold-crossing reading).
- Flag-based claims cite the flag on file.

## Workflow

- Draft → clinician review → edit/approve → patient-visible only after approval.
- A patient never sees a draft or a pending state.
