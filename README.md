# data-validator-plugin

게임 데이터 테이블(Google Sheets)을 3종 검증해 라이브 사고를 예방하는 Claude Code 플러그인.

## 검증 3종

| 검증 | 잡아내는 사고 |
|---|---|
| 스키마 | 필수값 빈 셀, 타입 오류, 범위 벗어남, 중복 ID, enum 외 값 |
| 크로스 참조 | 존재하지 않는 ID 참조 (예: 없는 몬스터 ID → 스테이지 진행 차단) |
| 밸런스 이상치 | 평균 대비 N-sigma 이상 튀는 값 (예: 데미지 9999, HP 계수 8.0) |

## 설치

```bash
claude plugin add https://github.com/juwon-cha-rocketdan/data-validator-plugin
```

## 사용법

```
/validate-data
```

처음 실행 시 한국어 온보딩이 시작됩니다 (5분 이내 완료).

## 필요 조건

- Python 3.9+
- Google Sheets: "링크가 있는 사람" 공개 설정
- Slack: MCP 연결 또는 Incoming Webhook URL

## 의존성 설치

```bash
pip install -r plugins/data-validator/skills/data-validator/requirements.txt
```

## 디렉터리 구조

```
plugins/data-validator/
├── .claude-plugin/
│   └── plugin.json
└── skills/
    └── data-validator/
        ├── SKILL.md
        ├── requirements.txt
        ├── scripts/
        │   ├── fetch_sheet.py      # Google Sheets CSV fetch
        │   ├── validate.py         # 3종 검증 엔진
        │   └── notify_slack.py     # Slack 알림 (MCP / Webhook)
        └── references/
            ├── onboarding_flow.md
            ├── schema_examples.md
            └── cross_ref_examples.md
```

## 설정 파일

온보딩 완료 후 `~/.claude/data-validator/config.json`에 저장됩니다.
이 파일에 시크릿(Webhook URL 등)이 포함될 수 있으므로 레포에 커밋하지 마세요.
