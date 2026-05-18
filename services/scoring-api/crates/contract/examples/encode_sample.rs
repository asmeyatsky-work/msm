use msm_scoring_contract::v1::{ClickFeatures, ScoreRequest};
use prost::Message;

fn main() {
    let msg = ScoreRequest {
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
        }),
    };
    let mut buf = Vec::new();
    msg.encode(&mut buf).unwrap();
    for b in &buf {
        print!("{:02x}", b);
    }
}
