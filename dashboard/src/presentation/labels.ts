// Plain-English translations of the engineering feature names so a non-technical
// executive doesn't see 'affinity_score' or 'rpc_14d' on the dashboard.
// Schema: PRD V2 (Credit Cards) §7.1.

export const FEATURE_LABEL: Record<string, string> = {
  hour_of_day:        "Hour of day",
  affinity_score:     "Likely-to-apply score",
  rpc_14d:            "Recent 14-day earnings",
  rpc_60d:            "Recent 60-day earnings",
  prior_applicant:    "Already applied before",
  income_band_bucket: "Income band",
  auction_pressure:   "Auction competition",
  visits_prev_30d:    "Repeat visitor",
  device:             "Device type",
  geo:                "Country / region",
  vertical_id:        "Product line",
  product_type:       "Card type",
  card_product_id:    "Card product",
  query_intent:       "Search intent",
  ad_creative_id:     "Ad creative",
  landing_path:       "Landing page",
  // Phoebe (PRD V2 §7.1).
  phoebe_calculator_used:      "Used a calculator",
  phoebe_guides_read:          "Guides read (30d)",
  phoebe_cards_compared:       "Cards compared (30d)",
  phoebe_session_engagement_s: "Time engaged (seconds)",
};

export function humanise(feature: string): string {
  return FEATURE_LABEL[feature] ?? feature.replace(/_/g, " ");
}
