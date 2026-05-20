---
name: validate-data
description: 게임 데이터 테이블(Google Sheets)을 검증해 라이브 사고를 예방. 데이터 미기입(필수값 빈 셀, 끊긴 외래키)과 튀는 데이터(평균 대비 N-sigma 이상치)를 잡아 슬랙으로 알림. 매일 오전 10시 KST 자동 실행과 수동 트리거 모두 지원. 사용자가 "/validate-data", "데이터 검증", "시트 검사", "데이터 테이블 확인", "게임 밸런스 점검", "Google Sheets 검증", "아이템/스킬/스테이지/가챠 테이블 점검", "데이터 사고 예방", "시트 변경 안전 확인" 같은 표현을 쓰면 반드시 이 스킬을 사용. 기획자/운영자가 시트를 수정한 직후나 빌드 전 점검 요청에도 적극 호출. 사용자가 명시적으로 "스킬 안 써도 돼"라고 말하지 않는 한 게임 데이터 테이블 관련 어떤 검증 요청에도 사용할 것.
---

# Data Table Validator

게임 데이터 테이블(Google Sheets)을 3종 검증해서 라이브 사고를 예방한다.

**대화는 한국어로, 코드/파일명/함수명/주석은 영어로.** (CLAUDE.md 규칙)

## 검증 3종

| 검증 | 잡아내는 사고 |
|---|---|
| 스키마 | 데이터 미기입(필수값 빈 셀), 타입 오류, 범위 벗어남, 중복 ID, enum 외 값 |
| 크로스 참조 | 존재하지 않는 ID 참조 — 예: 스폰 데이터가 없는 몬스터 ID를 가리켜 게임 진행 차단 |
| 밸런스 이상치 | 평균 대비 N-sigma 이상 튀는 값 — 예: 데미지 9999, HP 계수 8.0 |

---

## 워크플로우

### Step 1: 설정 확인

`~/.claude/data-validator/config.json` 존재 여부 확인.
- 없거나 `sheets` 항목이 비어 있으면 → **Step 2 (Onboarding)**
- 있으면 → **Step 2.5 (사전 점검)** 후 **Step 3 (검증 실행)**

config.json 스키마:
```json
{
  "sheet_id": "<google sheets id>",
  "sheets": [{"name": "items", "gid": "0"}, ...],
  "slack_transport": "mcp" | "webhook",
  "slack_channel": "#live-ops-alert",
  "slack_webhook_url": "<only when transport=webhook>",
  "schema": { "items": { "required": [...], "types": {...}, "ranges": {...} } },
  "cross_refs": [ { "from": "shop_rewards.reward_id", "to": "items.id" } ]
}
```

### Step 2: Onboarding (최초 1회, 한국어 대화)

세부 흐름은 `references/onboarding_flow.md` 참조. 핵심 순서:

1. **Slack 연결 자동 검사** — 현재 세션에서 호출 가능한 Slack 도구를 가볍게 1회 호출해 본다. 도구 이름은 환경에 따라 다르다:
   - **Slack MCP**: `slack_search_channels(query="")`
   - **Anthropic Connector (Claude Desktop / Cowork / Routines)**: `slack_list_channels` 또는 채널 검색에 해당하는 Connector 도구
   - 어느 쪽이든 성공하면 워크스페이스 정보를 추출하고 다음 단계로
   - 둘 다 실패 → 실행 환경(Claude Desktop의 Connectors / Claude Code의 MCP / Webhook 폴백) 가이드를 사용자에게 제시
2. **Google Sheets URL 입력** — "링크가 있는 사람" 공개 설정 안내. URL에서 `sheet_id` 추출.
3. **탭 자동 디스커버리 + "전체/선택" 분기** — `python scripts/fetch_sheet.py --list-tabs --sheet-id <id>`를 호출해 모든 탭의 `[{name, gid}, ...]` 목록을 받음. 사용자에게 두 선택지 제시:
   - **[전체]** — 발견된 모든 탭을 그대로 `sheets`에 등록. 스키마 미지정이라 강한 검증(필수값/타입/enum)은 동작하지 않고 outlier 검증만 돌아감 → 노이즈가 많아질 수 있음을 사전 고지.
   - **[선택]** — 탭 목록에서 멀티 선택. 선택된 탭만 등록.
