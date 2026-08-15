"""Deterministic input guard: deny-list prompt-injection / jailbreak detection."""
import re

_PATTERNS: list[tuple[str, re.Pattern]] = [
    (
        "ignore_instructions",
        re.compile(
            r"\bignore\s+(all\s+|the\s+|your\s+|previous\s+|above\s+)?(instructions|prompts|rules|system\s+prompts?|context|guidelines)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "reveal_instructions",
        re.compile(
            r"\b(reveal|show|print|display|repeat)\s+(me\s+)?(your\s+)?(system\s+prompts?|instructions|rules|prompts)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "impersonate",
        re.compile(
            r"\b(you are now|act as (an? )?(ai|chatgpt|assistant|different|another|model))\b",
            re.IGNORECASE,
        ),
    ),
    (
        "disregard_rules",
        re.compile(
            r"\b(disregard|forget|override)\s+(all\s+|the\s+|your\s+|previous\s+|above\s+)?(instructions|rules|prompts|context)\b",
            re.IGNORECASE,
        ),
    ),
    ("jailbreak", re.compile(r"\b(jailbreak|developer mode)\b", re.IGNORECASE)),
    ("dan_mode", re.compile(r"\bDAN\b")),
    (
        "system_message",
        re.compile(r"\b(system\s+message|as a system|respond as system)\b", re.IGNORECASE),
    ),
    (
        "cross_patient",
        re.compile(r"\b(list|show|give me|tell me)\s+(all|every)\s+(patients?|members?)\b", re.IGNORECASE),
    ),
]


def scan_injection(text: str) -> list[str]:
    return [name for name, pat in _PATTERNS if pat.search(text)]


def is_injection(message: str, history: list[dict] | None = None) -> bool:
    texts = [message]
    for m in history or []:
        if isinstance(m, dict) and isinstance(m.get("content"), str):
            texts.append(m["content"])
    return any(scan_injection(t) for t in texts)
