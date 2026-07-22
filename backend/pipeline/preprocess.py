"""Stage 2 (normalization) and Stage 3 (PII redaction) of the pipeline.

Order matters: normalize() must run, and redact_pii() must run on its
output, BEFORE any text reaches the LLM (Golden rule 7).
"""

import html
import re
import unicodedata

HTML_TAG_RE = re.compile(r"<[^>]+>")
MARKDOWN_MARKERS_RE = re.compile(
    r"(\*\*[^*]+\*\*|__[^_]+__|\*[^*]+\*|`[^`]+`|^#{1,6}\s|^>\s|^[-*+]\s|\[[^\]]+\]\([^)]+\))",
    re.MULTILINE,
)
MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")
URL_RE = re.compile(r"https?://\S+")
WHITESPACE_RE = re.compile(r"\s+")

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
# Digit-ish runs (allows space/dash/dot separators); classified by digit
# count after separators are stripped. A letter anywhere breaks the match,
# so this never eats surrounding words.
DIGIT_RUN_RE = re.compile(r"\+?\d[\d\-.\s]{3,18}\d")


def has_html(text: str) -> bool:
    return bool(HTML_TAG_RE.search(text))


def has_markdown(text: str) -> bool:
    return bool(MARKDOWN_MARKERS_RE.search(text))


def strip_html(text: str) -> str:
    """Remove tags, then decode entities (e.g. &amp; -> &)."""
    return html.unescape(HTML_TAG_RE.sub(" ", text))


def clean_markdown(text: str) -> str:
    """Drop markdown emphasis/heading/list/quote markers; keep link text,
    drop the URL."""
    text = MARKDOWN_LINK_RE.sub(r"\1", text)
    text = re.sub(r"(\*\*|__|`)", "", text)
    text = re.sub(r"^\s{0,3}#{1,6}\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s{0,3}>\s?", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s{0,3}[-*+]\s+", "", text, flags=re.MULTILINE)
    return text


def normalize_unicode_whitespace(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    return WHITESPACE_RE.sub(" ", text).strip()


def remove_urls(text: str) -> str:
    return URL_RE.sub(" ", text)


def normalize(text: str, strip_urls: bool = False) -> str:
    """Stage 2: deterministic cleanup, no PII handling here."""
    text = strip_html(text)
    text = clean_markdown(text)
    if strip_urls:
        text = remove_urls(text)
    return normalize_unicode_whitespace(text)


def _classify_digit_run(raw: str) -> str | None:
    digits = re.sub(r"\D", "", raw)
    if len(digits) >= 13:
        return "[CARD]"
    if 7 <= len(digits) <= 12:
        return "[PHONE]"
    if 5 <= len(digits) <= 6:
        return "[ID]"
    return None


def _redact_digit_runs(text: str) -> str:
    def _sub(match: re.Match) -> str:
        placeholder = _classify_digit_run(match.group(0))
        return placeholder if placeholder else match.group(0)

    return DIGIT_RUN_RE.sub(_sub, text)


def redact_pii(text: str) -> str:
    """Stage 3: regex PII redaction. Must run on already-normalized text,
    before the text is ever sent to the LLM. Order: email before digit
    runs, so an email's local-part digits aren't mistaken for a phone/ID."""
    text = EMAIL_RE.sub("[EMAIL]", text)
    text = _redact_digit_runs(text)
    return text


def clean_and_redact(text: str, strip_urls: bool = False) -> str:
    """Full Stage 2 + Stage 3 pipeline for one ticket's feedback text."""
    return redact_pii(normalize(text, strip_urls=strip_urls))


def word_count(text: str) -> int:
    return len(text.split())


def is_long_ticket(cleaned_text: str, word_limit: int) -> bool:
    """Single source of truth for the long-ticket threshold check. Must be
    called on the cleaned/normalized text (post clean_and_redact), and the
    same result must drive both the validation-report warning and the
    summarization-routing decision — never two independent word counts on
    different text versions (Loom_Source_of_Truth.md, Stage 4)."""
    return word_count(cleaned_text) > word_limit
