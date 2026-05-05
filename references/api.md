# IETF Author Tools API Reference

Base URL: `https://author-tools.ietf.org`

Optional auth: `X-API-KEY` header (generate at https://datatracker.ietf.org/accounts/apikey).

---

## GET /api/idnits

Run idnits on a draft by URL.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `url` | string | yes | Draft URL (txt, xml, md) |
| `verbose` | integer 0–2 | no | Verbosity level (default 0) |
| `submitcheck` | string | no | Set to run submission checks |
| `hidetext` | string | no | Set to omit draft text from output |
| `year` | integer | no | Override boilerplate year |

**Response 200**: `text/plain` — idnits output

---

## POST /api/idnits

Same as GET but accepts a file upload (multipart/form-data).

Fields: `file` (binary), `verbose`, `submitcheck`, `hidetext`, `year`.

---

## POST /api/validate

Full validation: xml2rfc + idnits + non-ASCII check.

Field: `file` (binary — txt, xml, md).

**Response 200** (JSON):
```json
{
  "errors": ["..."],
  "warnings": ["..."],
  "idnits": "...",
  "non_ascii": "...",
  "bare_unicode": ["..."]
}
```

---

## GET /api/abnf/extract

Extract ABNF from a draft.

| Parameter | Description |
|---|---|
| `url` | Document URL |
| `doc` | Document name (alternative to url) |

**Response 200**: `text/plain` — raw ABNF text (empty if none found)

---

## POST /api/abnf/parse

Parse ABNF text with BAP.

Field: `input` (string — ABNF text).

**Response 200** (JSON):
```json
{
  "errors": "...",
  "abnf": "..."
}
```

---

## GET /api/iddiff

Diff two drafts.

| Parameter | Description |
|---|---|
| `doc_1` | First document name |
| `doc_2` | Second document name (optional; inferred if omitted) |
| `url_1` / `url_2` | URLs instead of names |
| `wdiff` | Set for HTML wdiff output |
| `abdiff` | Set for before/after diff output |
| `table` | Set for HTML table output |
| `latest` | Set to compare doc_1 against its latest datatracker version |

**Response 200**: HTML or text diff

---

## POST /api/render/text

Convert draft to plain text.

Field: `file` (binary).

**Response 200** (JSON): `{ "url": "...", "errors": [...], "warnings": [...] }`

---

## POST /api/render/xml

Convert draft to xml2rfc v3 XML. Same interface as `/api/render/text`.

---

## GET /api/version

Returns tool version information (xml2rfc, idnits, kramdown-rfc, etc.).
