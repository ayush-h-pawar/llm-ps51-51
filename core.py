"""Validated extraction, deterministic range checks, and report processing."""
import io
import json
import re
from decimal import Decimal, InvalidOperation
from pypdf import PdfReader
from prompts import EXTRACT_PROMPT, EXPLAIN_PROMPT

DISCLAIMER = "Not medical advice — consult a doctor. Verify extracted values against the original report."
MAX_CHARS = 14000
MAX_BYTES = 5 * 1024 * 1024

class ReportError(ValueError):
    pass

def normal(text):
    return " ".join(text.split())

def parse_json(text):
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
        text = re.sub(r"\s*```$", "", text)
    try:
        result = json.loads(text)
    except (ValueError, TypeError) as exc:
        raise ReportError("The model returned invalid JSON. Try again or use a larger model.") from exc
    if not isinstance(result, dict):
        raise ReportError("The model response must be a JSON object.")
    return result

def read_report(name, data):
    if len(data) > MAX_BYTES:
        raise ReportError("Upload a file smaller than 5 MB.")
    if name.lower().endswith(".pdf"):
        try:
            pdf = PdfReader(io.BytesIO(data))
            if pdf.is_encrypted:
                raise ReportError("Use an unencrypted PDF.")
            if len(pdf.pages) > 10:
                raise ReportError("Use a report of at most 10 pages.")
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        except ReportError:
            raise
        except Exception as exc:
            raise ReportError("This PDF could not be read. Try a text PDF or paste its text.") from exc
        if not text.strip():
            raise ReportError("No selectable text found. Scanned PDFs need OCR first; paste the recognised text.")
    elif name.lower().endswith(".txt"):
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ReportError("Save the text file as UTF-8.") from exc
    else:
        raise ReportError("Only PDF and TXT files are supported.")
    return validate_input(text)

def validate_input(text):
    if not text.strip():
        raise ReportError("Enter report text or upload a report first.")
    if len(text) > MAX_CHARS:
        raise ReportError("Keep the report under 14,000 characters; split a long report into sections.")
    return text.strip()

NUMBER = r"[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"

def decimal(text):
    if not re.fullmatch(NUMBER, text.strip()):
        raise ReportError("Not a plain numeric value.")
    try:
        return Decimal(text.replace(",", "").strip())
    except InvalidOperation as exc:
        raise ReportError("Invalid numeric value.") from exc

def flag(value, reference):
    """Only compare exact numbers with a single printed interval or threshold."""
    try:
        value = decimal(value)
    except ReportError:
        return "Not assessed", "Result is qualitative, censored or not a plain number."
    r = reference.strip().replace("−", "-").replace("–", "-").replace("—", "-")
    r = r.replace("≤", "<=").replace("≥", ">=")
    pair = re.fullmatch(rf"\s*({NUMBER})\s*(?:-|to)\s*({NUMBER})\s*", r, re.I)
    if pair:
        low, high = map(decimal, pair.groups())
        if low > high:
            return "Not assessed", "The printed lower bound exceeds the upper bound."
        return ("Low" if value < low else "High" if value > high else "Within range"), "Compared with the printed inclusive interval."
    threshold = re.fullmatch(rf"(<=|>=|<|>)\s*({NUMBER})", r)
    if threshold:
        op, bound = threshold.groups()
        bound = decimal(bound)
        ok = {"<": value < bound, "<=": value <= bound, ">": value > bound, ">=": value >= bound}[op]
        return ("Within range" if ok else "High" if op.startswith("<") else "Low"), "Compared with the printed threshold, preserving its strictness."
    return "Not assessed", "No single supported numeric reference range was printed."

