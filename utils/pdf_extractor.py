import pdfplumber
import re
from datetime import datetime


def extract_statement_month(pdf_path):
    """
    Try to extract the statement month from the first two pages of the PDF.
    Returns e.g. 'August 2025'
    """
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages[:2]:  # Usually appears early
            text = page.extract_text()
            if not text:
                continue
            # Check for date range pattern: 01/08/2025 - 31/08/2025
            match = re.search(r'(\d{2}/\d{2}/\d{4})\s*-\s*(\d{2}/\d{2}/\d{4})', text)
            if match:
                dt = datetime.strptime(match.group(1), "%d/%m/%Y")
                return dt.strftime("%B %Y")  # e.g. "August 2025"
            # Check for month-year pattern: August 2025
            match2 = re.search(
                r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})',
                text,
                re.IGNORECASE
            )
            if match2:
                dt = datetime.strptime(f"01 {match2.group(1)} {match2.group(2)}", "%d %B %Y")
                return dt.strftime("%B %Y")
    return None


def parse_date(date_str):
    """
    Parse varied date formats like dd/mm/yyyy or dd MMM yy into ISO format yyyy-mm-dd
    """
    date_str = date_str.strip()
    for fmt in ("%d/%m/%Y", "%d %b %y"):
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime("%Y-%m-%d")
        except Exception:
            continue
    return date_str  # fallback to original string if parsing fails


def parse_amount_with_dc(amount_str):
    """
    Parses amount string for debit/credit suffix ('D' or 'C').
    Returns (debit_amount, credit_amount) as floats or empty strings.
    """
    if not amount_str or not str(amount_str).strip():
        return "", ""

    amt_raw = str(amount_str).replace(',', '').strip()

    # Regex for number and optional trailing D or C
    m = re.match(r"([\d\.]+)\s*([DdCc])?", amt_raw)
    if not m:
        return "", ""
    num = m.group(1)
    dc = m.group(2)

    try:
        val = float(num)
    except ValueError:
        return "", ""

    if dc:
        if dc.upper() == "C":
            return "", val  # Credit
        elif dc.upper() == "D":
            return val, ""  # Debit
    # Default to debit if no suffix
    return val, ""


def extract_transactions(pdf_path):
    """
    Extract transactions from the PDF.
    Returns a list of dicts with keys Date, Vendor, Description,
    Debit Amount, Credit Amount, Balance.
    Works with SBI and formats with 'D'/'C' suffixes.
    """
    transactions = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    if not row or len(row) < 2:
                        continue

                    first_col = str(row[0]).strip()
                    # Detect date in first column via two formats (SBI compatible)
                    if not (re.match(r"\d{2}/\d{2}/\d{4}", first_col) or re.match(r"\d{1,2} [A-Za-z]{3} \d{2}", first_col)):
                        continue

                    txn = {}
                    txn["Date"] = parse_date(first_col)
                    txn["Vendor"] = str(row[1]).strip() if len(row) > 1 else ""
                    txn["Description"] = str(row[2]).strip() if len(row) > 2 else ""

                    debit_amt = ""
                    credit_amt = ""

                    # Amount columns may vary - try from 4th column onward
                    amount_cols = row[3:] if len(row) > 3 else []

                    for amt_col in amount_cols:
                        d, c = parse_amount_with_dc(amt_col)
                        if d != "":
                            debit_amt = d
                        if c != "":
                            credit_amt = c

                    # Fallback: check specific 4th column if still empty
                    if debit_amt == "" and credit_amt == "" and len(row) >= 4:
                        d, c = parse_amount_with_dc(row[3])
                        debit_amt = d
                        credit_amt = c

                    txn["Debit Amount"] = debit_amt
                    txn["Credit Amount"] = credit_amt

                    # Balance or other data if exists
                    txn["Balance"] = str(row[5]).strip() if len(row) > 5 else ""

                    transactions.append(txn)

    return transactions
