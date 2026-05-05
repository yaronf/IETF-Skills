---
name: rfc-prepub-check
description: Run IETF Internet-Draft prepublication checks. Use this whenever the user wants to check, validate, or test an Internet-Draft before submission or publication — covering idnits nits checks, xml2rfc validation, and ABNF syntax checking. Trigger on phrases like "check my draft", "run idnits", "run nits", "prepub checks", "validate my RFC draft", "check draft-*", "nits check", "is my draft ready to submit", or any mention of checking an Internet-Draft for IETF submission readiness.
---

# RFC Prepublication Checks

This skill runs the standard suite of IETF prepublication checks on an Internet-Draft, using the [IETF Author Tools API](https://author-tools.ietf.org). It covers everything authors are expected to verify before submitting or publishing a draft.

## Checks performed (in order)

1. **idnits** — The canonical IETF nits checker. Flags formatting issues, boilerplate problems, missing required sections, stale references, line-length violations, and more. Run in submission-check mode by default so the output mirrors what the datatracker submission tool will see.
2. **Full validation** (`/api/validate`) — Runs xml2rfc structural validation plus idnits together, and also reports non-ASCII character usage.
3. **ABNF syntax check** — Extracts any ABNF grammars from the draft and validates them with BAP. Skipped silently if no ABNF is found.
4. **Downref check** — Fetches normative references from the IETF Datatracker, identifies any at lower maturity level (Informational, Experimental, Historic) per RFC 3967/RFC 8067, and checks whether they are already listed in the downref registry.
5. **Normative reference status** — Flags any normative reference that is an active Internet-Draft rather than a published RFC, and reports its current datatracker state.

## Setup

Install the one Python dependency if not already present:

```bash
pip install requests --break-system-packages
```

## Running checks

Use the bundled script `scripts/run_checks.py`. The first argument is the draft identifier, which can be:

- A **draft name**: `draft-ietf-oauth-rfc8725bis-04`
- A **full URL**: `https://www.ietf.org/archive/id/draft-ietf-oauth-rfc8725bis-04.txt`
- A **local file path**: `/path/to/my-draft.xml`

```bash
python scripts/run_checks.py draft-ietf-oauth-rfc8725bis-04
```

### Options

| Flag | Effect |
|---|---|
| `--skip-abnf` | Skip ABNF extraction and parsing |
| `--skip-refs` | Skip downref and reference status checks (steps 4–5) |
| `--no-submit-check` | Run idnits in normal mode rather than submission-check mode |
| `--verbose N` | idnits verbosity level 0–2 (default 1) |

## Interpreting and presenting results

After running the script, present the findings clearly:

1. **Lead with the idnits summary** — idnits always ends with a line like `"  -- 0 errors, 3 warnings, 1 comment."` Quote it directly.
2. **Errors are blockers** — list each one; the draft cannot be submitted until resolved.
3. **Warnings are important but non-blocking** — group by type if there are many.
4. **ABNF** — confirm it parsed cleanly, or list any grammar errors.
5. **Downrefs** — if any are flagged and not in the downref registry, the shepherd must note them explicitly in the Last Call announcement (RFC 8067). If already in the registry, no action needed.
6. **Ref status** — any normative reference to an unfinished draft is a potential blocker; flag it for the shepherd to track.

If the checks pass cleanly, say so clearly — authors appreciate knowing the draft is ready.

If the user hasn't specified which draft to check, ask for the draft name or file path before running.

## Example invocations

```bash
# Check a named draft (fetched from IETF archive)
python scripts/run_checks.py draft-ietf-oauth-rfc8725bis-04

# Check a local XML file
python scripts/run_checks.py ./my-draft.xml

# Check by URL with maximum idnits verbosity
python scripts/run_checks.py https://www.ietf.org/archive/id/draft-ietf-oauth-rfc8725bis-04.txt --verbose 2
```

## API reference

See `references/api.md` for the full IETF Author Tools API spec used by this skill.
