"""Utilities for LOINC MCP Server.

Response formatters, API helpers, and constants for the LOINC Search API.
"""

import json
import os
from typing import Any

LOINC_BASE_URL = "https://loinc.regenstrief.org/searchapi"
FHIR_BASE_URL = "https://fhir.loinc.org"
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

    units = data.get("EXAMPLE_UCUM_UNITS") or data.get("EXAMPLE_UNITS") or ""
    if units:
        code["units"] = units

    definition = data.get("DefinitionDescription", "")
    if definition:
        code["definition"] = definition

    related = data.get("RELATEDNAMES2") or data.get("RELATEDNAMES_SECONDARY") or ""
    if related:
        names = [n.strip() for n in related.split(";") if n.strip()]
        if names:
            code["related_names"] = names[:5]

    if panel_members:
        code["panel_members"] = panel_members

    return _to_json(code)


def format_panel_members(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract panel member entries from a FHIR Questionnaire response.

    Also extracts inline answer options when present (e.g. survey items).
    """
    items = data.get("item", [])
    members: list[dict[str, Any]] = []

    for item in items:
        codes = item.get("code", [])
        if not codes:
            continue
        code = codes[0].get("code", "")
        name = codes[0].get("display", "") or item.get("text", "")
        if not code:
            continue

        entry: dict[str, Any] = {"code": code, "name": name}
        if item.get("required") is not None:
            entry["required"] = item["required"]

        answer_opts = item.get("answerOption", [])
        if answer_opts:
            answers = []
            for opt in answer_opts:
                vc = opt.get("valueCoding", {})
                if vc.get("code") or vc.get("display"):
                    answers.append({"code": vc.get("code", ""), "text": vc.get("display", "")})
            if answers:
                entry["answers"] = answers

        members.append(entry)

    return members


def format_error(message: str, context: str | None = None) -> str:
    """Format an error message as JSON."""
    error: dict[str, str] = {"error": message}
    if context:
        error["context"] = context
    return _to_json(error)


def _to_json(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False)
