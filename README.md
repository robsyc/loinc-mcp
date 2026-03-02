# LOINC MCP Server

A [Model Context Protocol](https://modelcontextprotocol.io/) server for querying [LOINC](https://loinc.org/) (Logical Observation Identifiers Names and Codes) terminology through the LOINC Search API.

## Available Tools

| Tool | Description |
|------|-------------|
| `search` | Search LOINC codes by text query. Returns codes, names, and classifications. |
| `get_code` | Get full details for a LOINC code: parts, classification, units, panel members, and answer options. |

## Quick Start

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- A LOINC account (free at [loinc.org/join](https://loinc.org/join))

### Install as a uv tool

```bash
git clone https://github.com/robsyc/loinc-mcp && cd loinc-mcp
uv tool install .
```

Then add to your `.cursor/mcp.json` or Claude Desktop config:

```json
{
  "mcpServers": {
    "loinc-mcp": {
      "command": "loinc-mcp",
      "env": {
        "LOINC_USERNAME": "your-username",
        "LOINC_PASSWORD": "your-password"
      }
    }
  }
}
```

### Run with uvx

```json
{
  "mcpServers": {
    "LOINC": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/robsyc/loinc-mcp", "loinc-mcp"],
      "env": {
        "LOINC_USERNAME": "your-username",
        "LOINC_PASSWORD": "your-password"
      }
    }
  }
}
```

## Usage Examples

> "Search for LOINC codes related to glucose"

> "Get the full details for LOINC code 2339-0"

> "Look up the lipid panel 24331-1 and show me its members"

## API Details

This server wraps the [LOINC Search API](https://loinc.org/kb/using-loinc-api/):

- **Base URL**: `https://loinc.regenstrief.org/searchapi/`
- **Auth**: HTTP Basic Authentication (LOINC account credentials)
- **Endpoints used**: `/loincs` (search) and FHIR `/Questionnaire/{code}` (panels)

### LOINC Class Types

| Code | Type |
|------|------|
| 1 | Laboratory |
| 2 | Clinical |
| 3 | Claims attachments |
| 4 | Surveys |

### Panel Detection

When `get_code` is called for a panel (detected via the `CLASS` field), panel members are automatically fetched from the FHIR Questionnaire endpoint. For survey panels, answer options are included inline with each member.

## Development

```bash
uv sync --group dev

# Lint
uv run ruff check src/ tests/

# Tests
uv run pytest tests/ -v

# MCP Inspector
LOINC_USERNAME=your-user LOINC_PASSWORD=your-pass uv run fastmcp dev inspector src/loinc_mcp/server.py:mcp
```

## Acknowledgments

- [LOINC](https://loinc.org/) for the terminology and API
- [Regenstrief Institute](https://www.regenstrief.org/) for maintaining LOINC
- [FastMCP](https://gofastmcp.com/) for the MCP framework
