# Cross Reference Examples

`config.json`의 `cross_refs`에 들어갈 시트 간 ID 참조 규칙 예시.

## 형식

```json
{
  "cross_refs": [
    { "from": "<sheet>.<column>", "to": "<sheet>.<column>" }
  ]
}
```

`from`의 값이 `to`에 모두 존재해야 한다. (외래키 관계)

## 예시 1: 상점 보상이 아이템을 가리킨다

```json
{
  "cross_refs": [
    { "from": "shop_rewards.reward_id", "to": "items.id" }
  ]
}
```

- 통과: `shop_rewards.reward_id = "ITEM_5"`이고 `items.id`에 `"ITEM_5"`가 있음
- 실패: `shop_rewards.reward_id = "ITEM_999"`인데 `items.id`에 없음 → "shop_rewards 행 N: reward_id 'ITEM_999'는 items 시트에 존재하지 않음"

## 예시 2: 가챠 풀이 여러 시트를 가리킨다

```json
{
  "cross_refs": [
    { "from": "gacha_pool.item_id", "to": "items.id" },
    { "from": "gacha_pool.skill_id", "to": "skills.id" },
    { "from": "enemies.drop_table_id", "to": "drop_tables.id" }
  ]
}
```

## 예시 3: 스테이지의 스폰 데이터가 몬스터를 가리킨다 (게임 진행 차단 케이스)

```json
{
  "cross_refs": [
    { "from": "stages.spawn_enemy_id", "to": "enemies.id" }
  ]
}
```

- 사고 유형 B (데이터 미기입으로 게임 진행 차단)와 직결: `stages.spawn_enemy_id`가 가리키는 `enemies.id`가 없으면 그 스테이지는 진입 시 몬스터가 안 떠서 진행 자체가 막힌다.

## 다중 ID (쉼표 구분) 처리

일부 시트는 한 셀에 여러 ID를 쉼표로 넣는다. 예: `enemies.drop_items = "ITEM_1,ITEM_2,ITEM_3"`.

이 경우 cross_refs에 모드를 명시:
```json
{ "from": "enemies.drop_items", "to": "items.id", "multi": "comma" }
```

`multi`가 있으면 셀 값을 split해서 각각 검사. 1일 스펙에서는 기본 단일 ID만 지원하고 `multi`는 후속.

## 빈 셀 처리

`from` 컬럼이 비어 있는 경우는 어떻게 해석할지에 따라 다르다:
- 보통은 "참조하지 않음"이므로 통과로 본다
- 그러나 `required`로 지정된 컬럼이면 스키마 검증에서 미기입으로 잡힌다

cross_refs 자체는 빈 셀을 무시하고, 데이터 미기입은 스키마(required)에 맡기는 게 책임 분리상 깔끔하다.

## 가챠 확률 합계 같은 합산 제약은 어디에?

cross_refs 범위 밖. 후속 작업으로 `aggregate_constraints` 같은 별도 검증을 추가할 수 있다. plan doc §7.1 참조.
