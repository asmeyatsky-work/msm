"""§5: MCP servers must have schema compliance + round-trip tests."""
from server import ScoreInput


def test_schema_rejects_bad_hour():
    try:
        ScoreInput(
            click_id="c", correlation_id="t", device="m", geo="US",
            hour_of_day=99, query_intent="x", ad_creative_id="a",
            cerberus_score=0.5, rpc_7d=0, rpc_14d=0, rpc_30d=0,
            is_payday_week=False, auction_pressure=0, landing_path="/",
            visits_prev_30d=0,
        )
    except Exception:
        return
    raise AssertionError("expected rejection")


def test_schema_roundtrip():
    s = ScoreInput(
        click_id="c", correlation_id="t", device="m", geo="US",
        hour_of_day=10, query_intent="x", ad_creative_id="a",
        cerberus_score=0.5, rpc_7d=0, rpc_14d=0, rpc_30d=0,
        is_payday_week=False, auction_pressure=0, landing_path="/",
        visits_prev_30d=0,
    )
    dumped = s.model_dump()
    again = ScoreInput(**dumped)
    assert again == s
