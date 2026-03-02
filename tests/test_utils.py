"""Tests for loinc_mcp.utils — pure formatter and helper functions."""

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
# Sample data (mirrors LOINC Search API response shapes)
# ---------------------------------------------------------------------------

GLUCOSE_ITEM = {
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
    "STATUS": "ACTIVE",
    "ORDER_OBS": "Both",
    "DefinitionDescription": "",
    "RELATEDNAMES_SECONDARY": "Glucose; Gluc; Sugar; Blood sugar",
}

LIPID_PANEL_ITEM = {
    "LOINC_NUM": "24331-1",
    "LONG_COMMON_NAME": "Lipid 1996 panel - Serum or Plasma",
    "SHORTNAME": "Lipid 1996 Pnl SerPl",
    "COMPONENT": "Lipid 1996 panel",
    "PROPERTY": "-",
    "TIME_ASPCT": "Pt",
    "SYSTEM": "Ser/Plas",
    "SCALE_TYP": "-",
    "METHOD_TYP": "",
    "CLASS": "PANEL.CHEM",
    "CLASSTYPE": "1",
    "STATUS": "ACTIVE",
    "ORDER_OBS": "Order",
}

DEPRECATED_ITEM = {
    "LOINC_NUM": "9999-9",
    "LONG_COMMON_NAME": "Old Test",
    "COMPONENT": "OldComp",
    "CLASS": "CHEM",
    "CLASSTYPE": "1",
    "STATUS": "DEPRECATED",
}

SEARCH_RESPONSE = {"Results": [GLUCOSE_ITEM, LIPID_PANEL_ITEM, DEPRECATED_ITEM]}

PANEL_MEMBERS_RESPONSE = {
    "Results": [
        {
            "Loinc": "2093-3",
            "LoincName": "Cholesterol [Mass/volume] in Serum or Plasma",
            "Sequence": "1",
            "Optionality": "R",
        },
        {
            "Loinc": "2571-8",
            "LoincName": "Triglyceride [Mass/volume] in Serum or Plasma",
            "Sequence": "2",
            "Optionality": "R",
        },
        {
            "Loinc": "2085-9",
            "LoincName": "Cholesterol in HDL [Mass/volume] in Serum or Plasma",
            "Sequence": "3",
            "Optionality": "O",
        },
    ]
}

ANSWER_LIST_RESPONSE = {
    "Results": [
        {
            "ListId": "LL358-3",
            "LoincAnswerCode": "LA6568-5",
            "DisplayText": "Yes",
            "Sequence": "1",
        },
        {
            "ListId": "LL358-3",
            "LoincAnswerCode": "LA6569-3",
            "DisplayText": "No",
            "Sequence": "2",
        },
    ]
}


# ---------------------------------------------------------------------------
# Auth credentials
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

    def test_api_key_with_colon_in_password(self, monkeypatch):
        monkeypatch.delenv("LOINC_USERNAME", raising=False)
        monkeypatch.delenv("LOINC_PASSWORD", raising=False)
        monkeypatch.setenv("LOINC_API_KEY", "user:pass:word")
        assert get_auth_credentials() == ("user", "pass:word")

    def test_missing_credentials(self, monkeypatch):
        monkeypatch.delenv("LOINC_USERNAME", raising=False)
        monkeypatch.delenv("LOINC_PASSWORD", raising=False)
        monkeypatch.delenv("LOINC_API_KEY", raising=False)
        with pytest.raises(RuntimeError, match="credentials not configured"):
            get_auth_credentials()

    def test_username_without_password(self, monkeypatch):
        monkeypatch.setenv("LOINC_USERNAME", "alice")
        monkeypatch.setenv("LOINC_PASSWORD", "")
        monkeypatch.delenv("LOINC_API_KEY", raising=False)
        with pytest.raises(RuntimeError):
            get_auth_credentials()


# ---------------------------------------------------------------------------
# is_panel
# ---------------------------------------------------------------------------


class TestIsPanel:
    def test_panel_class(self):
        assert is_panel({"CLASS": "PANEL.CHEM"}) is True
        assert is_panel({"CLASS": "PANEL.OBS"}) is True

    def test_non_panel(self):
        assert is_panel({"CLASS": "CHEM"}) is False
        assert is_panel({"CLASS": ""}) is False
        assert is_panel({}) is False


# ---------------------------------------------------------------------------
# format_search_results
# ---------------------------------------------------------------------------


