"""Helpers for parsing JSON returned by chat models."""

from __future__ import annotations

import json


def _strip_code_fence(text: str) -> str:
    cleaned = text.strip()
    if not cleaned.startswith("```"):
        return cleaned

    lines = cleaned.splitlines()
    if lines and lines[0].strip().startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _remove_trailing_commas(text: str) -> str:
    output: list[str] = []
    in_string = False
    escaped = False
    index = 0
    while index < len(text):
        char = text[index]
        if in_string:
            output.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue

        if char == '"':
            in_string = True
            output.append(char)
            index += 1
            continue

        if char == ",":
            lookahead = index + 1
            while lookahead < len(text) and text[lookahead].isspace():
                lookahead += 1
            if lookahead < len(text) and text[lookahead] in "}]":
                index += 1
                continue

        output.append(char)
        index += 1

    return "".join(output)


def _first_json_object(text: str) -> str | None:
    start = text.find("{")
    if start < 0:
        return None

    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]

    return None


def _loads_object(text: str) -> dict:
    data = json.loads(text)
    if not isinstance(data, dict):
        raise TypeError("Expected JSON object")
    return data


def parse_llm_json_object(text: str) -> dict:
    cleaned = _strip_code_fence(str(text))
    candidates = [cleaned]
    extracted = _first_json_object(cleaned)
    if extracted and extracted != cleaned:
        candidates.append(extracted)

    last_error: Exception | None = None
    for candidate in candidates:
        for item in (candidate, _remove_trailing_commas(candidate)):
            try:
                return _loads_object(item)
            except (json.JSONDecodeError, TypeError) as exc:
                last_error = exc

    if last_error:
        raise last_error
    raise json.JSONDecodeError("No JSON object found", cleaned, 0)
