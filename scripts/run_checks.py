#!/usr/bin/env python3
"""
RFC Prepublication Checks
Runs IETF Author Tools API checks on an Internet-Draft.

Usage:
    python run_checks.py <draft-name|url|file>  [options]

Examples:
    python run_checks.py draft-ietf-oauth-rfc8725bis-04
    python run_checks.py https://www.ietf.org/archive/id/draft-ietf-oauth-rfc8725bis-04.txt
    python run_checks.py ./my-draft.xml --skip-iddiff
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
    print("  pip install requests --break-system-packages")
    sys.exit(1)

AUTHOR_TOOLS_BASE = "https://author-tools.ietf.org"
IETF_ARCHIVE_BASE = "https://www.ietf.org/archive/id"


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


def run_iddiff(name):
    """Step 4: diff against the previous version."""
    section("STEP 4: iddiff (vs. previous version)")

    match = re.match(r"^(.*-)(\d+)$", name)
    if not match:
        print("  Could not parse version number from draft name — skipping.")
        return None

    prefix, version_str = match.groups()
    version = int(version_str)

    if version == 0:
        print("  This is version -00; no previous version to diff against.")
        return None

    prev_name = f"{prefix}{version - 1:02d}"
    print(f"  Comparing {name}  ←→  {prev_name} ...")

    resp = requests.get(
        f"{AUTHOR_TOOLS_BASE}/api/iddiff",
        params={"doc_1": prev_name, "doc_2": name, "abdiff": "true"},
        timeout=120,
    )

    if resp.status_code == 200:
        # abdiff output can be long — print a preview
        lines = resp.text.splitlines()
        changed = [l for l in lines if l.startswith(("OLD:", "NEW:"))]
        print(f"  ✅  Diff produced ({len(lines)} lines, {len(changed)} changed lines).")
        if changed[:10]:
            print("  Sample changes:")
            for l in changed[:10]:
                print(f"    {l}")
            if len(changed) > 10:
                print(f"    … and {len(changed) - 10} more changed lines.")
        return resp.text
    else:
        try:
            err = resp.json().get("error", resp.text[:200])
        except Exception:
            err = resp.text[:200]
        print(f"  Diff error {resp.status_code}: {err}")
        return None


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
        "--skip-iddiff",
        action="store_true",
        help="Skip the iddiff step",
    )
    parser.add_argument(
        "--skip-abnf",
        action="store_true",
        help="Skip ABNF extraction and parsing",
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

    # Step 4: iddiff
    if not args.skip_iddiff and name:
        results["iddiff"] = run_iddiff(name)
    elif not name:
        print("\n  (iddiff skipped — draft name not available for local files)")
    else:
        print("\n  (iddiff skipped)")

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

    iddiff_result = results.get("iddiff")
    if iddiff_result:
        print("  iddiff : ✅  Diff produced (see above)")
    elif not args.skip_iddiff and name:
        print("  iddiff : (unavailable — see above)")
    else:
        print("  iddiff : (skipped)")

    print()


if __name__ == "__main__":
    main()
