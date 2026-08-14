"""Structured retrieval over the seeded patient dataset.

Numbers come from the record directly — no embeddings, no hallucination.
The trend math mirrors Baseline's deterministic summary generator.
"""
from datetime import datetime
from typing import Optional

THRESHOLDS: dict[str, tuple[float, str]] = {
    "HbA1c": (5.7, "5.7% prediabetes"),
    "LDL": (160, "160 mg/dL"),
    "HDL": (40, "40 mg/dL"),
}
FLAG_LABELS = {
    "elevated_cardiovascular_risk": "APOB variant — elevated cardiovascular risk",
    "hba1c_family_history": "family history of type 2 diabetes",
}
FLAG_TYPES = {
    "elevated_cardiovascular_risk": ["LDL", "HDL"],
    "hba1c_family_history": ["HbA1c"],
}
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def unit_for(btype: str) -> str:
    return "%" if btype == "HbA1c" else "mg/dL"


def fmt_date(iso: str) -> str:
    d = datetime.fromisoformat(iso)
    return f"{MONTHS[d.month - 1]} {d.year}"


def fmt_val(value: float, unit: str) -> str:
    return f"{value:.1f}%" if unit == "%" else f"{round(value)} {unit}"


def fmt_delta(value: float) -> str:
    r = round(value, 1)
    return str(int(r)) if r.is_integer() else str(r)


def article(pct: str) -> str:
    return "an" if pct.startswith("8") else "a"


def analyze_patient(patient: dict, biomarker: Optional[str] = None) -> list[dict]:
    """Per-biomarker trend facts. Pure computation over the record."""
    out: list[dict] = []
    types = [biomarker] if biomarker else list(patient["biomarkers"].keys())
    for t in types:
        readings = sorted(patient.get("biomarkers", {}).get(t, []), key=lambda r: r["date"])
        if not readings:
            continue
        if len(readings) < 2:
            out.append({"type": t, "note": "single reading on file"})
            continue
        first, last = readings[0], readings[-1]
        delta = last["value"] - first["value"]
        pct = delta / first["value"] * 100 if first["value"] else 0.0
        steep = max(
            ((readings[i - 1], readings[i], abs(readings[i]["value"] - readings[i - 1]["value"])) for i in range(1, len(readings))),
            key=lambda s: s[2],
        )
        crossing = None
        if t in THRESHOLDS:
            th = THRESHOLDS[t][0]
            for i in range(1, len(readings)):
                if readings[i - 1]["value"] < th <= readings[i]["value"]:
                    crossing = readings[i]
                    break
        out.append(
            {
                "type": t,
                "first": first,
                "last": last,
                "pct": pct,
                "delta": delta,
                "steep": {"from": steep[0], "to": steep[1], "abs": steep[2]},
                "crossing": crossing,
            }
        )
    return out


def _trend_lines(analyses: list[dict]) -> tuple[list[str], list[dict]]:
    lines: list[str] = []
    sources: list[dict] = []
    for a in analyses:
        if "note" in a:
            lines.append(f"- {a['type']}: {a['note']}")
            continue
        unit = unit_for(a["type"])
        pct = fmt_delta(abs(a["pct"]))
        lines.append(
            f"- **{a['type']}** {'rose' if a['delta'] >= 0 else 'fell'} from {fmt_val(a['first']['value'], unit)} to "
            f"{fmt_val(a['last']['value'], unit)} ({fmt_date(a['first']['date'])} → {fmt_date(a['last']['date'])}) — "
            f"{article(pct)} {pct}% {'increase' if a['pct'] >= 0 else 'decrease'}."
        )
        sources.append(
            {"type": "result", "label": f"{a['type']} {fmt_val(a['first']['value'], unit)} → {fmt_val(a['last']['value'], unit)} · {fmt_date(a['first']['date'])} → {fmt_date(a['last']['date'])}"}
        )
        step = a["steep"]
        lines.append(
            f"  - Steepest step: {fmt_val(step['from']['value'], unit)} → {fmt_val(step['to']['value'], unit)} "
            f"between {fmt_date(step['from']['date'])} and {fmt_date(step['to']['date'])}."
        )
        sources.append({"type": "result", "label": f"steepest step {a['type']} · {fmt_date(step['from']['date'])} → {fmt_date(step['to']['date'])}"})
        if a["crossing"]:
            th_label = THRESHOLDS[a["type"]][1]
            lines.append(f"  - Threshold crossing: crossed {th_label} at the {fmt_date(a['crossing']['date'])} reading ({fmt_val(a['crossing']['value'], unit)}).")
            sources.append({"type": "result", "label": f"{a['type']} crossed {th_label} · {fmt_date(a['crossing']['date'])}"})
    return lines, sources


