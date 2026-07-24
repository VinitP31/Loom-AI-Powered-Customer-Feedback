import type { Analytics } from "../../types/analyze";
import type { Urgency } from "../../types/taxonomy";
import { URGENCY_COLOR } from "../../utils/colors";
import DonutChart from "./DonutChart";

interface UrgencyBreakdownChartProps {
  analytics: Analytics;
}

const ORDER: Urgency[] = ["High", "Medium", "Low"];

export default function UrgencyBreakdownChart({ analytics }: UrgencyBreakdownChartProps) {
  const rows = ORDER.filter((u) => analytics.urgency_distribution[u] !== undefined).map((u) => ({
    name: u,
    value: analytics.urgency_distribution[u] ?? 0,
    color: URGENCY_COLOR[u],
  }));

  return (
    <DonutChart
      title="Urgency Breakdown"
      sub="By impact, independent of tone — primary issue only"
      rows={rows}
      total={analytics.total_processed}
    />
  );
}
