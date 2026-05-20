"""Fetch Google Sheets tabs as CSVs.

Reads sheet_id + sheets list from ~/.claude/data-validator/config.json,
downloads each tab via the public CSV export endpoint, and writes a CSV
per sheet to the output directory.

Output (stdout): JSON listing per-sheet paths to today's CSV.

Also supports --list-tabs mode for onboarding: scrapes the spreadsheet's
public /edit HTML to enumerate every tab as {"name", "gid"} pairs. The skill
workflow uses this to offer "validate all tabs vs. select specific tabs".
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from pathlib import Path
from urllib.parse import quote

import pandas as pd
import requests


CONFIG_PATH = Path.home() / ".claude" / "data-validator" / "config.json"
CSV_EXPORT_URL = "https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
EDIT_URL = "https://docs.google.com/spreadsheets/d/{sheet_id}/edit"

# Tab-discovery regex: extracts (gid, tab_name) pairs from /edit HTML.
# Google embeds tab metadata as escaped JSON inside a JS bootstrap blob,
# shaped like:  [<idx>,0,"<gid>",[{"1":[[0,0,"<tab_name>"]
# Heuristic — depends on Google's HTML and may break if they change format.
TAB_BOOTSTRAP_RE = re.compile(
    r'\[\d+,0,\\"(\d+)\\",\[\{\\"1\\":\[\[0,0,\\"([^\\"]+)\\"\]'
)


def list_tabs(sheet_id: str) -> list[dict]:
    """Return every tab in the sheet as [{"name", "gid"}, ...].

    Sheet must be public ("anyone with link"). Order matches the spreadsheet's
    natural tab order. Duplicates removed (first occurrence wins).
    """
    url = EDIT_URL.format(sheet_id=quote(sheet_id, safe=""))
    response = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    matches = TAB_BOOTSTRAP_RE.findall(response.text)
    if not matches:
        raise SystemExit(
            f"could not find any tabs in {url}. "
            "the sheet may be private, or Google's HTML format may have changed."
        )
    tabs: list[dict] = []
    seen: set[str] = set()
    for gid, name in matches:
        if gid in seen:
            continue
        seen.add(gid)
        tabs.append({"name": name, "gid": gid})
    return tabs


def load_config(override: Path | None = None) -> dict:
    path = override or CONFIG_PATH
    if not path.exists():
        raise SystemExit(
            f"config not found at {path}. run onboarding first via /validate-data."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def fetch_one(sheet_id: str, gid: str, sheet_config: dict | None = None) -> pd.DataFrame:
    url = CSV_EXPORT_URL.format(sheet_id=quote(sheet_id, safe=""), gid=quote(str(gid), safe=""))
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    from io import StringIO

    field_name_row = int(sheet_config.get("field_name_row", 1)) - 1 if sheet_config else 0
    db_ignore_prefix = sheet_config.get("db_ignore_prefix") if sheet_config else None

    raw = pd.read_csv(StringIO(response.text), header=None, dtype=str)
    col_names = raw.iloc[field_name_row].fillna("").astype(str).str.strip().tolist()

    if db_ignore_prefix and field_name_row > 0:
        display_row = raw.iloc[0].fillna("").astype(str).tolist()
        keep = [i for i, (d, f) in enumerate(zip(display_row, col_names))
                if not d.startswith(db_ignore_prefix) and f]
    else:
        keep = [i for i, name in enumerate(col_names) if name]

    df = raw.iloc[field_name_row + 1:, keep].copy()
    df.columns = [col_names[i] for i in keep]
    df = df.reset_index(drop=True)
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="ignore")
    return df


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=None,
                        help="override config.json path (for tests)")
    parser.add_argument("--out-dir", type=Path, default=None,
                        help="directory to write per-sheet CSVs (default: temp dir)")
    parser.add_argument("--list-tabs", action="store_true",
                        help="discover every tab in the sheet and print as JSON to stdout. "
                             "uses --sheet-id if given, otherwise reads from config.json.")
    parser.add_argument("--sheet-id", type=str, default=None,
                        help="google sheets id (used with --list-tabs when no config exists yet)")
    args = parser.parse_args()

    if args.list_tabs:
        sheet_id = args.sheet_id
        if not sheet_id:
            config = load_config(args.config)
            sheet_id = config.get("sheet_id")
        if not sheet_id:
            raise SystemExit("--list-tabs requires --sheet-id or sheet_id in config.json")
        tabs = list_tabs(sheet_id)
        json.dump({"sheet_id": sheet_id, "tabs": tabs},
                  sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return 0

    config = load_config(args.config)
    sheet_id = config.get("sheet_id")
    sheets = config.get("sheets", [])
    if not sheet_id or not sheets:
        raise SystemExit("config.json missing 'sheet_id' or 'sheets'. run onboarding.")

    out_dir = args.out_dir or Path(tempfile.mkdtemp(prefix="data-validator-"))
    out_dir.mkdir(parents=True, exist_ok=True)

    schema_config = config.get("schema", {})
    result: dict[str, str] = {}
    for entry in sheets:
        name = entry["name"]
        gid = entry["gid"]
        df = fetch_one(sheet_id, gid, schema_config.get(name))
        path = out_dir / f"{name}.csv"
        df.to_csv(path, index=False)
        result[name] = str(path)

    json.dump({"out_dir": str(out_dir), "sheets": result},
              sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
