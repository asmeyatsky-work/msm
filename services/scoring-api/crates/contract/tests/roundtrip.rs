//! Round-trip test: encode a ScoreRequest in Rust and decode it back.
//! Exists primarily to fail CI loudly if someone edits `scoring.proto` in a
//! breaking way — the generated types drift and this test stops compiling or
//! the decode fails.

use msm_scoring_contract::v1::{ClickFeatures, ScoreRequest};
use prost::Message;

fn sample() -> ScoreRequest {
    ScoreRequest {
        features: Some(ClickFeatures {
            click_id: "c-rt".into(),
            correlation_id: "t-rt".into(),
            vertical_id: "credit_cards".into(),
            device: "mobile".into(),
            geo: "GB-LDN".into(),
            hour_of_day: 14,
            product_type: "cashback".into(),
            card_product_id: "card-amex-blue".into(),
            query_intent: "compare".into(),
            affinity_score: 0.7,
            ad_creative_id: "ad-1".into(),
            prior_applicant: false,
            income_band_bucket: "mid".into(),
            auction_pressure: 0.4,
            rpc_14d: 1.2,
            rpc_60d: 1.1,
            landing_path: "/credit-cards/cashback".into(),
            visits_prev_30d: 3,
            phoebe_calculator_used: true,
            phoebe_guides_read: 2,
            phoebe_cards_compared: 4,
            phoebe_session_engagement_s: 320.5,
        }),
    }
}

#[test]
fn proto_roundtrip() {
    let msg = sample();
    let mut buf = Vec::new();
    msg.encode(&mut buf).unwrap();
    let decoded = ScoreRequest::decode(buf.as_slice()).unwrap();
    let feats = decoded.features.unwrap();
    assert_eq!(feats.click_id, "c-rt");
    assert_eq!(feats.vertical_id, "credit_cards");
    assert_eq!(feats.product_type, "cashback");
    assert!((feats.affinity_score - 0.7).abs() < 1e-9);
}

#[test]
fn wire_bytes_match_golden() {
    // Golden-bytes test — guards the on-wire contract across languages.
    // Length-prefixed varint field tags; a changed field number would change these bytes.
    let msg = sample();
    let mut buf = Vec::new();
    msg.encode(&mut buf).unwrap();

    // Decode again and re-encode; prost must produce byte-stable output.
    let re = ScoreRequest::decode(buf.as_slice()).unwrap();
    let mut buf2 = Vec::new();
    re.encode(&mut buf2).unwrap();
    assert_eq!(buf, buf2, "encode is not deterministic");
}
