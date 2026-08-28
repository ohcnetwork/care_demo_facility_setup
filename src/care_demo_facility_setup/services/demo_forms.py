from __future__ import annotations

import json
from importlib import resources
from typing import Any

PACKAGE = "care_demo_facility_setup"
DATA_DIR = "data"


def load_demo_form(slug: str) -> dict:
    path = resources.files(PACKAGE).joinpath(DATA_DIR, f"{slug}.json")
    if not path.is_file():
        raise FileNotFoundError(f"Missing demo questionnaire definition: {slug}.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Demo questionnaire {slug} must be a JSON object.")
    if payload.get("slug") != slug:
        raise ValueError(f"Demo questionnaire file slug must be '{slug}'.")
    return payload


def iter_questions(questions: list | None):
    for question in questions or []:
        if not isinstance(question, dict):
            continue
        yield question
        yield from iter_questions(question.get("questions"))


def _loinc_code(question: dict) -> str | None:
    code = question.get("code")
    if not isinstance(code, dict):
        return None
    raw = code.get("code")
    if not isinstance(raw, str):
        return None
    stripped = raw.strip()
    return stripped or None


def build_question_indexes(questionnaire: dict) -> tuple[dict[str, str], dict[str, str]]:
    """Return (loinc_code -> question_id, link_id -> question_id) for leaf-capable questions."""
    by_loinc: dict[str, str] = {}
    by_link_id: dict[str, str] = {}
    for question in iter_questions(questionnaire.get("questions")):
        question_id = question.get("id")
        if not question_id:
            continue
        question_id = str(question_id)
        loinc = _loinc_code(question)
        if loinc and loinc not in by_loinc:
            by_loinc[loinc] = question_id
        link_id = question.get("link_id")
        if isinstance(link_id, str) and link_id and link_id not in by_link_id:
            by_link_id[link_id] = question_id
    return by_loinc, by_link_id


def resolve_question_id(
    *,
    by_loinc: dict[str, str],
    by_link_id: dict[str, str],
    loinc: str | None = None,
    link_id: str | None = None,
    label: str,
) -> str:
    if loinc and loinc in by_loinc:
        return by_loinc[loinc]
    if link_id and link_id in by_link_id:
        return by_link_id[link_id]
    keys = []
    if loinc:
        keys.append(f"LOINC {loinc}")
    if link_id:
        keys.append(f"link_id {link_id}")
    joined = " / ".join(keys) if keys else "unknown key"
    raise ValueError(f"Could not resolve live question id for {label} ({joined}).")


def resolve_required_question_ids(questionnaire: dict, requirements: list[dict[str, Any]]) -> dict[str, str]:
    by_loinc, by_link_id = build_question_indexes(questionnaire)
    resolved: dict[str, str] = {}
    for requirement in requirements:
        key = requirement["key"]
        resolved[key] = resolve_question_id(
            by_loinc=by_loinc,
            by_link_id=by_link_id,
            loinc=requirement.get("loinc"),
            link_id=requirement.get("link_id"),
            label=key,
        )
    return resolved
