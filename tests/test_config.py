from app.config import load_settings


def test_defaults_when_env_is_empty(monkeypatch):
    for key in ("RFP_SERVICE_NAME", "RFP_RETRIEVER", "RFP_TOP_K", "RFP_MAX_TOP_K",
                "RFP_CORPUS_DIR"):
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


def test_settings_do_not_read_generation_env(monkeypatch):
    """생성기 관련 환경 변수는 아예 읽지 않는다 — 설정 객체에 흔적이 남지 않는다."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-secret-value")
    monkeypatch.setenv("RFP_ANSWER_MODEL", "some-model")

    s = load_settings()

    assert "sk-secret-value" not in repr(s)
    assert "some-model" not in repr(s)
    assert not hasattr(s, "generation_enabled")
    assert not hasattr(s, "has_answer_key")
    assert not hasattr(s, "answer_model")
