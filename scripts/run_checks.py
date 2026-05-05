#!/usr/bin/env python3
"""
RFC Prepublication Checks
Runs IETF Author Tools API checks on an Internet-Draft.

Usage:
    python run_checks.py <draft-name|url|file>  [options]

Examples:
    python run_checks.py draft-ietf-oauth-rfc8725bis-04
    python run_checks.py https://www.ietf.org/archive/id/draft-ietf-oauth-rfc8725bis-04.txt
    python run_checks.py ./my-draft.xml
"""

import sys
import os
import re
import argparse
from pathlib import Path

try:
    import requests
except ImportError:
    print("ERROR: 'requests' library not found. Install it with:")
    print("  pip install requests")
    sys.exit(1)

AUTHOR_TOOLS_BASE = "https://author-tools.ietf.org"
IETF_ARCHIVE_BASE = "https://www.ietf.org/archive/id"
DATATRACKER_BASE = "https://datatracker.ietf.org"

# std_level slugs that are lower maturity and trigger the downref rule (RFC 3967 / RFC 8067)
# when cited normatively from a Standards Track or BCP document
DOWNREF_LEVELS = {"inf", "exp", "historic"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def section(title):
    print()
    print("=" * 64)
    print(f"  {title}")
    print("=" * 64)


def resolve_draft(identifier):
    """
    Turn a draft identifier into (name, url, file_path).

    - Local file  → (None, None, path)
    - HTTP URL    → (stem, url, None)
    - Draft name  → (name, archive-url, None)
    """
    if os.path.exists(identifier):
        return None, None, identifier

    if identifier.startswith(("http://", "https://")):
        stem = Path(identifier).stem  # e.g. draft-ietf-oauth-rfc8725bis-04
        return stem, identifier, None

    # Bare draft name — strip any accidental extension
    name = re.sub(r"\.(txt|xml|md)$", "", identifier)
    url = f"{IETF_ARCHIVE_BASE}/{name}.txt"
    return name, url, None


def fetch_content(url):
    """Download a URL and return (bytes, filename)."""
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    filename = Path(url).name or "draft.txt"
    return resp.content, filename


# ---------------------------------------------------------------------------
# Check functions
# ---------------------------------------------------------------------------

def run_idnits(url=None, file_path=None, submit_check=True, verbose=1):
    """Step 1: idnits."""
    section("STEP 1: idnits")

    if url:
        params = {"url": url, "verbose": verbose}
        if submit_check:
            params["submitcheck"] = "true"
        resp = requests.get(
            f"{AUTHOR_TOOLS_BASE}/api/idnits",
            params=params,
            timeout=120,
        )
    else:
        with open(file_path, "rb") as f:
            data = {"verbose": str(verbose)}
            if submit_check:
                data["submitcheck"] = "true"
            resp = requests.post(
                f"{AUTHOR_TOOLS_BASE}/api/idnits",
                files={"file": (Path(file_path).name, f)},
                data=data,
                timeout=120,
            )

    if resp.status_code == 200:
        print(resp.text)
        # Pull out the summary line for later
        for line in reversed(resp.text.splitlines()):
            if re.search(r"\d+ error", line):
                return {"raw": resp.text, "summary": line.strip()}
        return {"raw": resp.text, "summary": None}
    else:
        print(f"ERROR {resp.status_code}: {resp.text[:400]}")
        return None


def run_validate(url=None, file_path=None):
    """Step 2: full validation via /api/validate."""
    section("STEP 2: Full validation (xml2rfc + idnits + non-ASCII)")

    if url:
        content, filename = fetch_content(url)
    else:
        content = Path(file_path).read_bytes()
        filename = Path(file_path).name

    resp = requests.post(
        f"{AUTHOR_TOOLS_BASE}/api/validate",
        files={"file": (filename, content)},
        timeout=180,
    )

    if resp.status_code != 200:
        print(f"ERROR {resp.status_code}: {resp.text[:400]}")
        return None

    result = resp.json()
    errors = result.get("errors") or []
    warnings = result.get("warnings") or []
    non_ascii = result.get("non_ascii", "").strip()
    bare_unicode = result.get("bare_unicode") or []

    if errors:
        print(f"ERRORS ({len(errors)}):")
        for e in errors:
            print(f"  ❌  {e}")
    else:
        print("  ✅  No errors.")

    if warnings:
        print(f"\nWARNINGS ({len(warnings)}):")
        for w in warnings:
            print(f"  ⚠️   {w}")
    else:
        print("  ✅  No warnings.")

    if non_ascii:
        print(f"\nNon-ASCII characters detected:\n{non_ascii}")

    if bare_unicode:
        print(f"\nBare Unicode usage ({len(bare_unicode)} instances):")
        for item in bare_unicode[:20]:
            print(f"  • {item}")
        if len(bare_unicode) > 20:
            print(f"  … and {len(bare_unicode) - 20} more.")

    return result


def run_abnf_check(url=None, name=None):
    """Step 3: extract ABNF and parse it."""
    section("STEP 3: ABNF check")

    params = {}
    if url:
        params["url"] = url
    elif name:
        params["doc"] = name
    else:
        print("  (skipped — no URL or name available)")
        return None

    extract_resp = requests.get(
        f"{AUTHOR_TOOLS_BASE}/api/abnf/extract",
        params=params,
        timeout=60,
    )

    if extract_resp.status_code != 200:
        print(f"  ABNF extract error {extract_resp.status_code}: {extract_resp.text[:200]}")
        return None

    abnf_text = extract_resp.text.strip()
    if not abnf_text:
        print("  No ABNF found in draft.")
        return {"found": False}

    line_count = abnf_text.count("\n") + 1
    print(f"  Found ABNF ({line_count} lines). Parsing with BAP...")

    parse_resp = requests.post(
        f"{AUTHOR_TOOLS_BASE}/api/abnf/parse",
        data={"input": abnf_text},
        timeout=60,
    )

    if parse_resp.status_code != 200:
        print(f"  ABNF parse error {parse_resp.status_code}: {parse_resp.text[:200]}")
        return None

    result = parse_resp.json()
    errors = (result.get("errors") or "").strip()

    if errors:
        print(f"  ❌  ABNF errors:\n{errors}")
    else:
        print("  ✅  ABNF parsed cleanly.")

    return {"found": True, "errors": errors, "abnf": result.get("abnf", "")}


def _dt_get(path, params=None):
    """GET from the datatracker API; return parsed JSON or None on error."""
    resp = requests.get(
        f"{DATATRACKER_BASE}{path}",
        params={"format": "json", **(params or {})},
        timeout=30,
    )
    if resp.status_code == 200:
        return resp.json()
    return None


def _strip_version(name):
    """Strip version suffix: draft-foo-bar-04 → draft-foo-bar."""
    return re.sub(r"-\d{2}$", "", name) if re.match(r".*-\d{2}$", name) else name


def _fetch_downref_registry():
    """Return a set of RFC names (e.g. 'rfc6979') already in the downref registry."""
    from html.parser import HTMLParser

    class _Parser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.in_td = False
            self.current = []
            self.rfcs = set()

        def handle_starttag(self, tag, attrs):
            if tag == "td":
                self.in_td = True

        def handle_endtag(self, tag):
            if tag == "td":
                text = "".join(self.current).strip().lower()
                m = re.match(r"rfc\s*(\d+)", text)
                if m:
                    self.rfcs.add(f"rfc{m.group(1)}")
                self.current = []
                self.in_td = False

        def handle_data(self, data):
            if self.in_td:
                self.current.append(data)

    resp = requests.get(f"{DATATRACKER_BASE}/doc/downref/", timeout=30)
    if resp.status_code != 200:
        return None
    p = _Parser()
    p.feed(resp.text)
    return p.rfcs


def run_downref_check(name):
    """Step 4: check normative references for downrefs (RFC 3967 / RFC 8067)."""
    section("STEP 4: Downref check")

    base_name = _strip_version(name)
    doc = _dt_get(f"/api/v1/doc/document/{base_name}/")
    if not doc:
        print(f"  Could not fetch document metadata from datatracker — skipping.")
        return None

    doc_id = doc["id"]
    rels = _dt_get("/api/v1/doc/relateddocument/", {"source": doc_id, "limit": 100})
    if not rels:
        print("  Could not fetch reference data from datatracker — skipping.")
        return None

    normative = [
        r["target"].split("/")[-2]
        for r in rels["objects"]
        if "refnorm" in r["relationship"]
    ]

    if not normative:
        print("  No normative references found in datatracker.")
        return {"downrefs": [], "not_in_registry": []}

    print(f"  Fetching std_level for {len(normative)} normative reference(s)...")

    registry = _fetch_downref_registry()
    if registry is None:
        print("  ⚠️  Could not fetch downref registry — will flag candidates without registry check.")

    downrefs = []
    not_in_registry = []
    untracked = []

    for ref_name in normative:
        ref_doc = _dt_get(f"/api/v1/doc/document/{ref_name}/")
        if not ref_doc:
            untracked.append(ref_name)
            continue
        std_level_uri = ref_doc.get("std_level") or ""
        std_level = std_level_uri.split("/")[-2] if std_level_uri else None
        if std_level in DOWNREF_LEVELS:
            downrefs.append((ref_name, std_level))
            if registry is not None and ref_name not in registry:
                not_in_registry.append((ref_name, std_level))

    if downrefs:
        print(f"\n  Normative refs at lower maturity level ({len(downrefs)}):")
        for ref_name, level in downrefs:
            in_reg = "" if registry is None else ("  [in registry]" if ref_name not in not_in_registry else "  ⚠️  NOT in downref registry")
            print(f"    {ref_name}  ({level}){in_reg}")
    else:
        print("  ✅  No downrefs detected.")

    if untracked:
        print(f"\n  Not in datatracker (verify manually): {', '.join(untracked)}")

    return {"downrefs": downrefs, "not_in_registry": not_in_registry, "untracked": untracked}


def run_ref_status_check(name):
    """Step 5: check that normative references to active drafts are publication-ready."""
    section("STEP 5: Normative reference status")

    base_name = _strip_version(name)
    doc = _dt_get(f"/api/v1/doc/document/{base_name}/")
    if not doc:
        print("  Could not fetch document metadata from datatracker — skipping.")
        return None

    doc_id = doc["id"]
    rels = _dt_get("/api/v1/doc/relateddocument/", {"source": doc_id, "limit": 100})
    if not rels:
        print("  Could not fetch reference data from datatracker — skipping.")
        return None

    normative_drafts = [
        r["target"].split("/")[-2]
        for r in rels["objects"]
        if "refnorm" in r["relationship"]
        and r["target"].split("/")[-2].startswith("draft-")
    ]

    if not normative_drafts:
        print("  ✅  No normative references to active drafts.")
        return {"unready": []}

    print(f"  Checking {len(normative_drafts)} normative draft reference(s)...")
    unready = []

    for ref_name in normative_drafts:
        ref_doc = _dt_get(f"/api/v1/doc/document/{ref_name}/")
        if not ref_doc:
            print(f"    ⚠️  {ref_name}: not found in datatracker")
            unready.append((ref_name, "not found"))
            continue
        # Fetch human-readable state names
        state_names = []
        for state_uri in ref_doc.get("states", []):
            state_id = state_uri.rstrip("/").split("/")[-1]
            state = _dt_get(f"/api/v1/doc/state/{state_id}/")
            if state:
                state_names.append(state.get("name", state_id))
        states_str = ", ".join(state_names) if state_names else "unknown"
        # Flag anything not in an IESG-approved or RFC-editor queue state
        approved_slugs = {"rfc", "pub", "rfced", "missref"}
        state_slugs = set()
        for state_uri in ref_doc.get("states", []):
            state_id = state_uri.rstrip("/").split("/")[-1]
            state = _dt_get(f"/api/v1/doc/state/{state_id}/")
            if state:
                state_slugs.add(state.get("slug", ""))
        if not any(s in state_slugs for s in approved_slugs):
            print(f"    ⚠️  {ref_name}: {states_str}")
            unready.append((ref_name, states_str))
        else:
            print(f"    ✅  {ref_name}: {states_str}")

    if not unready:
        print("  ✅  All normative draft references appear publication-ready.")

    return {"unready": unready}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Run IETF RFC prepublication checks on an Internet-Draft.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "draft",
        help="Draft name, URL, or local file path",
    )
    parser.add_argument(
        "--skip-abnf",
        action="store_true",
        help="Skip ABNF extraction and parsing",
    )
    parser.add_argument(
        "--skip-refs",
        action="store_true",
        help="Skip downref and reference status checks (requires datatracker access)",
    )
    parser.add_argument(
        "--no-submit-check",
        action="store_true",
        help="Run idnits in normal mode instead of submission-check mode",
    )
    parser.add_argument(
        "--verbose",
        type=int,
        default=1,
        choices=[0, 1, 2],
        metavar="N",
        help="idnits verbosity level 0–2 (default: 1)",
    )
    args = parser.parse_args()

    name, url, file_path = resolve_draft(args.draft)

    print()
    print("RFC Prepublication Checks")
    print("─" * 64)
    print(f"  Draft : {name or Path(file_path).name if file_path else '(unknown)'}")
    if url:
        print(f"  URL   : {url}")
    if file_path:
        print(f"  File  : {file_path}")
    print(f"  Mode  : {'submission-check' if not args.no_submit_check else 'normal'}")

    results = {}

    # Step 1: idnits
    results["idnits"] = run_idnits(
        url=url,
        file_path=file_path,
        submit_check=not args.no_submit_check,
        verbose=args.verbose,
    )

    # Step 2: full validation
    results["validate"] = run_validate(url=url, file_path=file_path)

    # Step 3: ABNF
    if not args.skip_abnf:
        results["abnf"] = run_abnf_check(url=url, name=name)
    else:
        print("\n  (ABNF check skipped)")

    # Steps 4 & 5: datatracker-based ref checks (require a draft name)
    if not args.skip_refs and name:
        results["downref"] = run_downref_check(name)
        results["ref_status"] = run_ref_status_check(name)
    elif not name:
        print("\n  (Downref and ref status checks skipped — draft name not available for local files)")
    else:
        print("\n  (Downref and ref status checks skipped)")

    # Summary
    section("SUMMARY")
    idnits_summary = (results.get("idnits") or {}).get("summary")
    if idnits_summary:
        print(f"  idnits : {idnits_summary}")
    else:
        print("  idnits : (see output above)")

    val = results.get("validate") or {}
    n_errors = len(val.get("errors") or [])
    n_warnings = len(val.get("warnings") or [])
    status = "✅  Clean" if n_errors == 0 and n_warnings == 0 else f"❌  {n_errors} error(s), {n_warnings} warning(s)"
    print(f"  xml2rfc: {status}")

    abnf_result = results.get("abnf")
    if abnf_result is None and not args.skip_abnf:
        print("  ABNF   : (check skipped or unavailable)")
    elif args.skip_abnf:
        print("  ABNF   : (skipped)")
    elif not abnf_result.get("found"):
        print("  ABNF   : (none found in draft)")
    elif abnf_result.get("errors"):
        print("  ABNF   : ❌  Parse errors (see above)")
    else:
        print("  ABNF   : ✅  Valid")

    if args.skip_refs or not name:
        print("  downref: (skipped)")
        print("  refstat: (skipped)")
    else:
        dr = results.get("downref") or {}
        not_in_reg = dr.get("not_in_registry", [])
        untracked = dr.get("untracked", [])
        if not_in_reg:
            print(f"  downref: ⚠️  {len(not_in_reg)} downref(s) not in registry (see above)")
        elif untracked:
            print(f"  downref: ⚠️  {len(untracked)} ref(s) untracked — verify manually")
        elif dr.get("downrefs") is not None:
            print("  downref: ✅  Clean")
        else:
            print("  downref: (unavailable)")

        rs = results.get("ref_status") or {}
        unready = rs.get("unready", [])
        if unready:
            print(f"  refstat: ⚠️  {len(unready)} normative draft ref(s) may not be ready")
        elif rs.get("unready") is not None:
            print("  refstat: ✅  Clean")
        else:
            print("  refstat: (unavailable)")

    print()


if __name__ == "__main__":
    main()
