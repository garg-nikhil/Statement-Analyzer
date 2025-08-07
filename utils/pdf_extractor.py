import pdfplumber
import re
from datetime import datetime


def extract_statement_month(pdf_path):
    """
    Extract statement month from first two pages using flexible regex.
    Handles formats like:
    - '01/07/2025 To 31/07/2025'
    - 'As on: 31/07/2025'
    - literal 'August 2025'
    Returns a string like 'July 2025' or None if not found.
    """
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages[:2]:
            text = page.extract_text() or ""

            # Pattern 1: date range with - or "to"
            m = re.search(r'(\d{2}/\d{2}/\d{4})\s*(?:-|to|To|TO)\s*(\d{2}/\d{2}/\d{4})', text, re.IGNORECASE)
            if m:
                dt = datetime.strptime(m.group(1), "%d/%m/%Y")
                return dt.strftime("%B %Y")

            # Pattern 2: "As on: 31/07/2025"
            m2 = re.search(r'As on:? (\d{2}/\d{2}/\d{4})', text, re.IGNORECASE)
            if m2:
                dt = datetime.strptime(m2.group(1), "%d/%m/%Y")
                return dt.strftime("%B %Y")

            # Pattern 3: literal month-year e.g. August 2025
            m3 = re.search(
                r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})',
                text, re.IGNORECASE)
            if m3:
                dt = datetime.strptime(f"01 {m3.group(1)} {m3.group(2)}", "%d %B %Y")
                return dt.strftime("%B %Y")

    return None


def parse_date(date_str):
    """
    Parse a date string in formats dd/mm/yyyy or dd MMM yy.
    Return ISO 8601 date string or original string if parsing fails.
    """
    date_str = date_str.strip()
    for fmt in ("%d/%m/%Y", "%d %b %y"):
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime("%Y-%m-%d")
        except Exception:
            continue
    return date_str


def parse_amount_with_dc(amount_str):
    """
    Parse an amount string with optional 'D' (debit) or 'C' (credit) suffix.
    Returns a tuple (debit_amount, credit_amount) as floats or empty strings.
    """
    if not amount_str or not str(amount_str).strip():
        return "", ""

    amt_raw = str(amount_str).replace(',', '').strip()

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
            return "", val
        elif dc.upper() == "D":
            return val, ""
    return val, ""  # default to debit if no suffix


def split_by_transaction_dates(text):
    """
    Splits a large transaction text blob into individual transaction strings,
    splitting at each new transaction date match.
    """
    pattern = r'\d{2}/\d{2}/\d{4}|\d{1,2} [A-Za-z]{3} \d{2}'
    matches = list(re.finditer(pattern, text))

    rows = []
    for i in range(len(matches)):
        start = matches[i].start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        row_text = text[start:end].strip()
        rows.append(row_text)
    return rows


def extract_transactions(pdf_path):
    """
    Extract transactions robustly from PDF.
    Handles both normally extracted multi-row tables and single-row large text blob tables.
    Returns list of dicts with keys:
    Date, Vendor, Description, Debit Amount, Credit Amount, Balance.
    """
    transactions = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()

            for table in tables:
                # Case: single large cell containing all transactions
                if len(table) == 1 and len(table[0]) == 1 and len(table[0][0]) > 100:
                    text_blob = table[0][0]
                    rows_text = split_by_transaction_dates(text_blob)

                    for row_text in rows_text:
                        # Split columns by 2+ spaces or tabs
                        cols = re.split(r'\s{2,}|\t', row_text)

                        if len(cols) < 3:
                            continue  # probable non-transaction

                        date_str = cols[0].strip()
                        if not (re.match(r"\d{2}/\d{2}/\d{4}", date_str) or re.match(r"\d{1,2} [A-Za-z]{3} \d{2}", date_str)):
                            continue

                        txn = {
                            "Date": parse_date(date_str),
                            "Vendor": cols[1].strip() if len(cols) > 1 else "",
                            "Description": cols[2].strip() if len(cols) > 2 else ""
                        }

                        debit_amt = ""
                        credit_amt = ""

                        for amt_col in cols[3:]:
                            d, c = parse_amount_with_dc(amt_col)
                            if d != "":
                                debit_amt = d
                            if c != "":
                                credit_amt = c

                        txn["Debit Amount"] = debit_amt
                        txn["Credit Amount"] = credit_amt
                        txn["Balance"] = ""  # add parsing if balance info is embedded

                        transactions.append(txn)

                else:
                    # Normal multi-row table case
                    for row in table:
                        if not row or len(row) < 2:
                            continue

                        first_col = str(row[0]).strip()
                        if not (re.match(r"\d{2}/\d{2}/\d{4}", first_col) or re.match(r"\d{1,2} [A-Za-z]{3} \d{2}", first_col)):
                            continue

                        txn = {
                            "Date": parse_date(first_col),
                            "Vendor": str(row[1]).strip() if len(row) > 1 else "",
                            "Description": str(row[2]).strip() if len(row) > 2 else ""
                        }

                        debit_amt = ""
                        credit_amt = ""

                        amount_cols = row[3:] if len(row) > 3 else []

                        for amt_col in amount_cols:
                            d, c = parse_amount_with_dc(amt_col)
                            if d != "":
                                debit_amt = d
                            if c != "":
                                credit_amt = c

                        if debit_amt == "" and credit_amt == "" and len(row) >= 4:
                            d, c = parse_amount_with_dc(row[3])
                            debit_amt = d
                            credit_amt = c

                        txn["Debit Amount"] = debit_amt
                        txn["Credit Amount"] = credit_amt
                        txn["Balance"] = str(row[5]).strip() if len(row) > 5 else ""

                        transactions.append(txn)

    return transactions
