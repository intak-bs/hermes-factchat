"""KBS factchat API Gateway를 Hermes에 연결하는 플러그인.

config.yaml의 custom_providers에 factchat 항목을 넣고 기본 모델로 지정한다.
GPT-5 계열은 도구 사용 시 reasoning_effort가 켜져 있으면 400 오류가 나므로
reasoning_effort를 none으로 고정한다.

  hermes factchat setup    모델 목록을 받아 설정 (설치 후 1회)
  hermes factchat key      API 키 새로 입력 (401 오류 시)
  hermes factchat status   현재 연결 상태 확인
  /factchat                대화 중 상태 확인
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

BASE_URL = "https://factchat.mindlogic-kr-api.com/v1/gateway"
KEY_ENV = "FACTCHAT_API_KEY"
PREFERRED_MODEL = "gpt-5.6-luna"
HOST = BASE_URL.split("//", 1)[1].split("/", 1)[0]
PROVIDER_ID = "custom:" + HOST
USER_AGENT = "hermes-factchat-plugin/1.0"


def _api_key() -> str:
    try:
        from hermes_cli.config import get_env_value

        value = get_env_value(KEY_ENV)
    except Exception:
        value = None
    return (value or os.environ.get(KEY_ENV) or "").strip()


def _request(path: str, key: str, body: dict | None = None, timeout: float = 20.0) -> dict:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        BASE_URL + path,
        data=data,
        method="POST" if body is not None else "GET",
        headers={
            "Authorization": "Bearer " + key,
            "User-Agent": USER_AGENT,
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _fetch_models(key: str) -> list[str]:
    data = _request("/models/", key)
    return sorted({m.get("id") for m in data.get("data", []) if m.get("id")})


def _is_configured(cfg: dict) -> bool:
    return any(HOST in str(p.get("base_url", "")) for p in cfg.get("custom_providers") or [])


def _apply(cfg: dict, models: list[str], default: str) -> dict:
    entry = {
        "name": HOST[0].upper() + HOST[1:],
        "base_url": BASE_URL,
        "model": default,
        "models": {m: {} for m in models},
        "models_discovered": True,
        "key_env": KEY_ENV,
        "extra_body": {"reasoning_effort": "none"},
    }
    providers = [p for p in cfg.get("custom_providers") or [] if HOST not in str(p.get("base_url", ""))]
    cfg["custom_providers"] = [entry] + providers

    model = cfg.get("model") if isinstance(cfg.get("model"), dict) else {}
    for k in ("api_key", "ollama_num_ctx", "key_env"):
        model.pop(k, None)
    model.update({"default": default, "provider": PROVIDER_ID, "base_url": BASE_URL})
    cfg["model"] = model

    agent = cfg.get("agent") if isinstance(cfg.get("agent"), dict) else {}
    overrides = agent.get("reasoning_overrides") or {}
    for m in models:
        if m.startswith("gpt-5"):
            overrides[m] = "none"
    agent["reasoning_overrides"] = overrides
    cfg["agent"] = agent
    return cfg


def setup(model: str | None = None, test: bool = True) -> str:
    """Fetch models with the saved key and write config.yaml. Returns a message."""
    from hermes_cli.config import read_raw_config, save_config

    key = _api_key()
    if not key:
        return (
            f"{KEY_ENV}가 없습니다. `hermes plugins install`을 다시 하거나 "
            f"`hermes config set {KEY_ENV} <키>`로 넣은 뒤 다시 실행하세요."
        )
    try:
        models = _fetch_models(key)
    except urllib.error.HTTPError as e:
        hint = " `hermes factchat key`로 키를 다시 넣으세요." if e.code in (401, 403) else ""
        return f"키 확인 실패 (HTTP {e.code}).{hint}"
    except Exception as e:
        return f"factchat 서버에 연결하지 못했습니다: {e}"
    if not models:
        return "이 키로 쓸 수 있는 모델이 없습니다."

    default = model or (PREFERRED_MODEL if PREFERRED_MODEL in models else models[0])
    if default not in models:
        return f"모델 '{default}'이 목록에 없습니다. `hermes factchat status`로 목록을 확인하세요."

    save_config(_apply(read_raw_config(), models, default))
    lines = [f"factchat 연결 완료: 모델 {len(models)}개, 기본 모델 {default}"]

    if test:
        body = {"model": default, "messages": [{"role": "user", "content": "한 단어로 답해: 안녕"}], "max_tokens": 20}
        if default.startswith("gpt-5"):
            body["reasoning_effort"] = "none"
        try:
            reply = _request("/chat/completions/", key, body)
            lines.append("테스트 응답: " + str(reply["choices"][0]["message"]["content"]).strip())
        except Exception as e:
            lines.append(f"테스트 호출 실패: {e}")
    lines.append("Hermes를 다시 시작하면 적용됩니다.")
    return "\n".join(lines)


def status() -> str:
    from hermes_cli.config import read_raw_config

    cfg = read_raw_config()
    model = cfg.get("model") if isinstance(cfg.get("model"), dict) else {}
    lines = [
        f"API 키: {'있음' if _api_key() else '없음'} ({KEY_ENV})",
        f"factchat 제공자: {'설정됨' if _is_configured(cfg) else '없음 — hermes factchat setup 실행'}",
        f"현재 기본 모델: {model.get('default', '-')} ({model.get('provider', '-')})",
    ]
    for p in cfg.get("custom_providers") or []:
        if HOST in str(p.get("base_url", "")):
            lines.append("사용 가능 모델: " + ", ".join(p.get("models") or {}))
    return "\n".join(lines)


def _setup_argparse(subparser) -> None:
    subs = subparser.add_subparsers(dest="factchat_command")
    p = subs.add_parser("setup", help="factchat 모델 목록을 받아 config.yaml에 연결")
    p.add_argument("--model", help="기본 모델 지정 (기본: gpt-5.6-luna)")
    p.add_argument("--no-test", action="store_true", help="테스트 호출 생략")
    subs.add_parser("status", help="연결 상태 확인")
    subs.add_parser("key", help="API 키를 새로 입력하고 setup 실행")
    subparser.set_defaults(func=_cli)


def _set_key() -> str | None:
    from hermes_cli.config import save_env_value
    from hermes_cli.secret_prompt import masked_secret_prompt

    try:
        value = masked_secret_prompt(f"{KEY_ENV} (화면에 안 보입니다): ").strip()
    except (EOFError, KeyboardInterrupt):
        return None
    if not value:
        return None
    save_env_value(KEY_ENV, value)
    os.environ[KEY_ENV] = value
    return value


def _cli(args) -> None:
    command = getattr(args, "factchat_command", None)
    if command == "key":
        if not _set_key():
            print("키를 입력하지 않아 그대로 둡니다.")
            return
        print(setup())
    elif command == "setup":
        print(setup(model=args.model, test=not args.no_test))
    else:
        print(status())


def _slash(raw_args: str) -> str:
    arg = raw_args.strip()
    if arg.startswith("setup"):
        return setup(model=arg[5:].strip() or None)
    return status() + "\n(설정: /factchat setup [모델])"


def register(ctx) -> None:
    ctx.register_cli_command(
        name="factchat",
        help="KBS factchat API Gateway 연결",
        setup_fn=_setup_argparse,
        handler_fn=_cli,
        description="factchat 키로 Hermes 모델 제공자를 설정한다. 예: hermes factchat setup",
    )
    ctx.register_command(
        "factchat",
        handler=_slash,
        description="factchat 연결 상태 확인 / 설정",
        args_hint="[setup [모델]]",
    )
