"""Tests for loinc_mcp.server — tool functions with mocked HTTP."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from loinc_mcp.server import get_code, search

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

GLUCOSE_ITEM = {
    "LOINC_NUM": "2339-0",
    "LONG_COMMON_NAME": "Glucose [Mass/volume] in Blood",
    "COMPONENT": "Glucose",
    "SYSTEM": "Bld",
    "CLASS": "CHEM",
    "CLASSTYPE": "1",
    "STATUS": "ACTIVE",
    "ORDER_OBS": "Both",
    "PROPERTY": "MCnc",
    "TIME_ASPCT": "Pt",
    "SCALE_TYP": "Qn",
}

LIPID_PANEL_ITEM = {
    "LOINC_NUM": "24331-1",
    "LONG_COMMON_NAME": "Lipid 1996 panel - Serum or Plasma",
    "COMPONENT": "Lipid 1996 panel",
    "SYSTEM": "Ser/Plas",
    "CLASS": "PANEL.CHEM",
    "CLASSTYPE": "1",
    "STATUS": "ACTIVE",
    "ORDER_OBS": "Order",
    "PROPERTY": "-",
    "TIME_ASPCT": "Pt",
    "SCALE_TYP": "-",
}

PANEL_MEMBERS = {
    "Results": [
        {"Loinc": "2093-3", "LoincName": "Cholesterol", "Sequence": "1", "Optionality": "R"},
        {"Loinc": "2571-8", "LoincName": "Triglyceride", "Sequence": "2", "Optionality": "R"},
    ]
}


def _mock_auth():
    return ("user", "pass")


def _make_response(data: dict, status_code: int = 200) -> MagicMock:
    """Create a mock httpx.Response with sync json() and raise_for_status()."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = data
    return resp


def _make_401_response() -> MagicMock:
    resp = MagicMock()
    resp.status_code = 401
    resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Unauthorized", request=MagicMock(), response=resp
    )
    return resp


# ---------------------------------------------------------------------------
# search tool
# ---------------------------------------------------------------------------


class TestSearchTool:
    @pytest.fixture(autouse=True)
    def _patch_auth(self):
        with patch("loinc_mcp.server._auth", side_effect=_mock_auth):
            yield

    async def test_search_basic(self):
        resp = _make_response({"Results": [GLUCOSE_ITEM]})

        with patch.object(httpx.AsyncClient, "get", AsyncMock(return_value=resp)) as mock_get:
            result = json.loads(await search("glucose"))
            assert result["total"] == 1
            assert result["results"][0]["code"] == "2339-0"
            mock_get.assert_called_once()

    async def test_search_with_class_type(self):
        resp = _make_response({"Results": [GLUCOSE_ITEM]})

        with patch.object(httpx.AsyncClient, "get", AsyncMock(return_value=resp)) as mock_get:
            result = json.loads(await search("glucose", class_type="1"))
            assert result["total"] == 1
            call_kwargs = mock_get.call_args
            assert call_kwargs.kwargs["params"]["CLASSTYPE"] == "1"

    async def test_search_auth_error(self):
        resp = _make_401_response()

        with patch.object(httpx.AsyncClient, "get", AsyncMock(return_value=resp)):
            result = json.loads(await search("glucose"))
            assert "error" in result
            assert "Authentication" in result["error"]

    async def test_search_limit_capped(self):
        resp = _make_response({"Results": []})

        with patch.object(httpx.AsyncClient, "get", AsyncMock(return_value=resp)) as mock_get:
            await search("glucose", limit=200)
            call_kwargs = mock_get.call_args
            assert call_kwargs.kwargs["params"]["rows"] == 100


# ---------------------------------------------------------------------------
# get_code tool
# ---------------------------------------------------------------------------


class TestGetCodeTool:
    @pytest.fixture(autouse=True)
    def _patch_auth(self):
        with patch("loinc_mcp.server._auth", side_effect=_mock_auth):
            yield

    async def test_get_code_basic(self):
        loinc_resp = _make_response({"Results": [GLUCOSE_ITEM]})
        answer_resp = _make_response({"Results": []})

        async def mock_get(*args, **kwargs):
            url = str(args[0]) if args else str(kwargs.get("url", ""))
            if "answerlists" in url:
                return answer_resp
            return loinc_resp

        with patch.object(httpx.AsyncClient, "get", side_effect=mock_get):
            result = json.loads(await get_code("2339-0"))
            assert result["code"] == "2339-0"
            assert result["parts"]["component"] == "Glucose"
            assert "panel_members" not in result

    async def test_get_code_not_found(self):
        resp = _make_response({"Results": []})

        with patch.object(httpx.AsyncClient, "get", AsyncMock(return_value=resp)):
            result = json.loads(await get_code("0000-0"))
            assert "error" in result

    async def test_get_panel_with_members(self):
        loinc_resp = _make_response({"Results": [LIPID_PANEL_ITEM]})
        panel_resp = _make_response(PANEL_MEMBERS)
        answer_resp = _make_response({"Results": []})

        async def mock_get(*args, **kwargs):
            url = str(args[0]) if args else str(kwargs.get("url", ""))
            if "panels" in url:
                return panel_resp
            if "answerlists" in url:
                return answer_resp
            return loinc_resp

        with patch.object(httpx.AsyncClient, "get", side_effect=mock_get):
            result = json.loads(await get_code("24331-1"))
            assert result["code"] == "24331-1"
            assert "panel_members" in result
            assert len(result["panel_members"]) == 2
            assert result["panel_members"][0]["code"] == "2093-3"

    async def test_get_code_auth_error(self):
        resp = _make_401_response()

        with patch.object(httpx.AsyncClient, "get", AsyncMock(return_value=resp)):
            result = json.loads(await get_code("2339-0"))
            assert "error" in result
            assert "Authentication" in result["error"]

    async def test_get_code_without_answer_list(self):
        resp = _make_response({"Results": [GLUCOSE_ITEM]})

        with patch.object(httpx.AsyncClient, "get", AsyncMock(return_value=resp)):
            result = json.loads(await get_code("2339-0", include_answer_list=False))
            assert result["code"] == "2339-0"
            assert "answer_list" not in result
