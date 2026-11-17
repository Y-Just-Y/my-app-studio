"""Require indexed adoption evidence for budget-status claims, not numeric facts."""

from datetime import date
import re

_WORD = r"(?:approv(?:e|ed|al)|adopt(?:ed|ion)?|final(?:ized|ised)?)"
_STATUS = re.compile(rf"\b{_WORD}\b", re.IGNORECASE)
_PHRASE = rf"{_WORD}(?:\s+(?:(?:and|or|nor)\s+)?{_WORD})*"
_NEGATED = re.compile(
    rf"\b(?:not|never|no)\s+(?:(?:an?|the|verified)\s+)?{_PHRASE}\b"
    rf"|\b(?:cannot|can't|could not|unable to|do not|does not)\s+"
    rf"(?:verify|confirm|establish|find|determine|have)\s+"
    rf"(?:(?:the|an?|any|\d{{4}})\s+)?{_PHRASE}\b"
    rf"|\b(?:no|not|not enough|insufficient|missing)\s+(?:verified\s+)?"
    rf"(?:evidence|proof|confirmation)(?:\s+\w+){{0,5}}\s+{_PHRASE}\b"
    rf"|\b{_WORD}(?:\s+\w+){{0,3}}\s+"
    r"(?:not\s+(?:been\s+)?(?:verified|confirmed|established|supplied)|"
    r"unverified|unconfirmed|unknown)\b",
    re.IGNORECASE,
)
_YEAR = re.compile(r"(?<![\w$])(?:FY\s*)?(\d{4})(?![\w.,%])", re.IGNORECASE)


def _metadata(chunk):
    value = chunk.get("metadata", {}) if isinstance(chunk, dict) else {}
    return value if isinstance(value, dict) else {}


def _budget_context(text, chunks):
    if re.search(r"\bbudget\b", text, re.IGNORECASE):
        return True
    if re.search(
        r"\b(?:ordinances?|resolutions?|meetings?|agendas?|events?)\b",
        text,
        re.IGNORECASE,
    ):
        return False
    return any(_metadata(row).get("kind") == "budget" for row in chunks)


def _positive_status(text):
    text = re.sub(r"[*_`]", "", text)
    clauses = re.split(r"[,;.!?\n]|\b(?:but|however|yet)\b", text, flags=re.IGNORECASE)
    return any(_STATUS.search(_NEGATED.sub("", clause)) for clause in clauses)


def _years(text):
    return set(_YEAR.findall(text))


def _verified_years(chunks):
    years = set()
    for chunk in chunks:
        metadata = _metadata(chunk)
        status = metadata.get("budget_status", metadata.get("status", ""))
        year = str(metadata.get("fiscal_year", metadata.get("year", "")))
        if (
            metadata.get("adoption_verified") is not True
            or str(status).lower() not in {"adopted", "approved", "final"}
            or not re.fullmatch(r"\d{4}", year)
        ):
            continue
        try:
            date.fromisoformat(metadata.get("adoption_date"))
        except (TypeError, ValueError):
            continue
        years.add(year)
    return years


def _missing():
    return {
        "answer": (
            "The indexed sources do not provide enough verified adoption evidence "
            "for this budget claim and fiscal year. I cannot establish an approved "
            "or adopted budget amount from this evidence."
        ),
        "citation_ids": [],
        "insufficient_evidence": True,
    }


def guard_request(question, chunks):
    """Stop explicit approved-budget requests lacking matching adoption proof."""
    question, chunks = str(question or ""), chunks or []
    if _budget_context(question, chunks) and _positive_status(question):
        verified, requested = _verified_years(chunks), _years(question)
        if not verified or not requested.issubset(verified):
            return _missing()
    return None


def guard_answer(question, result, chunks):
    """Check status and fiscal-year support in cited evidence; keep model metadata."""
    question, chunks = str(question or ""), chunks or []
    answer = str(result.get("answer", ""))
    cited = set(result.get("citation_ids", []))
    evidence = [row for row in chunks if row.get("chunk_id") in cited]
    budget = any(_metadata(row).get("kind") == "budget" for row in evidence)
    affirmative = _positive_status(answer)
    requested = _positive_status(question) and not result.get("insufficient_evidence")
    if (budget or _budget_context(question + " " + answer, evidence)) and (
        affirmative or requested
    ):
        verified = _verified_years(evidence)
        years = _years(question) | _years(answer)
        if not verified or not years or not years.issubset(verified):
            return {**result, **_missing()}
    return result
