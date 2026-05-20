# Onboarding Flow

신규 사용자가 `/validate-data`를 처음 입력했을 때 따라가는 한국어 대화 흐름.

모든 대화는 **한국어**, 시스템이 보내는 코드/필드명/슬랙 메시지는 **영어 식별자** 유지.

---

## 전체 순서

1. 인사 + Slack 연결 자동 검사
2. 시트 URL 입력
3. 검증할 탭 선택
4. Slack 채널 선택 (또는 Webhook 입력)
5. 스키마 자동 추론 + 확인
6. 크로스 참조 규칙 (선택)
7. 테스트 메시지 발송 + 사용자 확인
8. 자동 스케줄 등록 (선택)
9. 첫 검증 실행 제안

---

## Step 1: 인사 + Slack 연결 자동 검사

```
스킬: 안녕하세요! 데이터 테이블 검증 스킬입니다.
      먼저 슬랙 연결 상태를 확인할게요...
[내부적으로 slack_search_channels(query="") 호출]
```

**케이스 A — MCP 성공:**
```
스킬: ✓ 슬랙 워크스페이스 "my-game-studio"에 연결됐어요.
      검증할 구글 시트 링크를 알려주세요.
```

**케이스 B — MCP 실패:**
```
스킬: 슬랙 MCP가 연결되지 않은 것 같아요.
      두 가지 방법 중 선택해 주세요.
      [1] 슬랙 MCP를 지금 연결한다 (권장)
          - Cowork에서 실행 중이면: 데스크탑 앱 설정 → Connectors → Slack
          - Claude Code에서 실행 중이면: ~/.claude/claude_desktop_config.json에 슬랙 MCP 추가
      [2] Webhook URL로 진행한다 (셋업 빠름, 채널 변경 시 새 URL 필요)
```

선택지 [1] → 연결 후 다시 `/validate-data` 실행 안내. 선택지 [2] → Webhook URL 입력 단계로.

---

## Step 2: 시트 URL 입력

```
스킬: 검증할 구글 시트 링크를 알려주세요.
사용자: https://docs.google.com/spreadsheets/d/abc123.../edit#gid=0
스킬: 시트 ID `abc123...`을 인식했어요.
      이 시트가 "링크가 있는 사람" 공개로 설정돼 있어야 합니다.
      (시트 우상단 공유 → 일반 액세스 → "링크가 있는 모든 사용자")
      설정하셨나요?
사용자: 응
```

확인을 받으면 공개 CSV export URL로 시트 메타데이터(탭 목록)를 가져옴.

---

## Step 3: 검증할 탭 선택

```
스킬: 시트에 탭이 5개 있네요. 검증할 탭을 골라주세요.
      [ ] items
      [ ] skills
      [ ] shop_rewards
      [ ] gacha_pool
      [ ] enemies
사용자: items, skills, shop_rewards
```

---

## Step 4: Slack 채널 선택

**MCP 모드:**
```
스킬: 알림 받을 슬랙 채널을 골라주세요. (가입돼 있는 채널 중에서만 선택 가능)
      [1] #live-ops-alert
      [2] #data-team
      [3] #engineering-general
사용자: 1
```

**Webhook 모드:**
```
스킬: 슬랙 Webhook URL을 입력해 주세요.
      (https://hooks.slack.com/services/... 형태)
사용자: https://hooks.slack.com/services/T.../B.../...
```

**중요:** 채널은 절대 자유 텍스트로 받지 않는다. 오타나 권한 없는 채널을 입력해도 셋업이 통과되면 알림이 silent fail로 사라진다.

---

## Step 5: 스키마 자동 추론 + 확인

```
스킬: 각 시트의 첫 행을 헤더로 보고 두 번째 행을 샘플로 써서 스키마를 자동 추론해 봤어요.
      items 시트:
        id: string (필수)
        name: string (필수)
        damage: int 1~9999 (필수)
        icon_path: string (선택)
      이대로 진행할까요? (Y/n)
사용자: 응
```

사용자가 "아니"라고 답하면 한 컬럼씩 타입/필수 여부/범위를 묻는 fallback. 1일 스펙에서는 fallback 미구현 가능.

---

## Step 6: 크로스 참조 규칙 (선택)

```
스킬: 시트 간 참조 관계가 있나요? 예를 들어 shop_rewards 시트의 reward_id가
      items 시트의 id를 가리킨다거나.
      (없으면 "없음"이라고 답하시면 돼요)
사용자: shop_rewards.reward_id → items.id
```

자유 텍스트로 받되 `{sheet}.{column} → {sheet}.{column}` 형식으로 강제. 형식 안 맞으면 다시 묻기.

---

## Step 7: 테스트 메시지 발송 + 사용자 확인

```
스킬: 선택한 채널로 테스트 메시지 한 번 보낼게요...
[메시지 발송]
스킬: 슬랙을 열어서 "data-validator 셋업 테스트입니다"라는 메시지가
      도착했는지 확인해 주세요. 도착했나요? (Y/n)
사용자: 응
스킬: 좋아요! 셋업 완료입니다.
```

**도착 안 했다고 답하면:** Step 4(채널 선택)로 돌아간다. 환경 변경(MCP↔Webhook)도 다시 제안. 사용자가 "도착함"이라고 명시적으로 확인하기 전까지는 셋업 미완료.

---

## Step 8: 자동 스케줄 등록 (선택)

```
스킬: 매일 오전 10시에 자동으로 검증을 돌릴까요?
      (Cowork scheduled task로 등록됩니다)
사용자: 응
```

선택지 yes → Cowork scheduled task 등록 안내. no → 수동 트리거만 사용.

---

## Step 9: 첫 검증 실행 제안

```
스킬: 셋업 끝! 지금 첫 검증을 한 번 돌려볼까요?
사용자: 응
[Step 3 검증 워크플로우 진입]
```

---

## 실수 / 재진입 처리

- 사용자가 도중에 "처음부터 다시" 라고 말하면 `config.json`을 백업하고 Step 1부터 다시.
- 사용자가 도중에 이탈해도 다음 `/validate-data` 호출 시 `config.json`이 불완전하면(`sheets` 비어 있음 등) 자동으로 다시 Onboarding 진입.
