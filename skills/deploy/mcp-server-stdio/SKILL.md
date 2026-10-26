---
name: MCP server over stdio
description: fieldlens_mcp.py — 5 narzedzi, zero zaleznosci, JSON-RPC 2.0 po stdio.
---

# MCP server over stdio

`fieldlens_mcp.py` — samodzielny serwer, **bez SDK** (import `mcp` kolidowal
z lokalnym katalogiem `mcp/`). Protokol: JSON-RPC 2.0, `2024-11-05`.

## Narzedzia
| Nazwa | Rola |
|---|---|
| `inspect` | inspekcja jednym zestawem progow |
| `tune(channel, factor 0.5..2.0)` | reczna korekta progu |
| `explain(region)` | uzasadnienie kandydata |
| `request_rescan(reason)` | jawne "nie wiem" |
| `agent_inspect` | pelna petla active perception |

## Dlaczego bez SDK
`pip install mcp` blokowane przez PEP 668, a `import mcp` lapal lokalny katalog
projektu. Recznie obsluzone: `initialize`, `tools/list`, `tools/call`,
`notifications/initialized`, `ping`.

## Dowod
Uruchomienie `fieldlens_mcp.py` daje `INIT {'name': 'fieldlens', 'version': '1.0.0'} 2024-11-05`
i katalog 5 narzedzi.
