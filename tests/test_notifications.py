from __future__ import annotations

import urllib.error

from equitymind import notifications


def test_build_digest_contains_ranking(analysis_report):
    text = notifications.build_digest(analysis_report)
    assert "EquityMind" in text
    assert "Ranking" in text
    # every ranked ticker appears
    for e in analysis_report.comparison.entries:
        assert e.ticker in text


def test_send_telegram_without_credentials(monkeypatch):
    monkeypatch.delenv("EQUITYMIND_TELEGRAM_TOKEN", raising=False)
    monkeypatch.delenv("EQUITYMIND_TELEGRAM_CHAT_ID", raising=False)
    assert notifications.send_telegram_message("hi") is False


def test_send_telegram_success(monkeypatch):
    captured = {}

    def fake_post(url, payload, *, timeout=10.0):
        captured["url"] = url
        captured["payload"] = payload
        return {"ok": True, "result": {"message_id": 1}}

    monkeypatch.setattr(notifications, "_http_post_json", fake_post)
    ok = notifications.send_telegram_message("hello", token="T", chat_id="42")
    assert ok is True
    assert "botT/sendMessage" in captured["url"]
    assert captured["payload"]["chat_id"] == "42"
    assert captured["payload"]["text"] == "hello"


def test_send_telegram_api_rejection(monkeypatch):
    monkeypatch.setattr(
        notifications,
        "_http_post_json",
        lambda url, payload, **kw: {"ok": False, "description": "bad token"},
    )
    assert notifications.send_telegram_message("x", token="T", chat_id="42") is False


def test_send_telegram_network_error(monkeypatch):
    def boom(url, payload, **kw):
        raise urllib.error.URLError("no network")

    monkeypatch.setattr(notifications, "_http_post_json", boom)
    assert notifications.send_telegram_message("x", token="T", chat_id="42") is False


def test_notify_report_sends_digest(monkeypatch, analysis_report):
    sent = {}

    def fake_post(url, payload, *, timeout=10.0):
        sent["text"] = payload["text"]
        return {"ok": True}

    monkeypatch.setattr(notifications, "_http_post_json", fake_post)
    assert notifications.notify_report(analysis_report, token="T", chat_id="42") is True
    assert "EquityMind" in sent["text"]
