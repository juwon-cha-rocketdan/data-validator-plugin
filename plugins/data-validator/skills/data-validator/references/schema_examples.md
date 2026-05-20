# Schema Examples

`config.json`의 `schema` 항목에 들어갈 시트별 스키마 정의 예시.

## 형식

```json
{
  "schema": {
    "<sheet_name>": {
      "required": ["<column>", ...],
      "types": { "<column>": "string" | "int" | "float" | "bool" },
      "ranges": { "<numeric_column>": { "min": <n>, "max": <n> } },
      "unique": ["<column>", ...],
      "enum": { "<column>": ["<val1>", "<val2>", ...] }
    }
  }
}
```

모든 필드는 선택. 없으면 해당 검증을 스킵.

## 예시 1: items 시트

```json
{
  "items": {
    "required": ["id", "name", "damage", "rarity"],
    "types": {
      "id": "string",
      "name": "string",
      "damage": "int",
      "rarity": "string",
      "icon_path": "string"
    },
    "ranges": { "damage": { "min": 1, "max": 9999 } },
    "unique": ["id"],
    "enum": { "rarity": ["common", "rare", "epic", "legendary"] }
  }
}
```

## 예시 2: stages 시트 (수치 비율 컬럼 포함)

```json
{
  "stages": {
    "required": ["stage_id", "hp_coefficient", "spawn_data"],
    "types": {
      "stage_id": "string",
      "hp_coefficient": "float",
      "spawn_data": "string"
    },
    "ranges": { "hp_coefficient": { "min": 0.5, "max": 5.0 } },
    "unique": ["stage_id"]
  }
}
```

> `hp_coefficient`의 `max: 5.0` 같은 상한은 명시적인 사고 차단선. 회귀 검사가 잡지 못하는 *첫날 입력 실수*도 스키마에서 한 번 더 막힌다.

## 예시 3: 최소 스키마

```json
{
  "skills": { "required": ["id"], "unique": ["id"] }
}
```

스키마를 거의 정의하지 않아도 `required` + `unique`만으로 데이터 미기입 + 중복 ID는 잡을 수 있다. 정의가 비싸다고 느낄 땐 이 정도로 시작.

## 자동 추론 동작

Onboarding 단계에서 사용자가 스키마를 비워두면:
- `required`: 헤더에 있고 첫 데이터 행에서 비어 있지 않은 컬럼 전부
- `types`: 첫 데이터 행의 값을 보고 `int → float → string` 순으로 결정
- `ranges`: 자동 추론 안 함 (사용자가 명시적으로 줘야 함)
- `unique`: `id`로 끝나는 컬럼명 자동 후보 등록 + 사용자 확인

## 자주 하는 실수

- `damage`가 가끔 빈 셀이라 자동 추론이 `string`이 됐다 — 회귀 검사 시 타입이 흔들리지 않도록 `int`로 명시할 것
- `enum` 값 대소문자 불일치 (`Rare` vs `rare`) — 시트 표기 그대로 적을 것
- 한국어 컬럼명 — 동작은 하지만 회귀 검사의 코드 사용처 인덱싱이 어려워짐. 가능하면 컬럼명은 영어로.
