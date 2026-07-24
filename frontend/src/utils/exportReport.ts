/**
 * Client-side export of a report summarizing the current analysis — the
 * KPIs, the four distributions, and the executive summary. Deliberately
 * NOT a dump of every ticket: the per-ticket detail already lives in
 * FeedbackExplorer (searchable/sortable on screen), and CLAUDE.md's
 * golden rules apply here exactly as everywhere else — this only
 * formats data already in `AnalyzeResponse`, it never recomputes a
 * number or calls anything.
 */

import jsPDF from "jspdf";
import autoTable from "jspdf-autotable";
import type { AnalyzeResponse } from "../types/analyze";

// jspdf-autotable attaches this to the jsPDF instance at runtime; no
// public type export for it, so a narrow local cast stands in for `any`.
type WithAutoTable = jsPDF & { lastAutoTable: { finalY: number } };

function leaderText(single: string | null, leaders: string[]): string {
  if (single) return single;
  if (leaders.length > 0) return `Tied: ${leaders.join(", ")}`;
  return "—";
}

function pct(n: number): string {
  return `${n.toFixed(1)}%`;
}

/** One shared shape both exporters render from — a title plus a list of
 * (metric, value) rows or (name, count, %) distribution tables. */
function buildReportSections(data: AnalyzeResponse, fileName: string | null) {
  const { validation_report: v, analytics: a, summary } = data;

  const summaryRows: [string, string][] = [
    ["Total Feedback", String(v.total_rows)],
    ["Processed", String(v.processed)],
    ["Skipped Rows", String(v.skipped)],
    ["Positive %", pct(a.sentiment_distribution_pct.Positive ?? 0)],
    ["Negative %", pct(a.sentiment_distribution_pct.Negative ?? 0)],
    ["Top Category", leaderText(a.top_category, a.category_leaders)],
    ["Top Theme", leaderText(a.top_theme, a.theme_leaders)],
    ["High Urgency Count", String(a.high_urgency_count)],
    ["Actionable %", pct(a.actionable_pct)],
    ["Needs Review (fell back)", String(a.fell_back_count)],
    ["Processing Success Rate", pct(a.processing_success_rate)],
  ];

  const distributionTable = (
    dist: Partial<Record<string, number>>,
    total: number,
  ): [string, string, string][] =>
    Object.entries(dist)
      .sort((x, y) => (y[1] ?? 0) - (x[1] ?? 0))
      .map(([name, count]) => [name, String(count ?? 0), pct(total ? ((count ?? 0) / total) * 100 : 0)]);

  return {
    batchLabel: fileName ? `Batch from "${fileName}"` : "Batch",
    summaryRows,
    categoryRows: distributionTable(a.category_distribution, a.total_processed),
    themeRows: distributionTable(a.theme_frequency, a.total_processed),
    sentimentRows: distributionTable(a.sentiment_distribution, a.total_processed),
    urgencyRows: distributionTable(a.urgency_distribution, a.total_processed),
    summaryText: summary,
  };
}

export function exportReportPdf(data: AnalyzeResponse, fileName: string | null) {
  const s = buildReportSections(data, fileName);
  const doc = new jsPDF({ unit: "pt" });
  const marginX = 40;
  let y = 50;

  doc.setFontSize(16);
  doc.text("Loom — Feedback Analysis Report", marginX, y);
  y += 18;
  doc.setFontSize(10);
  doc.setTextColor(100);
  doc.text(s.batchLabel, marginX, y);
  doc.setTextColor(0);
  y += 20;

  autoTable(doc, {
    startY: y,
    head: [["Metric", "Value"]],
    body: s.summaryRows,
    margin: { left: marginX, right: marginX },
    theme: "grid",
    headStyles: { fillColor: [59, 63, 160] },
    styles: { fontSize: 9 },
  });
  y = (doc as WithAutoTable).lastAutoTable.finalY + 20;

  const distributionTables: [string, string[], string[][]][] = [
    ["Category Distribution", ["Category", "Count", "%"], s.categoryRows],
    ["Theme Frequency", ["Theme", "Count", "%"], s.themeRows],
    ["Sentiment Split", ["Sentiment", "Count", "%"], s.sentimentRows],
    ["Urgency Breakdown", ["Urgency", "Count", "%"], s.urgencyRows],
  ];

  for (const [title, head, rows] of distributionTables) {
    if (y > 700) {
      doc.addPage();
      y = 50;
    }
    doc.setFontSize(12);
    doc.text(title, marginX, y);
    y += 10;
    autoTable(doc, {
      startY: y,
      head: [head],
      body: rows,
      margin: { left: marginX, right: marginX },
      theme: "grid",
      headStyles: { fillColor: [59, 63, 160] },
      styles: { fontSize: 9 },
    });
    y = (doc as WithAutoTable).lastAutoTable.finalY + 20;
  }

  if (y > 650) {
    doc.addPage();
    y = 50;
  }
  doc.setFontSize(12);
  doc.text("Executive Summary", marginX, y);
  y += 16;
  doc.setFontSize(9);
  const wrapped = doc.splitTextToSize(s.summaryText, 515);
  doc.text(wrapped, marginX, y);

  doc.save("loom-report.pdf");
}
