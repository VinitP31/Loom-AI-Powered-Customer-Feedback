import type { Analytics } from "../../types/analyze";
import type { Theme } from "../../types/taxonomy";
import DistributionBarChart from "./DistributionBarChart";

interface ThemeFrequencyChartProps {
  analytics: Analytics;
  activeTheme?: Theme | null;
  onThemeClick?: (theme: Theme | null) => void;
}

// Themes aren't category-colored (a theme can appear under any category,
// and Positive Feedback spans all of them) — a single accent hue keeps
// this chart from implying a category-color relationship that isn't there.
const THEME_BAR_COLOR = "#3b3fa0";

export default function ThemeFrequencyChart({ analytics, activeTheme, onThemeClick }: ThemeFrequencyChartProps) {
  const rows = Object.entries(analytics.theme_frequency)
    .map(([name, value]) => ({
      name,
      value: value ?? 0,
      color: THEME_BAR_COLOR,
      tied: analytics.theme_leaders.includes(name as Theme),
    }))
    // Top themes only — frontend/CLAUDE.md: "sort for readability"; a
    // long tail of 1-count themes crowds the chart without adding signal.
    .sort((a, b) => b.value - a.value)
    .slice(0, 8);

  return (
    <DistributionBarChart
      title="Top Themes"
      sub="Primary theme of processed tickets, top 8 by frequency"
      rows={rows}
      total={analytics.total_processed}
      activeName={activeTheme}
      onBarClick={onThemeClick ? (name) => onThemeClick(name as Theme | null) : undefined}
    />
  );
}
