"""Tests for history, stocks and AI helpers. Stdlib-only (no pytest import) so they also run anywhere.
All numbers are SYNTHETIC fixtures used only by tests."""
from app import ai
from app.history import HistoryStore, summarize
from app.stocks import StockService, valid_symbol


def _raises(exc, fn, *a):
    try:
        fn(*a)
    except exc:
        return True
    return False


def _item(asset="usd_free_irt", price=100.0, ts=0, fresh="delayed"):
    return {"asset_id": asset, "price": price, "unit": "IRT", "source": "T", "ts": ts, "freshness": fresh}


def test_history_records_throttles_and_skips_stale():
    h = HistoryStore(":memory:", min_interval_s=300)
    assert h.record([_item(ts=1000)], now_ts=1000) == 1
    assert h.record([_item(ts=1100, price=101)], now_ts=1100) == 0      # inside min interval
    assert h.record([_item(ts=1400, price=102)], now_ts=1400) == 1
    assert h.record([_item(ts=2000, price=103, fresh="stale")], now_ts=2000) == 0  # stale never stored
    assert h.record([_item(ts=2000, price=0)], now_ts=2000) == 0                    # invalid never stored
    assert [p for _, p in h.series("usd_free_irt", 0)] == [100.0, 102.0]
    assert h.unit_of("usd_free_irt") == "IRT" and h.unit_of("nope") is None


def test_history_prunes_old_points():
    h = HistoryStore(":memory:", min_interval_s=1, retention_days=1)
    h.record([_item(ts=10)], now_ts=10)
    h.record([_item(ts=200000, price=5)], now_ts=200000)  # > 1 day later
    assert [p for _, p in h.series("usd_free_irt", 0)] == [5.0]


def test_summarize_requires_enough_history():
    assert summarize([])["sufficient"] is False
    one = summarize([(0, 100.0)])
    assert one["sufficient"] is False and one["change_pct"] is None
    short = summarize([(0, 100.0), (60, 110.0)])           # span too short
    assert short["sufficient"] is False and short["change_pct"] is None
    ok = summarize([(0, 100.0), (3600, 110.0)])
    assert ok["sufficient"] is True and round(ok["change_pct"], 6) == 10.0
    assert ok["min"] == 100.0 and ok["max"] == 110.0


def test_series_thinning_keeps_last_point():
    h = HistoryStore(":memory:", min_interval_s=1)
    for i in range(50):
        h.record([_item(ts=1000 + i * 10, price=100 + i)], now_ts=1000 + i * 10)
    s = h.series("usd_free_irt", 0, limit=10)
    assert len(s) == 10 and s[-1][1] == 149.0


def test_stock_symbol_validation_and_no_provider():
    assert valid_symbol("فولاد") and valid_symbol("خودرو") and valid_symbol("IKCO")
    assert not valid_symbol("") and not valid_symbol("a;DROP") and not valid_symbol("x" * 40)
    s = StockService(":memory:")
    st = s.status()
    assert st["provider_configured"] is False and "No verified" in st["message"]
    assert s.quotes() == []                                  # nothing is invented
    assert s.add_symbol("فولاد", "Foolad") is True
    assert s.add_symbol("فولاد") is False                    # no duplicates
    assert [x["symbol"] for x in s.symbols()] == ["فولاد"]
    assert _raises(ValueError, s.add_symbol, "bad;sym")


def test_stock_store_only_known_valid_quotes():
    s = StockService(":memory:")
    s.add_symbol("فولاد")
    n = s.store_quotes([
        {"symbol": "فولاد", "price": 200.0, "previous_close": 160.0},
        {"symbol": "ناشناس", "price": 5.0},        # unknown symbol ignored
        {"symbol": "فولاد", "price": -1},          # invalid ignored
    ], "TestSource", now_ts=5000)
    assert n == 1
    q = s.quotes()[0]
    assert q["price"] == 200.0 and round(q["change_pct"], 6) == 25.0 and q["source"] == "TestSource"
    assert s.history("فولاد", 0) == [(5000, 200.0)]
    assert s.remove_symbol("فولاد") and s.quotes() == []


def test_ai_configuration_requires_all_three():
    assert not ai.is_configured("openai", "", "https://x", "m")
    assert not ai.is_configured("openai", "k", "", "m")
    assert not ai.is_configured("openai", "k", "https://x", "")
    assert not ai.is_configured("weird", "k", "https://x", "m")
    assert ai.is_configured("openai", "k", "https://x", "m")
    svc = ai.AiService("openai", "SECRET", "https://x", "m", 5, 10)
    assert "SECRET" not in str(svc.info()) and "https://x" not in str(svc.info())



