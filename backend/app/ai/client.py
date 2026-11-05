from __future__ import annotations

import json
import re
from typing import Any

import httpx

FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


class AIError(RuntimeError):
    pass


def strip_fences(text: str) -> str:
    cleaned = FENCE_RE.sub("", text or "").strip()
    if cleaned.startswith("json"):
        cleaned = cleaned[4:].lstrip()
    return cleaned


def chat_json(
    messages: list[dict[str, str]],
    *,
    api_key: str,
    base_url: str,
    model: str,
    temperature: float = 0.1,
    max_tokens: int = 4_000,
) -> tuple[dict[str, Any], dict[str, int]]:
    endpoint = base_url.rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    last_error: Exception | None = None
    last_content = ""

    for attempt in range(2):
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens if attempt == 0 else min(8_000, max_tokens * 2),
            "stream": False,
        }
        if attempt == 0:
            payload["response_format"] = {"type": "json_object"}
        else:
            payload["messages"] = [
                *messages,
                {
                    "role": "system",
                    "content": (
                        "上一次输出不完整或不是合法 JSON。请重新输出一个完整、闭合的 JSON 对象；"
                        "减少条目数量，description 控制在 80 字以内，不要输出任何额外文字。"
                    ),
                },
            ]

        try:
            with httpx.Client(timeout=120.0) as client:
                response = client.post(endpoint, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
            content = data["choices"][0]["message"].get("content") or ""
            last_content = content
            if not content.strip():
                raise AIError("model returned empty content")
            parsed = json.loads(strip_fences(content))
            if not isinstance(parsed, dict):
                raise AIError("model did not return a JSON object")
            usage = data.get("usage") or {}
            tokens = {
                "prompt": int(usage.get("prompt_tokens") or len(str(messages)) // 3),
                "completion": int(
                    usage.get("completion_tokens") or len(content) // 2
                ),
            }
            return parsed, tokens
        except (httpx.HTTPError, KeyError, ValueError, json.JSONDecodeError, AIError) as exc:
            last_error = exc
            # Remove response_format on the retry for gateways that reject it.
            continue

    snippet = (last_content or "")[:400].replace("\n", " ")
    raise AIError(
        f"AI request failed: {last_error}; output starts with: {snippet!r}"
    )
