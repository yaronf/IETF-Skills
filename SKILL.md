---
name: rfc-prepub-check
description: Run IETF Internet-Draft prepublication checks. Use this whenever the user wants to check, validate, or test an Internet-Draft before submission or publication — covering idnits nits checks, xml2rfc validation, and ABNF syntax checking. Trigger on phrases like "check my draft", "run idnits", "run nits", "prepub checks", "validate my RFC draft", "check draft-*", "nits check", "is my draft ready to submit", or any mention of checking an Internet-Draft for IETF submission readiness.
---

# RFC Prepublication Checks

This skill runs the standard suite of IETF prepublication checks on an Internet-Draft, using the [IETF Author Tools API](https://author-tools.ietf.org). It covers everything authors are expected to verify before submitting or publishing a draft.

## Checks performed (in order)

1. **idnits** — The canonical IETF nits checker. Flags formatting issues, boilerplate problems, missing required sections, stale references, line-length violations, and more. Run in submission-check mode by default so the output mirrors what the datatracker submission tool will see.
2. **Full validation** (`/api/validate`) — Runs xml2rfc structural validation plus idnits together, and also reports non-ASCII character usage.
3. **ABNF syntax check** — Extracts any ABNF grammars from the draft and validates them with BAP (RFC 5234). Skipped silently if no ABNF is found.
4. **Downref check** — Fetches normative references from the IETF Datatracker, identifies any at lower maturity level (Informational, Experimental, Historic) per RFC 3967/RFC 8067, and checks whether they are already listed in the downref registry.
5. **Normative reference status** — Flags any normative reference that is an active Internet-Draft rather than a published RFC, and reports its current datatracker state.
6. **Automated content checks** — Regex-based checks against the IETF content guidelines ([https://authors.ietf.org/required-content](https://authors.ietf.org/required-content), [https://authors.ietf.org/recommended-content](https://authors.ietf.org/recommended-content), [https://authors.ietf.org/language-and-style](https://authors.ietf.org/language-and-style)):
   - Abstract length (guideline: 50–150 words per [required-content#abstract](https://authors.ietf.org/required-content#abstract))
   - Citations in the abstract (must be fully defined within it — same source)
   - Obsoletes/Updates header consistency: abstract and introduction must acknowledge it (same source)
   - Title does not contain status-implying words ("Standard", "Draft", etc.) per [language-and-style](https://authors.ietf.org/language-and-style#internet-drafts-are-not-rfcs)
   - Draft does not refer to itself as an RFC (same source)
   - BCP 14 keywords (MUST/SHOULD/etc.) used only when RFC 2119/RFC 8174 is cited per [language-and-style#use-of-bcp-14-terms](https://authors.ietf.org/language-and-style#use-of-bcp-14-terms)
   - Weak "no security considerations" claim detected per [required-content#security-considerations](https://authors.ietf.org/required-content#security-considerations) and RFC 3552
   - Author count does not exceed 5 without stream approval (RFC 7322 §4.1.1, [required-content#authors-addresses](https://authors.ietf.org/required-content#authors-addresses))
   - Implementation Status section includes RFC Editor removal note (BCP 205, [recommended-content#implementation-status](https://authors.ietf.org/recommended-content#implementation-status))
7. **LLM content review** — You (the agent) read the draft text and apply judgment-based checks that cannot be reliably automated with regex. See the section below.

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
| `--skip-abnf` | Skip ABNF extraction and parsing (step 3) |
| `--skip-refs` | Skip downref and reference status checks (steps 4–5) |
| `--skip-content` | Skip automated content checks (step 6) |
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
7. **Content check issues** — each issue includes a direct link to the relevant guideline. Flag them to the author with the source so they can verify against the current rules.

If the checks pass cleanly, say so clearly — authors appreciate knowing the draft is ready.

If the user hasn't specified which draft to check, ask for the draft name or file path before running.

## Step 7: LLM content review

After the script completes, fetch and read the draft text yourself (use the URL or file path the user provided) and evaluate the following. These are judgment-based checks that regex cannot reliably handle. Report findings with the relevant guideline URL so the author can verify.

**Source: [https://authors.ietf.org/required-content](https://authors.ietf.org/required-content)**

- **Abstract quality** — Does it stand alone as a self-contained summary? Does it accurately describe the document's purpose and scope, or is it just copy-pasted from the introduction? Is it appropriately specific without being overly detailed?
- **Security Considerations depth** — Is the section substantive? Does it identify concrete threats and mitigations relevant to this specific protocol/document, or is it generic boilerplate? A section that just says "implementers should follow good security practices" is inadequate. Reference: RFC 3552.
- **Introduction completeness** — Does it explain the motivation, the problem being solved, and the document's applicability? If the document obsoletes or updates an RFC, does the introduction briefly explain what changed and why?
- **Summary of Changes** — If the document obsoletes or updates an RFC: is there a dedicated section summarizing the changes? Does it address known errata against the RFC(s) being obsoleted/updated? Source: [required-content#summary-of-changes](https://authors.ietf.org/required-content#summary-of-changes).

**Source: [https://authors.ietf.org/language-and-style](https://authors.ietf.org/language-and-style)**

- **SHOULD justification** — Every use of SHOULD (and SHOULD NOT) should be accompanied by an explanation of why the requirement is not MUST, and what the implications are of not following the recommendation. Flag SHOULD uses that lack this context. RFC 2119 §6–7.
- **Inclusive language** — Flag terminology that NISTIR 8366 identifies as non-inclusive (e.g., "master/slave", "whitelist/blacklist", "sanity check"). Suggest alternatives. IESG statement: [https://www.ietf.org/about/groups/iesg/statements/inclusive-language/](https://www.ietf.org/about/groups/iesg/statements/inclusive-language/). NISTIR 8366 full text: [https://web.archive.org/web/20250203031433/https://nvlpubs.nist.gov/nistpubs/ir/2021/NIST.IR.8366.pdf](https://web.archive.org/web/20250203031433/https://nvlpubs.nist.gov/nistpubs/ir/2021/NIST.IR.8366.pdf).
- **Stale text** — Are there references to specific mailing lists for sending comments? References to a specific WG being responsible for future actions? Non-permanent URLs used as normative references? Source: [language-and-style#stale-text](https://authors.ietf.org/language-and-style#stale-text). **Exception:** the "About This Document" / "Discussion of this document" section containing the WG mailing list and GitHub links is auto-generated from the `venue` YAML front matter by kramdown-rfc (kdrfc) and is automatically removed by the RFC Editor before publication — do not flag it.
- **Abbreviation expansion** — Are abbreviations expanded on first use in the body text (not counting the RFC Editor's pre-approved list)? Are they also expanded in the abstract if used there?

**Source: [https://authors.ietf.org/recommended-content](https://authors.ietf.org/recommended-content)**

- **Privacy Considerations** — If the document defines a protocol that touches personal data, user identifiers, location, or communication metadata, is a Privacy Considerations section present? RFC 6973 is the reference.

**General**

- **Consistency** — Are defined terms, acronyms, and protocol field names used consistently throughout? Do section cross-references point to the right places?
- **Clarity of normative vs. informative** — Is it clear which statements are requirements (normative) vs. guidance (informative)? Are non-requirement statements accidentally using RFC 2119 keywords?

Present your LLM review findings as a separate section after the script output, clearly labeled. Distinguish between issues (actionable problems) and observations (things the author should be aware of). Keep it focused — don't flag things that are clearly fine.

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