class TestFormatSearchResults:
    def test_basic(self):
        result = json.loads(format_search_results(SEARCH_RESPONSE, 10))
        assert result["total"] == 3
        assert len(result["results"]) == 3

        glucose = result["results"][0]
        assert glucose["code"] == "2339-0"
        assert glucose["name"] == "Glucose [Mass/volume] in Blood"
        assert glucose["class_type"] == "Laboratory"
        assert "status" not in glucose  # ACTIVE is omitted

    def test_panel_flagged(self):
        result = json.loads(format_search_results(SEARCH_RESPONSE, 10))
        panel = result["results"][1]
        assert panel["is_panel"] is True

    def test_deprecated_status(self):
        result = json.loads(format_search_results(SEARCH_RESPONSE, 10))
        deprecated = result["results"][2]
        assert deprecated["status"] == "DEPRECATED"

    def test_limit(self):
        result = json.loads(format_search_results(SEARCH_RESPONSE, 1))
        assert len(result["results"]) == 1
        assert result["total"] == 3  # total reflects actual API count

    def test_empty_results(self):
        result = json.loads(format_search_results({"Results": []}, 10))
        assert result["results"] == []
        assert result["total"] == 0

    def test_lowercase_key(self):
        data = {"results": [GLUCOSE_ITEM]}
        result = json.loads(format_search_results(data, 10))
        assert len(result["results"]) == 1


# ---------------------------------------------------------------------------
# format_code_details
# ---------------------------------------------------------------------------


class TestFormatCodeDetails:
    def test_basic_code(self):
        result = json.loads(format_code_details(GLUCOSE_ITEM))
        assert result["code"] == "2339-0"
        assert result["parts"]["component"] == "Glucose"
        assert result["parts"]["system"] == "Bld"
        assert result["classification"]["type"] == "Laboratory"
        assert result["classification"]["usage"] == "Orderable and observable"
        assert result["status"] == "ACTIVE"

    def test_empty_fields_omitted(self):
        result = json.loads(format_code_details(GLUCOSE_ITEM))
        assert "method" not in result["parts"]
        assert "definition" not in result

    def test_related_names(self):
        result = json.loads(format_code_details(GLUCOSE_ITEM))
        assert "related_names" in result
        assert "Glucose" in result["related_names"]

    def test_related_names_capped_at_5(self):
        data = {**GLUCOSE_ITEM, "RELATEDNAMES_SECONDARY": "a;b;c;d;e;f;g"}
        result = json.loads(format_code_details(data))
        assert len(result["related_names"]) == 5

    def test_with_panel_members(self):
        members = [{"code": "2093-3", "name": "Cholesterol"}]
        result = json.loads(format_code_details(LIPID_PANEL_ITEM, panel_members=members))
        assert result["panel_members"] == members

    def test_with_answer_list(self):
        result = json.loads(
            format_code_details(GLUCOSE_ITEM, answer_list_data=ANSWER_LIST_RESPONSE)
        )
        assert result["answer_list"]["id"] == "LL358-3"
        assert len(result["answer_list"]["answers"]) == 2
        assert result["answer_list"]["answers"][0]["text"] == "Yes"

    def test_no_optional_extras(self):
        result = json.loads(format_code_details(GLUCOSE_ITEM))
        assert "panel_members" not in result
        assert "answer_list" not in result


# ---------------------------------------------------------------------------
# format_panel_members
# ---------------------------------------------------------------------------


class TestFormatPanelMembers:
    def test_basic(self):
        members = format_panel_members(PANEL_MEMBERS_RESPONSE)
        assert len(members) == 3
        assert members[0]["code"] == "2093-3"
        assert members[0]["required"] is True
        assert members[2]["required"] is False

    def test_empty(self):
        assert format_panel_members({"Results": []}) == []
        assert format_panel_members({}) == []

    def test_lowercase_keys(self):
        data = {
            "results": [
                {"loinc": "1234-5", "loincName": "Test", "sequence": "1", "optionality": "R"}
            ]
        }
        members = format_panel_members(data)
        assert len(members) == 1
        assert members[0]["code"] == "1234-5"


# ---------------------------------------------------------------------------
# format_error
# ---------------------------------------------------------------------------


class TestFormatError:
    def test_simple(self):
        result = json.loads(format_error("Something went wrong"))
        assert result["error"] == "Something went wrong"
        assert "context" not in result

    def test_with_context(self):
        result = json.loads(format_error("Auth failed", "Check env vars"))
        assert result["error"] == "Auth failed"
        assert result["context"] == "Check env vars"
