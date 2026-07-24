import type { Analytics } from "../../types/analyze";
import type { Sentiment } from "../../types/taxonomy";
import { SENTIMENT_COLOR } from "../../utils/colors";
import DonutChart from "./DonutChart";

interface SentimentDistributionChartProps {
  analytics: Analytics;
}

const ORDER: Sentiment[] = ["Positive", "Neutral", "Negative"];

export default function SentimentDistributionChart({ analytics }: SentimentDistributionChartProps) {
  const rows = ORDER.filter((s) => analytics.sentiment_distribution[s] !== undefined).map((s) => ({
    name: s,
    value: analytics.sentiment_distribution[s] ?? 0,
    color: SENTIMENT_COLOR[s],
  }));

  return (
    <DonutChart title="Sentiment Split" sub="Share of processed tickets" rows={rows} total={analytics.total_processed} />
  );
}
