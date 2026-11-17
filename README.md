# hermes-factchat

Hermes Agent에 KBS factchat API Gateway를 연결하는 플러그인입니다.
본인 API 키만 있으면 됩니다. 크레딧은 키를 만든 계정에서 차감됩니다.

## 설치 (Windows, Hermes 터미널)

```
hermes plugins install <GitHub계정>/hermes-factchat --enable
hermes factchat setup
```

1. 첫 줄을 실행하면 `FACTCHAT_API_KEY`를 묻습니다. 키를 붙여넣으세요 (화면에 안 보임).
2. 둘째 줄이 모델 목록을 받아 기본 모델(gpt-5.6-luna)로 연결하고 테스트까지 합니다.
3. Hermes를 다시 시작합니다.

## 명령

| 명령 | 하는 일 |
|---|---|
| `hermes factchat setup [--model 모델]` | 모델 목록 갱신 + 기본 모델 지정 |
| `hermes factchat status` | 키·제공자·기본 모델 확인 |
| `/factchat`, `/factchat setup` | 대화 중 같은 기능 |

## 바꾸는 설정

`config.yaml`만 바꿉니다. 다른 설정은 그대로 둡니다.

- `custom_providers`에 factchat 항목 (`key_env: FACTCHAT_API_KEY`)
- `model.default`, `model.provider`, `model.base_url`
- `agent.reasoning_overrides`의 GPT-5 계열을 `none`으로
  - 도구를 쓰면서 reasoning_effort가 켜져 있으면 400 오류가 나기 때문

키는 `.env`에만 저장되고 이 저장소에는 들어 있지 않습니다.

## 업데이트·삭제

```
hermes plugins update factchat
hermes plugins remove factchat
```
