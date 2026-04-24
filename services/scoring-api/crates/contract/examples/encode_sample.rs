use msm_scoring_contract::v1::{ClickFeatures, ScoreRequest};
use prost::Message;

fn main() {
    let msg = ScoreRequest {
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
    };
    let mut buf = Vec::new();
    msg.encode(&mut buf).unwrap();
    for b in &buf {
        print!("{:02x}", b);
    }
}
