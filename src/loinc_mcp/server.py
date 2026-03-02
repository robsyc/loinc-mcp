"""LOINC MCP Server.

Provides MCP tools for searching and retrieving LOINC codes
via the LOINC Search API (https://loinc.regenstrief.org/searchapi).
"""

from typing import Annotated

import httpx
from fastmcp import FastMCP

from .utils import (
    LOINC_BASE_URL,
    LOINC_TIMEOUT,
    format_code_details,
    format_error,
    format_panel_members,
    format_search_results,
    get_auth_credentials,
    is_panel,
)

mcp = FastMCP(
    "LOINC",
    instructions=(
        "Query LOINC medical terminology codes. "
        "Use `search` to find codes by text (e.g., 'glucose', 'blood pressure'). "
        "Use `get_code` for full details including panel members and answer lists."
    ),
)

client = httpx.AsyncClient(timeout=LOINC_TIMEOUT)


def _auth() -> tuple[str, str]:
    return get_auth_credentials()


async def _request(endpoint: str, params: dict[str, str | int]) -> dict:
    """Make an authenticated GET to the LOINC Search API."""
    username, password = _auth()
    resp = await client.get(
        f"{LOINC_BASE_URL}/{endpoint}",
        params=params,
        auth=(username, password),
        headers={"Accept": "application/json"},
    )
    resp.raise_for_status()
    return resp.json()


async def _search_code(code: str) -> dict | None:
    """Search for a single LOINC code and return the matching entry."""
    data = await _request("loincs", {"query": code, "rows": 5})
    items = data.get("Results") or data.get("results") or []
    for item in items:
        if item.get("LOINC_NUM") == code:
            return item
    return items[0] if items else None


async def _get_panel_members(code: str) -> list[dict]:
    """Fetch panel members via the /panels endpoint."""
    try:
        data = await _request("panels", {"query": code, "rows": 100})
        return format_panel_members(data)
    except httpx.HTTPError:
        return []


async def _get_answer_list(code: str) -> dict | None:
    """Fetch the answer list for a LOINC code."""
    try:
        return await _request("answerlists", {"LoincNumber": code})
    except httpx.HTTPError:
        return None


# ---------------------------------------------------------------------------
# MCP Tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def search(
    query: Annotated[
        str,
        "Search text, e.g. 'glucose', 'blood pressure', 'PHQ-9'. "
        "Supports field syntax: 'Component:glucose AND System:Serum'.",
    ],
    limit: Annotated[int, "Maximum results (1-100)"] = 10,
    class_type: Annotated[
        str | None,
        "Filter by class type: '1' (Lab), '2' (Clinical), '3' (Claims), '4' (Surveys)",
    ] = None,
) -> str:
    """Search LOINC codes by text. Returns matching codes with names and classifications."""
    try:
        params: dict[str, str | int] = {"query": query, "rows": min(limit, 100)}
        if class_type:
            params["CLASSTYPE"] = class_type

        data = await _request("loincs", params)
        return format_search_results(data, limit)

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            return format_error(
                "Authentication failed",
                "Check LOINC_USERNAME and LOINC_PASSWORD environment variables.",
            )
        return format_error(f"HTTP {e.response.status_code}", str(e))
    except httpx.HTTPError as e:
        return format_error("Request failed", str(e))


@mcp.tool()
async def get_code(
    code: Annotated[str, "LOINC code, e.g. '2339-0' (Glucose in Blood) or '24331-1' (Lipid Panel)"],
    include_answer_list: Annotated[
        bool,
        "Include answer options for coded observations (surveys, questionnaires)",
    ] = True,
) -> str:
    """Get full details for a LOINC code: parts, classification, and panel members if applicable."""
    try:
        loinc_data = await _search_code(code)
        if not loinc_data:
            return format_error(f"LOINC code '{code}' not found")

        panel_members = None
        if is_panel(loinc_data):
            panel_members = await _get_panel_members(code) or None

        answer_list = None
        if include_answer_list:
            answer_list = await _get_answer_list(code)

        return format_code_details(loinc_data, panel_members, answer_list)

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            return format_error(
                "Authentication failed",
                "Check LOINC_USERNAME and LOINC_PASSWORD environment variables.",
            )
        return format_error(f"HTTP {e.response.status_code}", str(e))
    except httpx.HTTPError as e:
        return format_error("Request failed", str(e))


def main():
    """Entry point for the MCP server."""
    mcp.run()
