/**
 * Canonical taxonomy — mirrors backend/schemas/taxonomy.py character-for-
 * character. Never invent a category/theme/sentiment/urgency string here;
 * if the backend enum changes, this file changes to match, not the other
 * way around (frontend/CLAUDE.md, golden rule 6).
 */

export type Category =
  | "Billing & Payments"
  | "Account & Access"
  | "Performance & Reliability"
  | "Functional Issues"
  | "Feature Requests & Enhancements"
  | "Usability & User Experience"
  | "Support Experience"
  | "Security"
  | "Other";

export const CATEGORIES: Category[] = [
  "Billing & Payments",
  "Account & Access",
  "Performance & Reliability",
  "Functional Issues",
  "Feature Requests & Enhancements",
  "Usability & User Experience",
  "Support Experience",
  "Security",
  "Other",
];

export type Theme =
  // Billing & Payments
  | "Failed Payment"
  | "Duplicate Charge"
  | "Refund Delay"
  | "Unexpected Charge"
  | "Subscription/Renewal Issue"
  // Account & Access
  | "Login Failure"
  | "Password Reset"
  | "OTP/2FA Problem"
  | "Account Locked"
  | "Profile Settings Issue"
  // Performance & Reliability
  | "App Crash"
  | "Slow Performance"
  | "Downtime/Outage"
  | "Timeout Error"
  | "High Resource Usage"
  // Functional Issues
  | "Function Not Working"
  | "Incorrect Data Displayed"
  | "UI Element Broken"
  | "Sync Issue"
  | "Validation Error"
  // Feature Requests & Enhancements
  | "New Feature Request"
  | "Enhancement Request"
  | "Integration Request"
  | "Workflow Improvement"
  // Usability & User Experience
  | "Confusing Navigation"
  | "Poor Layout"
  | "Hard to Find Feature"
  | "Accessibility Issue"
  // Support Experience
  | "Slow Response"
  | "Unhelpful Agent"
  | "Issue Unresolved"
  | "Difficult to Reach Support"
  // Security
  | "Unauthorized Access"
  | "Data Privacy Concern"
  | "Suspicious Activity"
  | "Vulnerability Report"
  | "Phishing/Scam Report"
  // Other
  | "General Feedback"
  | "Unclear"
  | "Requires Human Review"
  // Cross-category — valid under every category, not just one (see
  // CATEGORY_THEMES below).
  | "Positive Feedback";

export type Sentiment = "Positive" | "Neutral" | "Negative";

export type Urgency = "High" | "Medium" | "Low";

/** Category -> its owned themes, for display grouping (e.g. a filter
 * dropdown). `Positive Feedback` is valid under every category and is
 * intentionally listed under all of them here, matching the backend's
 * UNIVERSAL_THEMES special-case. */
export const CATEGORY_THEMES: Record<Category, Theme[]> = {
  "Billing & Payments": [
    "Failed Payment",
    "Duplicate Charge",
    "Refund Delay",
    "Unexpected Charge",
    "Subscription/Renewal Issue",
    "Positive Feedback",
  ],
  "Account & Access": [
    "Login Failure",
    "Password Reset",
    "OTP/2FA Problem",
    "Account Locked",
    "Profile Settings Issue",
    "Positive Feedback",
  ],
  "Performance & Reliability": [
    "App Crash",
    "Slow Performance",
    "Downtime/Outage",
    "Timeout Error",
    "High Resource Usage",
    "Positive Feedback",
  ],
  "Functional Issues": [
    "Function Not Working",
    "Incorrect Data Displayed",
    "UI Element Broken",
    "Sync Issue",
    "Validation Error",
    "Positive Feedback",
  ],
  "Feature Requests & Enhancements": [
    "New Feature Request",
    "Enhancement Request",
    "Integration Request",
    "Workflow Improvement",
    "Positive Feedback",
  ],
  "Usability & User Experience": [
    "Confusing Navigation",
    "Poor Layout",
    "Hard to Find Feature",
    "Accessibility Issue",
    "Positive Feedback",
  ],
  "Support Experience": [
    "Slow Response",
    "Unhelpful Agent",
    "Issue Unresolved",
    "Difficult to Reach Support",
    "Positive Feedback",
  ],
  Security: [
    "Unauthorized Access",
    "Data Privacy Concern",
    "Suspicious Activity",
    "Vulnerability Report",
    "Phishing/Scam Report",
    "Positive Feedback",
  ],
  Other: ["General Feedback", "Unclear", "Requires Human Review", "Positive Feedback"],
};
