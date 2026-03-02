"""Integration tests — calls the real LOINC Search API.

Requires LOINC_USERNAME and LOINC_PASSWORD (set in .env or CI secrets).
Skipped automatically when credentials are unavailable.
"""

import json
import os

import pytest

from loinc_mcp.server import get_code, search

pytestmark = pytest.mark.skipif(
    not os.environ.get("LOINC_USERNAME") or not os.environ.get("LOINC_PASSWORD"),
    reason="LOINC credentials not set",
)


class TestSearch:
    async def test_finds_glucose_codes(self):
        raw = await search("glucose")
        result = json.loads(raw)
        assert result["total"] > 0
        names = [r.get("name", "").lower() for r in result["results"]]
        assert any("glucose" in n for n in names)
        assert all("code" in r and "component" in r for r in result["results"])

    async def test_search_result_structure(self):
        raw = await search("hemoglobin", limit=3)
        result = json.loads(raw)
        assert result["total"] > 0
        assert len(result["results"]) <= 3
        first = result["results"][0]
        assert "code" in first
        assert "name" in first
        assert "class" in first or "class_type" in first

    async def test_panels_flagged_in_results(self):
        raw = await search("lipid panel")
        result = json.loads(raw)
        assert result["total"] > 0
        panels = [r for r in result["results"] if r.get("is_panel")]
        assert len(panels) > 0


class TestGetCode:
    async def test_glucose_details(self):
        raw = await get_code("2339-0")
        result = json.loads(raw)
        assert result["code"] == "2339-0"
        assert "glucose" in result["name"].lower()
        assert result["parts"]["component"] == "Glucose"
        assert result["parts"]["system"] == "Bld"
        assert result["parts"]["property"] == "MCnc"
        assert result["parts"]["scale"] == "Qn"
        assert result["classification"]["type"] == "Laboratory"
        assert result["classification"]["class"] == "CHEM"
        assert result["units"] == "mg/dL"
        assert result["status"] == "ACTIVE"

    async def test_lipid_panel_with_members(self):
        raw = await get_code("24331-1")
        result = json.loads(raw)
        assert result["code"] == "24331-1"
        assert "lipid" in result["name"].lower()
        assert "panel_members" in result
        assert len(result["panel_members"]) > 0
        member_codes = [m["code"] for m in result["panel_members"]]
        assert "2093-3" in member_codes  # Cholesterol
        assert "2571-8" in member_codes  # Triglycerides
        assert "2085-9" in member_codes  # HDL
        required = [m for m in result["panel_members"] if m.get("required") is True]
        assert len(required) >= 3

    async def test_not_found(self):
        raw = await get_code("0000-0")
        result = json.loads(raw)
        assert "error" in result
