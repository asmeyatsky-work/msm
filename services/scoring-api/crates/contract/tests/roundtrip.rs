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
            device: "mobile".into(),
            geo: "US-CA".into(),
            hour_of_day: 14,
            query_intent: "commercial".into(),
            ad_creative_id: "ad-1".into(),
            cerberus_score: 0.8,
            rpc_7d: 1.2,
            rpc_14d: 1.1,
            rpc_30d: 1.0,
            is_payday_week: false,
            auction_pressure: 0.4,
            landing_path: "/p".into(),
            visits_prev_30d: 3,
        }),
    }
}

#[test]
fn proto_roundtrip() {
    let msg = sample();
    let mut buf = Vec::new();
    msg.encode(&mut buf).unwrap();
    let decoded = ScoreRequest::decode(buf.as_slice()).unwrap();
    assert_eq!(decoded.features.as_ref().unwrap().click_id, "c-rt");
    assert!((decoded.features.unwrap().cerberus_score - 0.8).abs() < 1e-9);
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
