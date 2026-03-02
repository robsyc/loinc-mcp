"""Utilities for LOINC MCP Server.

Response formatters, API helpers, and constants for the LOINC Search API.
"""

import json
import os
from typing import Any

LOINC_BASE_URL = "https://loinc.regenstrief.org/searchapi"
LOINC_TIMEOUT = 30.0

CLASS_TYPES: dict[str, str] = {
    "1": "Laboratory",
    "2": "Clinical",
    "3": "Claims attachments",
    "4": "Surveys",
}

ORDER_OBS_TYPES: dict[str, str] = {
    "Order": "Orderable",
    "Observation": "Observable",
    "Both": "Orderable and observable",
}


def get_auth_credentials() -> tuple[str, str]:
    """Get LOINC API credentials from environment variables.

    Supports:
    - LOINC_USERNAME + LOINC_PASSWORD (separate vars)
    - LOINC_API_KEY as "username:password" (single var)

    Raises:
        RuntimeError: If credentials are not configured.
    """
    username = os.environ.get("LOINC_USERNAME", "")
    password = os.environ.get("LOINC_PASSWORD", "")
    if username and password:
        return username, password

    api_key = os.environ.get("LOINC_API_KEY", "")
    if api_key and ":" in api_key:
        u, p = api_key.split(":", 1)
        return u, p

    raise RuntimeError(
        "LOINC API credentials not configured. "
        "Set LOINC_USERNAME and LOINC_PASSWORD, "
        "or LOINC_API_KEY as 'username:password'. "
        "Register free at https://loinc.org/join"
    )


def is_panel(data: dict[str, Any]) -> bool:
    """Check whether a LOINC item is a panel based on its CLASS field."""
    cls = (data.get("CLASS") or "").upper()
    return cls.startswith("PANEL.") or cls == "PANEL"


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------

def _results_list(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract the results array from a Search API response."""
    return data.get("Results") or data.get("results") or []


def format_search_results(data: dict[str, Any], limit: int) -> str:
    """Format LOINC search results into a concise JSON string."""
    items = _results_list(data)
    results: list[dict[str, Any]] = []

    for item in items[:limit]:
        entry: dict[str, Any] = {
            "code": item.get("LOINC_NUM", ""),
            "name": item.get("LONG_COMMON_NAME", ""),
            "component": item.get("COMPONENT", ""),
            "system": item.get("SYSTEM", ""),
            "class": item.get("CLASS", ""),
            "class_type": CLASS_TYPES.get(str(item.get("CLASSTYPE", "")), ""),
        }
        entry = {k: v for k, v in entry.items() if v}

        status = item.get("STATUS", "")
        if status and status != "ACTIVE":
            entry["status"] = status

        if is_panel(item):
            entry["is_panel"] = True

        results.append(entry)

    return _to_json({"results": results, "total": len(items)})


def format_code_details(
    data: dict[str, Any],
    panel_members: list[dict[str, Any]] | None = None,
    answer_list_data: dict[str, Any] | None = None,
) -> str:
    """Format detailed LOINC code information."""
    code: dict[str, Any] = {
        "code": data.get("LOINC_NUM", ""),
        "name": data.get("LONG_COMMON_NAME", ""),
    }

    short = data.get("SHORTNAME", "")
    if short:
        code["short_name"] = short

    parts = {
        "component": data.get("COMPONENT", ""),
        "property": data.get("PROPERTY", ""),
        "timing": data.get("TIME_ASPCT", ""),
        "system": data.get("SYSTEM", ""),
        "scale": data.get("SCALE_TYP", ""),
        "method": data.get("METHOD_TYP", ""),
    }
    code["parts"] = {k: v for k, v in parts.items() if v}

    classification: dict[str, str] = {}
    ct = str(data.get("CLASSTYPE", ""))
    if ct in CLASS_TYPES:
        classification["type"] = CLASS_TYPES[ct]
    if data.get("CLASS"):
        classification["class"] = data["CLASS"]
    order_obs = data.get("ORDER_OBS", "")
    if order_obs:
        classification["usage"] = ORDER_OBS_TYPES.get(order_obs, order_obs)
    if classification:
        code["classification"] = classification

    status = data.get("STATUS", "")
    if status:
        code["status"] = status

    definition = data.get("DefinitionDescription", "")
    if definition:
        code["definition"] = definition

    related = data.get("RELATEDNAMES_SECONDARY", "")
    if related:
        names = [n.strip() for n in related.split(";") if n.strip()]
        if names:
            code["related_names"] = names[:5]

    if panel_members:
        code["panel_members"] = panel_members

    if answer_list_data:
        answers = _format_answer_list(answer_list_data)
        if answers:
            code["answer_list"] = answers

    return _to_json(code)


def format_panel_members(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract and format panel member entries from a /panels response."""
    items = _results_list(data)
    members: list[dict[str, Any]] = []

    for item in items:
        entry: dict[str, Any] = {}
        loinc = item.get("Loinc") or item.get("LOINC_NUM") or item.get("loinc") or ""
        name = (
            item.get("LoincName")
            or item.get("LONG_COMMON_NAME")
            or item.get("loincName")
            or ""
        )
        if not loinc and not name:
            continue

        if loinc:
            entry["code"] = loinc
        if name:
            entry["name"] = name

        seq = item.get("Sequence") or item.get("sequence") or ""
        if seq:
            entry["sequence"] = seq

        opt = item.get("Optionality") or item.get("optionality") or ""
        if opt:
            entry["required"] = opt in ("R", "r")

        members.append(entry)

    return members


def format_error(message: str, context: str | None = None) -> str:
    """Format an error message as JSON."""
    error: dict[str, str] = {"error": message}
    if context:
        error["context"] = context
    return _to_json(error)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _format_answer_list(data: dict[str, Any]) -> dict[str, Any] | None:
    """Format answer list data for a LOINC code."""
    items = _results_list(data)
    if not items:
        return None

    answers: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        answer: dict[str, Any] = {
            "code": item.get("LoincAnswerCode") or item.get("answerCode") or "",
            "text": item.get("DisplayText") or item.get("displayText") or "",
            "sequence": item.get("Sequence") or item.get("sequence") or "",
        }
        answer = {k: v for k, v in answer.items() if v}
        if answer.get("code") or answer.get("text"):
            answers.append(answer)

    if not answers:
        return None

    list_id = items[0].get("ListId") or items[0].get("listId") or ""
    result: dict[str, Any] = {"answers": answers}
    if list_id:
        result["id"] = list_id
    return result


def _to_json(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False)