4. **Slack 채널 선택** — Slack 도구의 채널 검색 결과로 후보 제시(자유 텍스트 X). Webhook 모드면 URL 입력.
5. **(선택) 스키마 정의** — 비워두면 헤더 + 첫 데이터 행으로 자동 추론. 예시는 `references/schema_examples.md` 참조.
6. **(선택) 크로스 참조 규칙** — 예: `shop_rewards.reward_id → items.id`. 예시는 `references/cross_ref_examples.md` 참조.
7. **테스트 메시지 발송 + 사용자 확인** — 사용자가 "도착함"이라고 명시적으로 확인할 때까지 셋업 미완료. 도착 안 했다고 답하면 채널 재선택으로 돌아감.
8. **자동 스케줄 등록 (선택)** — 매일 오전 10시 KST에 Cowork scheduled task로 등록.

수집한 정보를 `config.json`에 저장한 뒤 **Step 3**로 이동.

### Step 2.5: 사전 점검 (매 실행)

가벼운 호출 하나로 사용 중인 transport가 여전히 살아 있는지 확인.
- MCP / Connector 모드: 채널 검색 도구 1회 호출 (`slack_search_channels` 또는 동등 Connector 도구)
- Webhook 모드: 별도 호출 없이 진행, 실패는 Step 4에서 잡음

실패해도 검증 자체는 의미가 있으므로 결과를 콘솔에도 같이 출력한다.

### Step 3: 검증 실행 (3종)

다음 순서로 실행한다:

1. **데이터 가져오기** — `python scripts/fetch_sheet.py` 실행
   - 각 시트를 공개 CSV export URL로 가져와 메모리에 로드
   - 가져온 데이터를 임시 디렉터리에 CSV로 저장 (validate.py가 읽음)
   - 별도 모드 `--list-tabs --sheet-id <id>` 는 시트의 모든 탭(name, gid)을 JSON으로 stdout 출력 (onboarding 단계에서 사용)
2. **3종 검증** — `python scripts/validate.py` 실행
   - 스키마(타입/필수값/범위/중복/enum) + 크로스 참조 + 밸런스 이상치(3-sigma)
   - 출력 JSON:

```json
{
  "passed": false,
  "summary": "2 errors, 1 warning",
  "issues": [
    {
      "severity": "error" | "warning" | "info",
      "sheet": "shop_rewards",
      "row": 14,
      "column": "reward_id",
      "value": "ITEM_999",
      "rule": "cross_ref",
      "message": "reward_id 'ITEM_999'는 items 시트에 존재하지 않음"
    }
  ]
}
```

### Step 4: 슬랙 알림

`python scripts/notify_slack.py --input <validation_result.json>` 실행. 내부 분기:
- `slack_transport: mcp` → 스크립트가 Block Kit payload JSON을 stdout으로 출력 → **이 워크플로우의 Claude가 그 텍스트를 받아 사용 가능한 Slack 도구로 직접 전달**. (Python이 MCP/Connector 전송로에 직접 접근할 수 없기 때문)
  - Claude Code + Slack MCP 환경: `slack_send_message(channel=..., blocks=...)`
  - Claude Desktop / Cowork / Routines + Slack Connector 환경: Connector가 노출하는 메시지 전송 도구(예: `slack_send_message`, `slack_post_message`, 또는 그와 동등한 이름)
  - 도구 이름은 환경마다 다를 수 있으므로 현재 세션에서 호출 가능한 Slack 메시지 전송 도구를 사용.
- `slack_transport: webhook` → 스크립트 안에서 `requests.post(webhook_url, json=blocks_payload)` 직접 호출
- 전송 실패 시 → 채팅창/콘솔에 폴백 로그 + 사용자 알림. **silent fail 금지.**

메시지 톤:
- 통과(이슈 0): "✅ 검증 통과 (N sheets, M rows)" 1줄
- 실패: Block Kit으로 시트별/심각도별 그룹화 + 시트 URL 딥링크

