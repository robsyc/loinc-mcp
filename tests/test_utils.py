"""Unit tests for loinc_mcp.utils — pure functions, no API calls."""

import json

import pytest

from loinc_mcp.utils import (
    format_code_details,
    format_error,
    format_panel_members,
    format_search_results,
    get_auth_credentials,
    is_panel,
)

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


class TestGetAuthCredentials:
    def test_username_password(self, monkeypatch):
        monkeypatch.setenv("LOINC_USERNAME", "alice")
        monkeypatch.setenv("LOINC_PASSWORD", "secret")
        monkeypatch.delenv("LOINC_API_KEY", raising=False)
        assert get_auth_credentials() == ("alice", "secret")

    def test_api_key(self, monkeypatch):
        monkeypatch.delenv("LOINC_USERNAME", raising=False)
        monkeypatch.delenv("LOINC_PASSWORD", raising=False)
        monkeypatch.setenv("LOINC_API_KEY", "bob:pass123")
        assert get_auth_credentials() == ("bob", "pass123")

    def test_missing_credentials(self, monkeypatch):
        monkeypatch.delenv("LOINC_USERNAME", raising=False)
        monkeypatch.delenv("LOINC_PASSWORD", raising=False)
        monkeypatch.delenv("LOINC_API_KEY", raising=False)
        with pytest.raises(RuntimeError, match="credentials not configured"):
            get_auth_credentials()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class TestIsPanel:
    def test_panel_class(self):
        assert is_panel({"CLASS": "PANEL.CHEM"}) is True
        assert is_panel({"CLASS": "PANEL"}) is True

    def test_non_panel(self):
        assert is_panel({"CLASS": "CHEM"}) is False
        assert is_panel({}) is False


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------


SAMPLE_SEARCH_RESPONSE = {
    "Results": [
        {
            "LOINC_NUM": "2339-0",
            "LONG_COMMON_NAME": "Glucose [Mass/volume] in Blood",
            "COMPONENT": "Glucose",
            "SYSTEM": "Bld",
            "CLASS": "CHEM",
            "CLASSTYPE": "1",
            "STATUS": "ACTIVE",
        },
        {
            "LOINC_NUM": "24331-1",
            "LONG_COMMON_NAME": "Lipid 1996 panel - Serum or Plasma",
            "COMPONENT": "Lipid 1996 panel",
            "SYSTEM": "Ser/Plas",
            "CLASS": "PANEL.CHEM",
            "CLASSTYPE": "1",
            "STATUS": "ACTIVE",
        },
    ],
}

SAMPLE_CODE_DATA = {
    "LOINC_NUM": "2339-0",
    "LONG_COMMON_NAME": "Glucose [Mass/volume] in Blood",
    "SHORTNAME": "Glucose Bld-mCnc",
    "COMPONENT": "Glucose",
    "PROPERTY": "MCnc",
    "TIME_ASPCT": "Pt",
    "SYSTEM": "Bld",
    "SCALE_TYP": "Qn",
    "METHOD_TYP": "",
    "CLASS": "CHEM",
    "CLASSTYPE": "1",
    "ORDER_OBS": "Both",
    "STATUS": "ACTIVE",
    "EXAMPLE_UNITS": "mg/dL",
    "EXAMPLE_UCUM_UNITS": "mg/dL",
    "DefinitionDescription": "",
    "RELATEDNAMES2": "Blood sugar; Glucs",
}


class TestFormatSearchResults:
    def test_basic_results(self):
        result = json.loads(format_search_results(SAMPLE_SEARCH_RESPONSE, 10))
        assert result["total"] == 2
        assert len(result["results"]) == 2
        assert result["results"][0]["code"] == "2339-0"
        assert result["results"][0]["class_type"] == "Laboratory"

    def test_panel_flagged(self):
        result = json.loads(format_search_results(SAMPLE_SEARCH_RESPONSE, 10))
        panel = result["results"][1]
        assert panel["is_panel"] is True

    def test_limit_applied(self):
        result = json.loads(format_search_results(SAMPLE_SEARCH_RESPONSE, 1))
        assert len(result["results"]) == 1

    def test_empty_response(self):
        result = json.loads(format_search_results({"Results": []}, 10))
        assert result["results"] == []
        assert result["total"] == 0

    def test_inactive_status_shown(self):
        data = {"Results": [{"LOINC_NUM": "X", "STATUS": "DEPRECATED", "LONG_COMMON_NAME": "X"}]}
        result = json.loads(format_search_results(data, 10))
        assert result["results"][0]["status"] == "DEPRECATED"

    def test_active_status_omitted(self):
        data = {"Results": [{"LOINC_NUM": "X", "STATUS": "ACTIVE", "LONG_COMMON_NAME": "X"}]}
        result = json.loads(format_search_results(data, 10))
        assert "status" not in result["results"][0]


