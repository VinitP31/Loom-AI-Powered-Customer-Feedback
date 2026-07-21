"""Canonical taxonomy — single source of truth for categories, themes,
sentiment, and urgency. Every other module (prompts, analytics, pipeline)
imports from here. Never redefine these strings elsewhere.
"""

from enum import Enum


class Category(str, Enum):
    BILLING_PAYMENTS = "Billing & Payments"
    ACCOUNT_ACCESS = "Account & Access"
    PERFORMANCE_RELIABILITY = "Performance & Reliability"
    FUNCTIONAL_ISSUES = "Functional Issues"
    FEATURE_REQUESTS = "Feature Requests & Enhancements"
    USABILITY_UX = "Usability & User Experience"
    SUPPORT_EXPERIENCE = "Support Experience"
    OTHER = "Other"


class Theme(str, Enum):
    # Billing & Payments
    FAILED_PAYMENT = "Failed Payment"
    DUPLICATE_CHARGE = "Duplicate Charge"
    REFUND_DELAY = "Refund Delay"
    UNEXPECTED_CHARGE = "Unexpected Charge"
    SUBSCRIPTION_RENEWAL_ISSUE = "Subscription/Renewal Issue"
    # Account & Access
    LOGIN_FAILURE = "Login Failure"
    PASSWORD_RESET = "Password Reset"
    OTP_2FA_PROBLEM = "OTP/2FA Problem"
    ACCOUNT_LOCKED = "Account Locked"
    PROFILE_SETTINGS_ISSUE = "Profile Settings Issue"
    # Performance & Reliability
    APP_CRASH = "App Crash"
    SLOW_PERFORMANCE = "Slow Performance"
    DOWNTIME_OUTAGE = "Downtime/Outage"
    TIMEOUT_ERROR = "Timeout Error"
    HIGH_RESOURCE_USAGE = "High Resource Usage"
    # Functional Issues
    FUNCTION_NOT_WORKING = "Function Not Working"
    INCORRECT_DATA_DISPLAYED = "Incorrect Data Displayed"
    UI_ELEMENT_BROKEN = "UI Element Broken"
    SYNC_ISSUE = "Sync Issue"
    VALIDATION_ERROR = "Validation Error"
    # Feature Requests & Enhancements
    NEW_FEATURE_REQUEST = "New Feature Request"
    ENHANCEMENT_REQUEST = "Enhancement Request"
    INTEGRATION_REQUEST = "Integration Request"
    WORKFLOW_IMPROVEMENT = "Workflow Improvement"
    # Usability & User Experience
    CONFUSING_NAVIGATION = "Confusing Navigation"
    POOR_LAYOUT = "Poor Layout"
    HARD_TO_FIND_FEATURE = "Hard to Find Feature"
    ACCESSIBILITY_ISSUE = "Accessibility Issue"
    POSITIVE_EXPERIENCE = "Positive Experience"
    # Support Experience
    SLOW_RESPONSE = "Slow Response"
    UNHELPFUL_AGENT = "Unhelpful Agent"
    ISSUE_UNRESOLVED = "Issue Unresolved"
    DIFFICULT_TO_REACH_SUPPORT = "Difficult to Reach Support"
    # Other
    GENERAL_FEEDBACK = "General Feedback"
    UNCLEAR = "Unclear"


class Sentiment(str, Enum):
    POSITIVE = "Positive"
    NEUTRAL = "Neutral"
    NEGATIVE = "Negative"


class Urgency(str, Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


# Category -> allowed themes. Enforced by the theme_belongs_to_category
# validator on IssueEnrichment / TicketClassification below.
CATEGORY_THEMES: dict[Category, set[Theme]] = {
    Category.BILLING_PAYMENTS: {
        Theme.FAILED_PAYMENT,
        Theme.DUPLICATE_CHARGE,
        Theme.REFUND_DELAY,
        Theme.UNEXPECTED_CHARGE,
        Theme.SUBSCRIPTION_RENEWAL_ISSUE,
    },
    Category.ACCOUNT_ACCESS: {
        Theme.LOGIN_FAILURE,
        Theme.PASSWORD_RESET,
        Theme.OTP_2FA_PROBLEM,
        Theme.ACCOUNT_LOCKED,
        Theme.PROFILE_SETTINGS_ISSUE,
    },
    Category.PERFORMANCE_RELIABILITY: {
        Theme.APP_CRASH,
        Theme.SLOW_PERFORMANCE,
        Theme.DOWNTIME_OUTAGE,
        Theme.TIMEOUT_ERROR,
        Theme.HIGH_RESOURCE_USAGE,
    },
    Category.FUNCTIONAL_ISSUES: {
        Theme.FUNCTION_NOT_WORKING,
        Theme.INCORRECT_DATA_DISPLAYED,
        Theme.UI_ELEMENT_BROKEN,
        Theme.SYNC_ISSUE,
        Theme.VALIDATION_ERROR,
    },
    Category.FEATURE_REQUESTS: {
        Theme.NEW_FEATURE_REQUEST,
        Theme.ENHANCEMENT_REQUEST,
        Theme.INTEGRATION_REQUEST,
        Theme.WORKFLOW_IMPROVEMENT,
    },
    Category.USABILITY_UX: {
        Theme.CONFUSING_NAVIGATION,
        Theme.POOR_LAYOUT,
        Theme.HARD_TO_FIND_FEATURE,
        Theme.ACCESSIBILITY_ISSUE,
        Theme.POSITIVE_EXPERIENCE,
    },
    Category.SUPPORT_EXPERIENCE: {
        Theme.SLOW_RESPONSE,
        Theme.UNHELPFUL_AGENT,
        Theme.ISSUE_UNRESOLVED,
        Theme.DIFFICULT_TO_REACH_SUPPORT,
    },
    Category.OTHER: {
        Theme.GENERAL_FEEDBACK,
        Theme.UNCLEAR,
    },
}