def test_ai_fallback_configuration_is_safe():
    for provider in ("openai", "anthropic", "gemini", "groq", "openrouter"):
        assert ai.is_configured(provider, "secret", "https://api.example.com", "model")

    svc = ai.AiService(
        "gemini", "PRIMARY_SECRET", "https://primary.example.com", "primary-model",
        5, 100,
        fallbacks=[
            {
                "provider": "groq",
                "api_key": "FALLBACK_SECRET",
                "base_url": "https://fallback.example.com",
                "model": "fallback-model",
            },
        ],
    )
    info = str(svc.info())
    assert svc.configured
    assert svc.info()["providers"] == ["gemini", "groq"]
    assert "SECRET" not in info
    assert "example.com" not in info


def test_ai_fallback_uses_next_provider():
    import asyncio

    svc = ai.AiService(
        "gemini", "key1", "https://one.example.com", "model-one",
        5, 100,
        fallbacks=[
            {
                "provider": "groq",
                "api_key": "key2",
                "base_url": "https://two.example.com",
                "model": "model-two",
            },
        ],
    )
    calls = []

    async def fake_complete(config, system, messages):
        calls.append(config["provider"])
        if config["provider"] == "gemini":
            raise ai.AiError("ai_upstream_error")
        return "Fallback answer"

    svc._complete_with_provider = fake_complete
    result = asyncio.run(
        svc.complete_result("system", [{"role": "user", "content": "hello"}])
    )

    assert calls == ["gemini", "groq"]
    assert result.text == "Fallback answer"
    assert result.provider == "groq"
    assert result.model == "model-two"


def test_ai_invalid_input_does_not_trigger_fallback():
    import asyncio

    svc = ai.AiService(
        "gemini", "key1", "https://one.example.com", "model-one",
        5, 100,
        fallbacks=[
            {
                "provider": "groq",
                "api_key": "key2",
                "base_url": "https://two.example.com",
                "model": "model-two",
            },
        ],
    )
    calls = []

    async def fake_complete(config, system, messages):
        calls.append(config["provider"])
        return "unexpected"

    svc._complete_with_provider = fake_complete

    try:
        asyncio.run(svc.complete_result("system", []))
        assert False, "Invalid input should raise AiError"
    except ai.AiError as error:
        assert error.code == "invalid_input"

    assert calls == []

def test_validate_messages_rules():
    ok = ai.validate_messages([{"role": "user", "content": " hi "}])
    assert ok == [{"role": "user", "content": "hi"}]
    assert _raises(ai.AiError, ai.validate_messages, [])
    assert _raises(ai.AiError, ai.validate_messages, [{"role": "system", "content": "x"}])
    assert _raises(ai.AiError, ai.validate_messages, [{"role": "assistant", "content": "x"}])  # last must be user
    assert _raises(ai.AiError, ai.validate_messages, [{"role": "user", "content": "x" * 2001}])
    assert _raises(ai.AiError, ai.validate_messages, [{"role": "user", "content": "  "}])
    many = [{"role": "user", "content": "a"}] * 21
    assert _raises(ai.AiError, ai.validate_messages, many)


def test_facts_hide_history_when_insufficient_and_prompt_has_rules():
    q = [{"asset_id": "usd_free_irt", "price": 100.0, "unit": "IRT", "market": "free",
          "source": "T", "freshness": "delayed", "change_pct": None, "flags": []}]
    facts = ai.build_facts(q, {"usd_free_irt": summarize([(0, 100.0)])}, ["eur_free_irt"])
    f = facts["quotes"][0]
    assert f["history_change_pct"] is None and f["history_min"] is None
    assert facts["unavailable_assets"] == ["eur_free_irt"]
    p = ai.system_prompt("fa", facts, 0)
    assert "Persian" in p and "ONLY the DATA block" in p and "eur_free_irt" in p
    assert "buy/sell" in p


def test_response_parsing_and_http_mapping():
    assert ai.parse_openai({"choices": [{"message": {"content": " hello "}}]}) == "hello"
    assert ai.parse_anthropic({"content": [{"type": "text", "text": "a"}, {"type": "text", "text": "b"}]}) == "ab"
    assert _raises(ai.AiError, ai.parse_openai, {"choices": []})
    assert _raises(ai.AiError, ai.parse_anthropic, {"content": []})
    assert ai.map_http_status(401).code == "ai_auth_failed"
    assert ai.map_http_status(429).status == 429
    assert ai.map_http_status(500).code == "ai_upstream_error"


def test_complete_without_key_raises_not_configured():
    import asyncio
    svc = ai.AiService("openai", "", "", "", 5, 10)
    try:
        asyncio.run(svc.complete("s", [{"role": "user", "content": "x"}]))
    except ai.AiError as e:
        assert e.code == "ai_not_configured" and e.status == 503
    else:
        raise AssertionError("expected AiError")
