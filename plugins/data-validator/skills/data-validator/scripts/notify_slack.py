"""Format validation results into a Slack message.

Two output modes, picked from config.json's slack_transport:

  - 'mcp': prints a JSON payload {"channel": ..., "blocks": [...], "text": ...}
    to stdout. The Claude session driving this skill is expected to read the
    payload and call the Slack MCP tool (slack_send_message) with it. Required
    because Python can't talk to the MCP transport directly.

  - 'webhook': posts the same Block Kit payload to the webhook URL using
    requests.post. Returns exit code 0 on success, non-zero otherwise.

Validation result schema (input):
  {
    "passed": bool,
    "summary": str,
    "issues": [
      { "severity": "error"|"warning"|"info",
        "sheet": str, "row": int|null, "column": str|null,
        "value": any, "previous_value": any (optional),
        "rule": str, "ai_verdict": str (optional),
        "ai_reason": str (optional), "code_usage": [str] (optional),
        "message": str }
    ]
  }
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import requests


CONFIG_PATH = Path.home() / ".claude" / "data-validator" / "config.json"


def load_config(override: Path | None = None) -> dict:
    path = override or CONFIG_PATH
    if not path.exists():
        raise SystemExit(f"config not found at {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def build_blocks(result: dict, sheet_url: str | None) -> tuple[list[dict], str]:
    issues = result.get("issues", [])
    summary = result.get("summary", "")

    if not issues:
        text = f"✅ data validation passed ({summary})"
        return [
            {"type": "section", "text": {"type": "mrkdwn", "text": f"*{text}*"}}
        ], text

    text = f"🚨 data validation found issues ({summary})"
    blocks: list[dict] = [
        {"type": "header", "text": {"type": "plain_text", "text": text}},
    ]

    # group by sheet, then by severity
    by_sheet: dict[str, list[dict]] = defaultdict(list)
    for issue in issues:
        by_sheet[issue.get("sheet") or "(global)"].append(issue)

    for sheet, sheet_issues in by_sheet.items():
        blocks.append({"type": "divider"})
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*{sheet}*"},
        })
        for issue in sheet_issues:
            blocks.append(_issue_block(issue, sheet_url))

    if sheet_url:
        blocks.append({"type": "divider"})
        blocks.append({
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"<{sheet_url}|open the spreadsheet>"}
            ],
        })

    return blocks, text


def _issue_block(issue: dict, sheet_url: str | None) -> dict:
    sev_icon = {"error": ":rotating_light:", "warning": ":warning:", "info": ":information_source:"}.get(
        issue.get("severity", "info"), ":grey_question:"
    )
    parts = [f"{sev_icon} *{issue.get('rule', '?')}* — {issue.get('message', '')}"]
    loc_bits = []
    if issue.get("row"):
        loc_bits.append(f"row {issue['row']}")
    if issue.get("column"):
        loc_bits.append(f"column `{issue['column']}`")
    if loc_bits:
        parts.append("  " + " · ".join(loc_bits))
    if "previous_value" in issue:
        parts.append(f"  was `{issue.get('previous_value')}` → now `{issue.get('value')}`")
    if issue.get("ai_verdict"):
        parts.append(f"  *AI 판단:* {issue['ai_verdict']} — {issue.get('ai_reason','')}")
    if issue.get("code_usage"):
        usage_lines = "\n".join(f"    • `{u}`" for u in issue["code_usage"][:5])
        parts.append(f"  *code usage:*\n{usage_lines}")
    return {"type": "section", "text": {"type": "mrkdwn", "text": "\n".join(parts)}}


def post_webhook(url: str, blocks: list[dict], fallback_text: str) -> int:
    payload = {"text": fallback_text, "blocks": blocks}
    r = requests.post(url, json=payload, timeout=10)
    if r.status_code >= 300:
        sys.stderr.write(f"slack webhook failed: HTTP {r.status_code} — {r.text}\n")
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True,
                        help="validation result JSON file")
    parser.add_argument("--config", type=Path, default=None)
    args = parser.parse_args()

    config = load_config(args.config)
    result = json.loads(args.input.read_text(encoding="utf-8"))

    sheet_id = config.get("sheet_id")
    sheet_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}" if sheet_id else None
    blocks, text = build_blocks(result, sheet_url)
    channel = config.get("slack_channel")
    transport = config.get("slack_transport", "mcp")

    if transport == "webhook":
        url = config.get("slack_webhook_url")
        if not url:
            sys.stderr.write("slack_webhook_url missing in config.json\n")
            return 1
        return post_webhook(url, blocks, text)

    # transport == 'mcp' → emit payload for the Claude session to forward
    payload = {"transport": "mcp", "channel": channel, "text": text, "blocks": blocks}
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