def validate_rows(payload, report):
    rows = payload.get("tests")
    if not isinstance(rows, list) or len(rows) > 60:
        raise ReportError("Expected a list containing at most 60 tests.")
    checked, seen = [], set()
    def contains(source, field, ignore_case=False):
        # Token boundaries prevent an invented "1" matching the value "118".
        return not field or re.search(r"(?<![\w.<>])" + re.escape(normal(field)) + r"(?![\w.])", source, re.I if ignore_case else 0) is not None
    lines = [normal(line) for line in report.splitlines() if line.strip()]
    structured = any(line.replace(" ", "").lower() == "test|result|unit|referencerange" for line in lines)
    for row in rows:
        keys = ("test", "value", "unit", "reference_range")
        if not isinstance(row, dict) or any(not isinstance(row.get(k), str) for k in keys):
            raise ReportError("A model row is missing a required text field.")
        fields = {k: row[k].strip() for k in keys}
        if not fields["test"] or not fields["value"]:
            raise ReportError("The model omitted a test name or value.")
        match_keys = ("test", "value") if structured else keys
        matches = [line for line in lines if all(contains(line, fields[k], k == "test") for k in match_keys)]
        if len(set(matches)) != 1:
            raise ReportError("An extracted field could not be traced to one report line. Retry or simplify the text layout.")
        source = matches[0]
        fields["test"] = re.search(re.escape(normal(fields["test"])), source, re.I).group()
        # Honour source evidence if supplied by an alternate model/client.
        if "source" in row and (not isinstance(row["source"], str) or normal(row["source"]) != source):
            raise ReportError("An extracted source field could not be traced to the report.")
        notes = []
        if structured:
            cells = [cell.strip() for cell in source.split("|")]
            if len(cells) != 4 or cells[0].casefold() != fields["test"].casefold() or cells[1] != fields["value"]:
                raise ReportError("Extracted test or value does not match its source table columns.")
            for key, printed in zip(keys, cells):
                if fields[key] != printed:
                    notes.append(f"{key} copied from the verified source table cell.")
                fields[key] = printed
        row = {**fields, "source": source}
        identity = tuple(row.values())
        if identity in seen:
            continue
        seen.add(identity)
        status, reason = flag(row["value"], row["reference_range"])
        checked.append({"id": len(checked), **row, "status": status, "comparison_note": reason, "validation_notes": notes})
    # A recognised four-column table permits an explicit completeness check.
    header = "test|result|unit|reference range"
    if any(line.replace(" ", "").lower() == header.replace(" ", "") for line in lines):
        expected_sources = {line for line in lines if len(line.split("|")) == 4 and line.split("|")[0].strip().lower() != "test"}
        if expected_sources - {row["source"] for row in checked}:
            raise ReportError("The model omitted a table row. Retry and include qualitative or missing-range results.")
    if not checked:
        raise ReportError("No laboratory test rows were found. Include test names, values and printed reference ranges.")
    return checked

def analyse(report, client):
    report = validate_input(report)
    extraction_attempts = 1
    try:
        rows = validate_rows(parse_json(client.complete(EXTRACT_PROMPT, report)), report)
    except ReportError:
        extraction_attempts = 2
        repair = EXTRACT_PROMPT + "\nCheck every field carefully: the earlier extraction failed validation. Return all four keys. Copy exact test names, values, units and ranges from the input. For example, a printed range <200 must remain <200, never 200. Empty fields must be empty strings."
        rows = validate_rows(parse_json(client.complete(repair, report)), report)
    warnings = []
    try:
        explanation_input = [{k: r[k] for k in ("id", "test")} for r in rows]
        data = parse_json(client.complete(EXPLAIN_PROMPT, json.dumps(explanation_input, ensure_ascii=False)))
        items = data.get("explanations")
        if not isinstance(items, list) or len(items) != len(rows):
            raise ReportError("The explanation list did not match the extracted tests.")
        descriptions = {}
        for item in items:
            if not isinstance(item, dict) or type(item.get("id")) is not int or not isinstance(item.get("explanation"), str) or not item["explanation"].strip() or item["id"] in descriptions:
                raise ReportError("An explanation was missing or repeated.")
            descriptions[item["id"]] = item["explanation"].strip()
        if set(descriptions) != set(range(len(rows))):
            raise ReportError("The model returned unmatched explanation IDs.")
        comparisons = {
            "Low": "This value is below the report's printed range. Discuss the result with your clinician.",
            "High": "This value is outside the report's printed range on the high side. Discuss the result with your clinician.",
            "Within range": "This value is within the report's printed range; this alone does not establish good health.",
            "Not assessed": "A reliable numerical comparison is unavailable for this row. Ask your clinician to interpret it.",
        }
        for row in rows:
            row["test_meaning"] = descriptions[row["id"]]
            row["explanation"] = descriptions[row["id"]] + " " + comparisons[row["status"]]
    except ReportError as exc:
        warnings.append(f"Numerical checks completed, but explanations are unavailable. {exc}")
        for row in rows:
            row["explanation"] = "Explanation unavailable. " + row["comparison_note"]
    return {"tests": rows, "warnings": warnings, "disclaimer": DISCLAIMER, "model": client.model, "provider": client.provider, "extraction_attempts": extraction_attempts}
