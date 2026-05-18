"""§5: MCP servers must have schema compliance + round-trip tests."""
from server import ScoreInput


def _kwargs(**over):
    base = dict(
        click_id="c", correlation_id="t", vertical_id="credit_cards",
        device="m", geo="GB", hour_of_day=10,
        product_type="cashback", card_product_id="card-x",
        query_intent="compare", affinity_score=0.5,
        ad_creative_id="a", prior_applicant=False,
        income_band_bucket="mid", auction_pressure=0.5,
        rpc_14d=0.0, rpc_60d=0.0, landing_path="/", visits_prev_30d=0,
    )
    base.update(over)
    return base


def test_schema_rejects_bad_hour():
    try:
        ScoreInput(**_kwargs(hour_of_day=99))
    except Exception:
        return
    raise AssertionError("expected rejection")


def test_schema_roundtrip():
    s = ScoreInput(**_kwargs())
    dumped = s.model_dump()
    again = ScoreInput(**dumped)
    assert again == s
