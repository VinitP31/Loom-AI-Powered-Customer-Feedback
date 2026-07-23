import type { Analytics } from "../../types/analyze";
import type { Category } from "../../types/taxonomy";
import { CATEGORY_COLOR } from "../../utils/colors";
import DistributionBarChart from "./DistributionBarChart";

interface CategoryDistributionChartProps {
  analytics: Analytics;
}

export default function CategoryDistributionChart({ analytics }: CategoryDistributionChartProps) {
  const rows = Object.entries(analytics.category_distribution).map(([name, value]) => ({
    name,
    value: value ?? 0,
    color: CATEGORY_COLOR[name as Category] ?? CATEGORY_COLOR.Other,
    tied: analytics.category_leaders.includes(name as Category),
  }));

  return (
    <DistributionBarChart
      title="Category Distribution"
      sub="Primary category of processed tickets"
      rows={rows}
      total={analytics.total_processed}
    />
  );
}