---

## 디렉터리 구조 (참조용)

```
.claude/skills/data-validator/
├── SKILL.md
├── requirements.txt            # pandas, numpy, requests
├── scripts/
│   ├── fetch_sheet.py          # 시트 fetch + 탭 디스커버리(--list-tabs)
│   ├── validate.py             # 스키마 / 크로스 참조 / 이상치 3종
│   └── notify_slack.py         # MCP 분기 / Webhook 호출
├── references/
│   ├── onboarding_flow.md
│   ├── schema_examples.md
│   └── cross_ref_examples.md
└── evals/                      # fixture 기반 sanity check
    ├── expected.md
    └── fixtures/
        ├── config.json
        └── csv/

~/.claude/data-validator/
└── config.json
```

---

## 주의사항 (왜 이렇게 하는가)

- **Slack 채널은 자유 텍스트로 받지 않는다.** 오타/권한 없는 채널로 알림이 사라지는 사고를 막기 위해 `slack_search_channels` 결과 중에서만 선택 가능.
- **silent fail 금지.** 슬랙 전송이 실패하면 콘솔에 반드시 출력. 매일 알림이 와야 한다는 신뢰가 깨지는 것이 가장 큰 사고다.
- **이상치 임계값(3-sigma)은 보수적으로 시작.** false positive로 신뢰 잃는 것보다 처음엔 좀 놓치는 게 낫다. 운영하면서 컬럼별로 조정.
- **첫 실행 체크리스트**
  - [ ] `~/.claude/data-validator/config.json` 존재
  - [ ] 시트가 "링크가 있는 사람" 공개로 설정됨
  - [ ] 현재 세션에서 Slack 도구(MCP 또는 Connector)가 호출 가능하거나, Webhook URL이 config에 들어 있음
  - [ ] 테스트 메시지가 슬랙 채널에 실제 도착함을 사용자가 확인함

---

## 실행 환경별 가이드

이 스킬이 어디서 실행되느냐에 따라 사용 가능한 Slack 전송 경로가 달라진다.

| 환경 | Slack 전송 경로 | 비고 |
|---|---|---|
| **Claude Code CLI** | Slack MCP(`claude mcp add slack ...`) 또는 Webhook | MCP는 Bot Token 필요. Anthropic Connector는 사용 불가. |
| **Claude Desktop 앱 (Code 탭 포함)** | Anthropic Slack Connector 또는 Webhook | Connectors 메뉴에서 1회 연결로 사용 가능. App 설치 권한 불필요. |
| **Cowork** | Anthropic Slack Connector 또는 Webhook | Desktop과 동일 환경. |
| **Routines (`/schedule`)** | Anthropic Slack Connector 가능성 큼 / 검증 필요 | 첫 routine 실행 시 슬랙 발송 성공 여부로 확인. 실패 시 Webhook 폴백. |

## 자동 스케줄링 (매일 오전 10시 KST)

수동 시연으로 동작이 확인되면 같은 워크플로우를 자동 실행하도록 등록한다.

1. **Claude Code의 `/schedule` 스킬 사용 (권장)**
   - cron 표현으로 등록: `0 10 * * *` (매일 10:00 로컬시간) — KST 환경이라면 그대로 10AM KST
   - routine 본문: "data-validator 스킬을 실행해 시트 검증 결과를 슬랙으로 전송"
   - 등록 직후 `/schedule run <id>` 등으로 1회 시범 실행해서 슬랙 도착 확인
2. **Cowork Scheduled Task** — Desktop 앱의 Cowork 기능에서 비슷한 cron 등록 가능
3. **외부 cron (launchd / GitHub Actions / n8n)** — 1, 2가 막힐 때 폴백. 이 경우 Slack 전송은 Webhook 또는 Bot Token이 필요(Connector 사용 불가).

> 자동 실행 시점에는 사용자 대화가 없으므로, 사전에 onboarding이 끝나 `config.json`이 채워져 있어야 한다. 또한 Anthropic Connector에 의존하는 routine이면 Connector 인증이 만료되지 않도록 주기적으로 확인.
