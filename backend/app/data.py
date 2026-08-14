"""Load and search the bundled patient dataset."""
import json
from pathlib import Path
from typing import Optional

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PATIENTS_PATH = DATA_DIR / "patients.json"


def load_patients() -> list[dict]:
    with open(PATIENTS_PATH, encoding="utf-8") as f:
        return json.load(f)["patients"]


def search_patients(q: Optional[str] = None) -> list[dict]:
    patients = load_patients()
    if not q or not q.strip():
        return patients
    needle = q.strip().lower()
    return [
        p
        for p in patients
        if needle in p["name"].lower() or needle in p["memberId"].lower()
    ]


def get_patient(patient_id: str) -> Optional[dict]:
    for p in load_patients():
        if p["id"] == patient_id:
            return p
    return None


def list_summary(patient: dict) -> dict:
    latest = ""
    for readings in patient.get("biomarkers", {}).values():
        for r in readings:
            if r["date"] > latest:
                latest = r["date"]
    pending = 0
    status = "no_summary"
    for s in patient.get("summaries", []):
        if s["status"] == "pending_review":
            pending += 1
            if status == "no_summary":
                status = "pending_review"
        elif status == "no_summary":
            status = s["status"]
    return {
        "id": patient["id"],
        "name": patient["name"],
        "memberId": patient["memberId"],
        "age": patient["age"],
        "sex": patient["sex"],
        "latestPanel": latest,
        "pendingReview": pending,
        "summaryStatus": status,
    }


def patient_snapshot(patient: dict) -> dict:
    return {
        "id": patient["id"],
        "name": patient["name"],
        "memberId": patient["memberId"],
        "age": patient["age"],
        "sex": patient["sex"],
        "geneticFlags": patient.get("geneticFlags", []),
        "biomarkers": patient.get("biomarkers", {}),
        "summaries": patient.get("summaries", []),
    }
