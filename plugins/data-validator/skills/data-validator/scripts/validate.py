"""Three integrity checks: schema, cross reference, balance outlier.

Reads today's snapshots from fetch_sheet.py output (or --snapshots-dir override
for tests), applies the schema/cross_refs/outlier rules from config.json,
and prints a JSON report to stdout.

Designed to run *without* network access — feeds purely from local CSVs.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


CONFIG_PATH = Path.home() / ".claude" / "data-validator" / "config.json"


def load_config(override: Path | None = None) -> dict:
    path = override or CONFIG_PATH
    if not path.exists():
        raise SystemExit(f"config not found at {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_sheets(csv_dir: Path, sheet_names: list[str]) -> dict[str, pd.DataFrame]:
    sheets: dict[str, pd.DataFrame] = {}
    for name in sheet_names:
        path = csv_dir / f"{name}.csv"
        if not path.exists():
            raise SystemExit(f"csv missing: {path}. run fetch_sheet.py first.")
        sheets[name] = pd.read_csv(path)
    return sheets


# ---------------------------- schema ----------------------------


def check_schema(name: str, df: pd.DataFrame, rules: dict) -> list[dict]:
    issues: list[dict] = []

    for col in rules.get("required", []):
        if col not in df.columns:
            issues.append(
                _issue("error", name, None, col, None, "schema.required",
                       f"required column '{col}' missing from sheet '{name}'"))
            continue
        empties = df.index[df[col].isna() | (df[col].astype(str).str.strip() == "")].tolist()
        for row_idx in empties:
            issues.append(
                _issue("error", name, row_idx, col, "", "schema.required",
                       f"required value empty at {name} row {row_idx + 2} column '{col}'"))

    for col, expected in rules.get("types", {}).items():
        if col not in df.columns:
            continue
        for row_idx, value in df[col].items():
            if pd.isna(value):
                continue
            if not _matches_type(value, expected):
                issues.append(
                    _issue("error", name, row_idx, col, value, "schema.type",
                           f"type mismatch at {name} row {row_idx + 2} column '{col}': "
                           f"expected {expected}, got {type(value).__name__} ({value!r})"))

    for col, bounds in rules.get("ranges", {}).items():
        if col not in df.columns:
            continue
        lo = bounds.get("min")
        hi = bounds.get("max")
        for row_idx, value in df[col].items():
            if pd.isna(value):
                continue
            try:
                fval = float(value)
            except (TypeError, ValueError):
                continue
            if lo is not None and fval < lo:
                issues.append(
                    _issue("error", name, row_idx, col, value, "schema.range",
                           f"{name} row {row_idx + 2} {col}={value} below min {lo}"))
            if hi is not None and fval > hi:
                issues.append(
                    _issue("error", name, row_idx, col, value, "schema.range",
                           f"{name} row {row_idx + 2} {col}={value} above max {hi}"))

    for col in rules.get("unique", []):
        if col not in df.columns:
            continue
        dupes = df[df.duplicated(subset=[col], keep=False)]
        for row_idx, value in dupes[col].items():
            issues.append(
                _issue("error", name, row_idx, col, value, "schema.unique",
                       f"duplicate value '{value}' in {name}.{col} at row {row_idx + 2}"))

    for col, allowed in rules.get("enum", {}).items():
        if col not in df.columns:
            continue
        allowed_set = set(allowed)
        for row_idx, value in df[col].items():
            if pd.isna(value):
                continue
            if value not in allowed_set:
                issues.append(
                    _issue("error", name, row_idx, col, value, "schema.enum",
                           f"{name} row {row_idx + 2} {col}={value!r} not in allowed values {sorted(allowed_set)}"))

    return issues


def _matches_type(value: Any, expected: str) -> bool:
    if expected == "string":
        return isinstance(value, str) or not _looks_numeric(value)
    if expected == "int":
        try:
            return float(value).is_integer()
        except (TypeError, ValueError):
            return False
    if expected == "float":
        try:
            float(value)
            return True
        except (TypeError, ValueError):
            return False
    if expected == "bool":
        return isinstance(value, (bool, np.bool_)) or str(value).lower() in {"true", "false"}
    return True  # unknown type → don't gate


def _looks_numeric(value: Any) -> bool:
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


# ---------------------------- cross refs ----------------------------


def check_cross_refs(sheets: dict[str, pd.DataFrame], cross_refs: list[dict]) -> list[dict]:
    issues: list[dict] = []
    for ref in cross_refs:
        src_sheet, src_col = ref["from"].split(".")
        dst_sheet, dst_col = ref["to"].split(".")
        if src_sheet not in sheets or dst_sheet not in sheets:
            continue
        src_df = sheets[src_sheet]
        dst_df = sheets[dst_sheet]
        if src_col not in src_df.columns or dst_col not in dst_df.columns:
            continue
        valid_ids = set(dst_df[dst_col].dropna().astype(str).tolist())
        for row_idx, value in src_df[src_col].items():
            if pd.isna(value) or str(value).strip() == "":
                continue
            if str(value) not in valid_ids:
                issues.append(
                    _issue("error", src_sheet, row_idx, src_col, value, "cross_ref",
                           f"{src_sheet} row {row_idx + 2} {src_col}={value!r} not present in {dst_sheet}.{dst_col}"))
    return issues


# ---------------------------- balance outlier ----------------------------


def check_outliers(name: str, df: pd.DataFrame, numeric_cols: list[str], sigma: float = 3.0) -> list[dict]:
    """Flag values that are >sigma standard deviations from the column mean."""
    issues: list[dict] = []
    for col in numeric_cols:
        if col not in df.columns:
            continue
        series = pd.to_numeric(df[col], errors="coerce").dropna()
        if len(series) < 4:  # too few samples to compute stable stats
            continue
        mean = series.mean()
        std = series.std()
        if std == 0 or pd.isna(std):
            continue
        for row_idx, raw in df[col].items():
            try:
                value = float(raw)
            except (TypeError, ValueError):
                continue
            z = abs(value - mean) / std
            if z > sigma:
                issues.append(
                    _issue("warning", name, row_idx, col, value, "outlier",
                           f"{name} row {row_idx + 2} {col}={value} is {z:.1f}σ from column mean {mean:.2f}"))
    return issues


# ---------------------------- output ----------------------------


def _issue(severity: str, sheet: str, row: int | None, column: str, value: Any,
           rule: str, message: str) -> dict:
    return {
        "severity": severity,
        "sheet": sheet,
        "row": (row + 2) if isinstance(row, int) else None,  # +2 for header + 0-index
        "column": column,
        "value": value if not (isinstance(value, float) and np.isnan(value)) else None,
        "rule": rule,
        "message": message,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=None,
                        help="override config.json path (for tests)")
    parser.add_argument("--csv-dir", type=Path, required=True,
                        help="directory containing per-sheet CSVs (output of fetch_sheet.py)")
    parser.add_argument("--numeric-cols", default="",
                        help="comma-separated cols to outlier-check (default: all numeric)")
    args = parser.parse_args()

    config = load_config(args.config)
    sheet_names = [s["name"] for s in config.get("sheets", [])]
    sheets = load_sheets(args.csv_dir, sheet_names)

    issues: list[dict] = []
    schema = config.get("schema", {})
    for name, df in sheets.items():
        issues.extend(check_schema(name, df, schema.get(name, {})))

    issues.extend(check_cross_refs(sheets, config.get("cross_refs", [])))

    explicit_cols = [c.strip() for c in args.numeric_cols.split(",") if c.strip()]
    for name, df in sheets.items():
        if explicit_cols:
            cols = explicit_cols
        else:
            cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
        issues.extend(check_outliers(name, df, cols))

    summary = _summary(issues)
    json.dump(
        {"passed": all(i["severity"] != "error" for i in issues),
         "summary": summary, "issues": issues},
        sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


def _summary(issues: list[dict]) -> str:
    counts: dict[str, int] = {}
    for i in issues:
        counts[i["severity"]] = counts.get(i["severity"], 0) + 1
    parts = [f"{n} {sev}{'s' if n != 1 else ''}" for sev, n in counts.items()]
    return ", ".join(parts) if parts else "no issues"


if __name__ == "__main__":
    sys.exit(main())
