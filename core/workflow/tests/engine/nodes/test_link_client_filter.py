import json
import sys
import types
from typing import Any

import pytest

_kafka_stub = types.ModuleType("confluent_kafka")
_kafka_stub.Producer = object
_kafka_stub.Consumer = object
sys.modules.setdefault("confluent_kafka", _kafka_stub)

from workflow.engine.nodes.plugin_tool.link_client import Tool


class _FakeSpan:
    def start(self, _name: str) -> "_FakeSpan":
        return self

    def __enter__(self) -> "_FakeSpan":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        return False

    async def add_info_events_async(self, _attributes: dict[str, Any]) -> None:
        return None


class _FakeResponse:
    async def __aenter__(self) -> "_FakeResponse":
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        return False

    async def json(self) -> dict[str, Any]:
        payload = {
            "id": 1,
            "name": "Leanne Graham",
            "email": "Sincere@april.biz",
            "address": {
                "street": "Kulas Light",
                "suite": "Apt. 556",
                "city": "Gwenborough",
            },
        }
        return {
            "header": {"code": 0, "message": "ok"},
            "payload": {"text": {"text": json.dumps(payload, ensure_ascii=False)}},
        }


class _FakeSession:
    async def __aenter__(self) -> "_FakeSession":
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        return False

    def post(self, *args: Any, **kwargs: Any) -> _FakeResponse:
        return _FakeResponse()


@pytest.mark.asyncio
async def test_tool_run_filters_hidden_fields_for_nested_object(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import aiohttp

    monkeypatch.setattr(aiohttp, "ClientSession", _FakeSession)

    method_schema = {
        "responses": {
            "200": {
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "number", "x-display": True},
                                "name": {"type": "string", "x-display": True},
                                "email": {"type": "string", "x-display": False},
                                "address": {
                                    "type": "object",
                                    "properties": {
                                        "street": {
                                            "type": "string",
                                            "x-display": False,
                                        },
                                        "suite": {
                                            "type": "string",
                                            "x-display": True,
                                        },
                                        "city": {
                                            "type": "string",
                                            "x-display": True,
                                        },
                                    },
                                },
                            },
                        }
                    }
                }
            }
        }
    }

    tool = Tool(
        app_id="app",
        tool_id="tool",
        operation_id="op",
        method_schema=method_schema,
        parameters={},
        get_url="http://unused",
        run_url="http://unused",
        version="V1.0",
    )

    result = await tool.run({}, {}, _FakeSpan())

    assert "email" not in result
    assert "street" not in result["address"]
    assert result["address"]["suite"] == "Apt. 556"
    assert result["address"]["city"] == "Gwenborough"


@pytest.mark.asyncio
async def test_tool_run_keeps_empty_object_when_all_nested_fields_hidden(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import aiohttp

    monkeypatch.setattr(aiohttp, "ClientSession", _FakeSession)

    method_schema = {
        "responses": {
            "200": {
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "number", "x-display": True},
                                "address": {
                                    "type": "object",
                                    "properties": {
                                        "street": {
                                            "type": "string",
                                            "x-display": False,
                                        },
                                        "suite": {
                                            "type": "string",
                                            "x-display": False,
                                        },
                                        "city": {
                                            "type": "string",
                                            "x-display": False,
                                        },
                                    },
                                },
                            },
                        }
                    }
                }
            }
        }
    }

    tool = Tool(
        app_id="app",
        tool_id="tool",
        operation_id="op",
        method_schema=method_schema,
        parameters={},
        get_url="http://unused",
        run_url="http://unused",
        version="V1.0",
    )

    result = await tool.run({}, {}, _FakeSpan())

    assert result["address"] == {}
