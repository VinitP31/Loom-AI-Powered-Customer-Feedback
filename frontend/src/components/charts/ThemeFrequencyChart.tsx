import type { Analytics } from "../../types/analyze";
import type { Theme } from "../../types/taxonomy";
import { themeColor } from "../../utils/colors";
import DistributionBarChart from "./DistributionBarChart";

interface ThemeFrequencyChartProps {
  analytics: Analytics;
  activeTheme?: Theme | null;
  onThemeClick?: (theme: Theme | null) => void;
}

const SHOWN = 8;

export default function ThemeFrequencyChart({ analytics, activeTheme, onThemeClick }: ThemeFrequencyChartProps) {
  const allThemes = Object.entries(analytics.theme_frequency);
  const rows = allThemes
    .map(([name, value]) => ({
      name,
      value: value ?? 0,
      color: themeColor(name as Theme),
      tied: analytics.theme_leaders.includes(name as Theme),
    }))
    // Top themes only — frontend/CLAUDE.md: "sort for readability"; a
    // long tail of 1-count themes crowds the chart without adding signal.
    // The sub-label below states the true total instead of a bare "top 8"
    // so a batch with more themes than fit isn't silently truncated.
    .sort((a, b) => b.value - a.value)
    .slice(0, SHOWN);

  const sub =
    allThemes.length > SHOWN
      ? `Primary theme of processed tickets — top ${SHOWN} of ${allThemes.length}`
      : "Primary theme of processed tickets";

  return (
    <DistributionBarChart
      title="Top Themes"
      sub={sub}
      rows={rows}
      total={analytics.total_processed}
      activeName={activeTheme}
      onBarClick={onThemeClick ? (name) => onThemeClick(name as Theme | null) : undefined}
    />
  );
}
