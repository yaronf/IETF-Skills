# rfc-prepub-check

A Cowork skill that runs the standard IETF Internet-Draft prepublication checks using the [IETF Author Tools API](https://author-tools.ietf.org).

## What it checks

| # | Check | Tool |
|---|---|---|
| 1 | **idnits** — boilerplate, line length, references, formatting | idnits (submission-check mode) |
| 2 | **Full validation** — structural errors and warnings | xml2rfc + idnits |
| 3 | **ABNF syntax** — extracts and validates any ABNF grammars | BAP |
| 4 | **iddiff** — diff against the previous version of the draft | rfcdiff/iddiff |

## Installation as a Cowork skill

Download `rfc-prepub-check.skill` from the [Releases](../../releases) page and open it in the Claude desktop app. Claude will automatically invoke it when you ask to check or validate an Internet-Draft.

Or clone and point Claude at the local directory:

```bash
git clone https://github.com/yaronf/rfc-prepub-check
```

## Standalone use (no Cowork)

The script works independently:

```bash
# Install dependency
pip install requests

# Check a draft by name (fetched from IETF archive)
python scripts/run_checks.py draft-ietf-oauth-rfc8725bis-04

# Check a local file
python scripts/run_checks.py ./my-draft.xml --skip-iddiff

# Check by URL with maximum verbosity
python scripts/run_checks.py https://www.ietf.org/archive/id/draft-ietf-oauth-rfc8725bis-04.txt --verbose 2
```

### Options

| Flag | Effect |
|---|---|
| `--skip-iddiff` | Skip diff against previous version |
| `--skip-abnf` | Skip ABNF extraction/parsing |
| `--no-submit-check` | Run idnits in normal mode (not submission-check mode) |
| `--verbose N` | idnits verbosity 0–2 (default 1) |

## Requirements

- Python 3.8+
- `requests` (`pip install requests`)
- Internet access to `author-tools.ietf.org`

## How it works

All checks are delegated to the [IETF Author Tools API](https://author-tools.ietf.org) — no local tool installation required. See [`references/api.md`](references/api.md) for the full API spec.

## License

MIT
