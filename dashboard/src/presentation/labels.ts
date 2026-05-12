// Plain-English translations of the engineering feature names so a non-technical
// executive doesn't see 'cerberus_score' or 'rpc_14d' on the dashboard.

export const FEATURE_LABEL: Record<string, string> = {
  hour_of_day:     "Hour of day",
  cerberus_score:  "User trust score",
  rpc_7d:          "Recent 7-day earnings",
  rpc_14d:         "Recent 14-day earnings",
  rpc_30d:         "Recent 30-day earnings",
  is_payday_week:  "Payday week",
  auction_pressure:"Auction competition",
  visits_prev_30d: "Repeat visitor",
  device:          "Device type",
  geo:             "Country",
  query_intent:    "Search intent",
  ad_creative_id:  "Ad creative",
  landing_path:    "Landing page",
};

export function humanise(feature: string): string {
  return FEATURE_LABEL[feature] ?? feature.replace(/_/g, " ");
}
