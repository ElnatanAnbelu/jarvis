"""P1: brain/llm.py local-model client — model-free (mocks Ollama HTTP)."""
from brain import llm


def test_to_ollama_tools_converts_registry_schema():
    schemas = [{
        "name": "t", "description": "d",
        "input_schema": {"type": "object", "properties": {"a": {"type": "string"}}, "required": ["a"]},
    }]
    out = llm.to_ollama_tools(schemas)
    assert out[0]["type"] == "function"
    assert out[0]["function"]["name"] == "t"
    assert out[0]["function"]["parameters"]["properties"] == {"a": {"type": "string"}}


def test_parse_tool_calls_handles_dict_and_string_and_bad_args():
    msg = {"tool_calls": [
        {"function": {"name": "a", "arguments": {"x": 1}}},
        {"function": {"name": "b", "arguments": '{"y": 2}'}},
        {"function": {"name": "c", "arguments": "not json"}},
    ]}
    calls = llm._parse_tool_calls(msg)
    assert calls[0] == {"name": "a", "arguments": {"x": 1}}
    assert calls[1] == {"name": "b", "arguments": {"y": 2}}
    assert calls[2] == {"name": "c", "arguments": {}}  # unparseable → empty


def test_chat_parses_response(monkeypatch):
    class FakeResp:
        status_code = 200
        def raise_for_status(self):
            pass
        def json(self):
            return {"message": {"content": "hi", "tool_calls": [
                {"function": {"name": "t", "arguments": {"a": "b"}}}]}}

    monkeypatch.setattr(llm.requests, "post", lambda *a, **k: FakeResp())
    r = llm.chat([{"role": "user", "content": "x"}])
    assert r["content"] == "hi"
    assert r["tool_calls"] == [{"name": "t", "arguments": {"a": "b"}}]


def test_available_false_on_error(monkeypatch):
    def boom(*a, **k):
        raise OSError("no server")
    monkeypatch.setattr(llm.requests, "get", boom)
    assert llm.available() is False