class TestFormatCodeDetails:
    def test_basic_fields(self):
        result = json.loads(format_code_details(SAMPLE_CODE_DATA))
        assert result["code"] == "2339-0"
        assert result["name"] == "Glucose [Mass/volume] in Blood"
        assert result["short_name"] == "Glucose Bld-mCnc"
        assert result["parts"]["component"] == "Glucose"
        assert result["classification"]["type"] == "Laboratory"
        assert result["classification"]["usage"] == "Orderable and observable"

    def test_units_included(self):
        result = json.loads(format_code_details(SAMPLE_CODE_DATA))
        assert result["units"] == "mg/dL"

    def test_units_omitted_when_absent(self):
        data = {**SAMPLE_CODE_DATA, "EXAMPLE_UNITS": "", "EXAMPLE_UCUM_UNITS": ""}
        result = json.loads(format_code_details(data))
        assert "units" not in result

    def test_empty_method_omitted(self):
        result = json.loads(format_code_details(SAMPLE_CODE_DATA))
        assert "method" not in result["parts"]

    def test_related_names_truncated(self):
        result = json.loads(format_code_details(SAMPLE_CODE_DATA))
        assert result["related_names"] == ["Blood sugar", "Glucs"]

    def test_panel_members_included(self):
        members = [{"code": "2093-3", "name": "Cholesterol"}]
        result = json.loads(format_code_details(SAMPLE_CODE_DATA, panel_members=members))
        assert result["panel_members"] == members


class TestFormatPanelMembers:
    def test_extracts_members(self):
        fhir = {
            "item": [
                {
                    "code": [{"code": "2093-3", "display": "Cholesterol"}],
                    "text": "Cholest SerPl-mCnc",
                    "required": True,
                },
                {
                    "code": [{"code": "2571-8", "display": "Triglycerides"}],
                    "required": False,
                },
            ]
        }
        members = format_panel_members(fhir)
        assert len(members) == 2
        assert members[0] == {"code": "2093-3", "name": "Cholesterol", "required": True}
        assert members[1] == {"code": "2571-8", "name": "Triglycerides", "required": False}

    def test_extracts_answer_options(self):
        fhir = {
            "item": [
                {
                    "code": [{"code": "44250-9", "display": "Little interest"}],
                    "type": "choice",
                    "answerOption": [
                        {"valueCoding": {"code": "LA6568-5", "display": "Not at all"}},
                        {"valueCoding": {"code": "LA6569-3", "display": "Several days"}},
                    ],
                },
            ]
        }
        members = format_panel_members(fhir)
        assert len(members) == 1
        assert members[0]["code"] == "44250-9"
        assert len(members[0]["answers"]) == 2
        assert members[0]["answers"][0] == {"code": "LA6568-5", "text": "Not at all"}

    def test_no_answers_when_absent(self):
        fhir = {"item": [{"code": [{"code": "X", "display": "Y"}]}]}
        members = format_panel_members(fhir)
        assert "answers" not in members[0]

    def test_skips_entries_without_code(self):
        fhir = {"item": [{"code": [], "text": "No code"}]}
        assert format_panel_members(fhir) == []

    def test_empty_items(self):
        assert format_panel_members({"item": []}) == []
        assert format_panel_members({}) == []


class TestFormatError:
    def test_simple_error(self):
        result = json.loads(format_error("Not found"))
        assert result == {"error": "Not found"}

    def test_error_with_context(self):
        result = json.loads(format_error("Auth failed", "Check credentials"))
        assert result["error"] == "Auth failed"
        assert result["context"] == "Check credentials"
