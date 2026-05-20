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
# 1. 마켓플레이스 등록
claude plugin marketplace add https://github.com/juwon-cha-rocketdan/data-validator-plugin

# 2. 플러그인 설치
claude plugin install data-validator
```

## 사용법

```
/validate-data
```

처음 실행 시 한국어 온보딩이 시작됩니다 (5분 이내 완료).

온보딩 흐름:
1. Slack 연결 자동 확인 (MCP 또는 Webhook)
2. Google Sheets URL 입력
3. 탭 자동 디스커버리 → **전체 등록** 또는 **직접 선택**
4. Slack 채널 선택
5. 스키마 자동 추론 + 확인
6. 테스트 메시지 발송 → 도착 확인 후 셋업 완료

이후 `/validate-data` 호출 시 즉시 검증 → Slack 알림.

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
        │   ├── fetch_sheet.py      # Google Sheets CSV fetch + 탭 디스커버리(--list-tabs)
        │   ├── validate.py         # 3종 검증 엔진
        │   └── notify_slack.py     # Slack 알림 (MCP / Webhook)
        └── references/
            ├── onboarding_flow.md
            ├── schema_examples.md
            └── cross_ref_examples.md
```

## 업데이트

새 버전이 나오면:

```bash
claude plugin update data-validator
```

## 설정 파일

온보딩 완료 후 `~/.claude/data-validator/config.json`에 저장됩니다.
이 파일에 시크릿(Webhook URL 등)이 포함될 수 있으므로 레포에 커밋하지 마세요.
