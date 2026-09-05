from app.config import load_settings


def test_defaults_when_env_is_empty(monkeypatch):
    for key in ("RFP_SERVICE_NAME", "RFP_RETRIEVER", "RFP_TOP_K", "RFP_MAX_TOP_K",
                "RFP_CORPUS_DIR", "RFP_ANSWER_MODEL", "OPENAI_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    s = load_settings()
    assert (s.service_name, s.retriever, s.top_k, s.max_top_k) == ("rfp-service", "keyword", 5, 20)


def test_bad_numbers_fall_back(monkeypatch):
    monkeypatch.setenv("RFP_TOP_K", "not-a-number")
    monkeypatch.setenv("RFP_MAX_TOP_K", "-3")
    s = load_settings()
    assert (s.top_k, s.max_top_k) == (5, 20)


def test_top_k_cannot_exceed_max(monkeypatch):
    monkeypatch.setenv("RFP_TOP_K", "999")
    monkeypatch.setenv("RFP_MAX_TOP_K", "7")
    assert load_settings().top_k == 7


def test_generation_stays_off_without_both_key_and_model(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.delenv("RFP_ANSWER_MODEL", raising=False)
    assert load_settings().generation_enabled is False


def test_api_key_value_is_not_stored(monkeypatch):
    """설정 객체에 키 값 자체를 담지 않는다 — 존재 여부만 남긴다."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-secret-value")
    s = load_settings()
    assert s.has_answer_key is True
    assert "sk-secret-value" not in repr(s)