def patient_facts(patient: dict) -> tuple[str, list[dict]]:
    lines, sources = _trend_lines(analyze_patient(patient))
    for flag in patient.get("geneticFlags", []):
        affected = ", ".join(FLAG_TYPES.get(flag, []))
        lines.append(f"- Genetic flag: **{FLAG_LABELS.get(flag, flag)}** on file — read {affected} trends with extra weight.")
        sources.append({"type": "flag", "label": f"{FLAG_LABELS.get(flag, flag)} · read {affected} with extra weight"})
    if not lines:
        return f"No biomarker data for {patient['name']}.", []
    return "\n".join(lines), sources


def summary_facts(patient: dict) -> tuple[str, list[dict]]:
    s = patient["summaries"][-1] if patient.get("summaries") else None
    if not s:
        return f"No summary yet for {patient['name']}.", []
    status = s.get("status", "unknown")
    created = fmt_date(s.get("createdAt", "")) if s.get("createdAt") else "unknown date"
    return (
        f"Latest summary for **{patient['name']}** ({patient['memberId']}): status **{status}** (created {created}).\n\n{s['generatedText']}",
        [{"type": "summary", "label": f"{status.replace('_', ' ')} · created {created}"}],
    )


def queue_facts() -> tuple[str, list[dict]]:
    from .data import load_patients

    pending = [
        (p, s)
        for p in load_patients()
        for s in p.get("summaries", [])
        if s.get("status") == "pending_review"
    ]
    if not pending:
        return "Review queue is empty — no summaries pending review.", []
    lines = ["Review queue:"]
    sources = []
    for p, s in pending:
        lines.append(f"- **{p['name']}** ({p['memberId']}) — draft awaiting review (created {fmt_date(s.get('createdAt', ''))}).")
        sources.append({"type": "queue", "label": f"{p['name']} · {s.get('status', 'pending_review')}"})
    return "\n".join(lines), sources


def chart_facts(patient: dict, biomarker: Optional[str] = None) -> dict | None:
    """Deterministic chart payload: real series + thresholds, no LLM in the loop."""
    types = [biomarker] if biomarker else list(patient["biomarkers"].keys())
    series = []
    for t in types:
        readings = sorted(patient.get("biomarkers", {}).get(t, []), key=lambda r: r["date"])
        if len(readings) < 2:
            continue
        series.append(
            {
                "name": t,
                "unit": unit_for(t),
                "points": [{"date": r["date"], "value": r["value"]} for r in readings],
            }
        )
    if not series:
        return None
    return {
        "title": f"{biomarker + ' trend' if biomarker else 'Biomarker trends'} — {patient['name']} ({patient['memberId']})",
        "series": series,
        "thresholds": [
            {"value": THRESHOLDS[t][0], "label": THRESHOLDS[t][1]}
            for t in types
            if t in THRESHOLDS
        ],
    }


def compare_facts(patients: list[dict], biomarker: str) -> tuple[str, list[dict]]:
    unit = unit_for(biomarker)
    lines = [f"Comparing **{biomarker}** ({unit}):"]
    sources: list[dict] = []
    for p in patients:
        a = next(iter(analyze_patient(p, biomarker)), None)
        if not a or "note" in a:
            lines.append(f"- **{p['name']}**: no trend data.")
            continue
        pct = fmt_delta(abs(a["pct"]))
        lines.append(
            f"- **{p['name']}**: {a['first']['value']} → {a['last']['value']} ({fmt_date(a['first']['date'])} → {fmt_date(a['last']['date'])}) — "
            f"{article(pct)} {pct}% {'increase' if a['pct'] >= 0 else 'decrease'}."
        )
        sources.append({"type": "result", "label": f"{p['name']} {biomarker} {a['first']['value']} → {a['last']['value']}"})
    return "\n".join(lines), sources
