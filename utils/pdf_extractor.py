import pdfplumber
import re
from datetime import datetime
import pprint

def extract_statement_month(pdf_path):
    import re
    from datetime import datetime
    import pdfplumber

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages[:2]:
            text = page.extract_text() or ""

            m = re.search(r'(\d{2}/\d{2}/\d{4})\s*(?:-|to|To|TO)\s*(\d{2}/\d{2}/\d{4})', text, re.IGNORECASE)
            if m:
                dt = datetime.strptime(m.group(1), "%d/%m/%Y")
                return dt.strftime("%B %Y")

            m2 = re.search(r'As on:? (\d{2}/\d{2}/\d{4})', text, re.IGNORECASE)
            if m2:
                dt = datetime.strptime(m2.group(1), "%d/%m/%Y")
                return dt.strftime("%B %Y")

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
    Parse an amount string that may have a trailing 'D' or 'C' for debit or credit.
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
    except Exception:
        return "", ""

    if dc:
        if dc.upper() == "C":
            return "", val
        elif dc.upper() == "D":
            return val, ""
    return val, ""  # default to debit if no suffix


def split_text_blob_to_rows(text):
    """
    First split text by newlines, then further split any lines containing multiple transactions
    by each transaction date pattern (dd/mm/yyyy or dd MMM yy).
    Returns a list of individual transaction text lines.
    """
    rows = []
    lines = text.split('\n')

    date_pattern = r'(?=\d{2}/\d{2}/\d{4})|(?=\d{1,2} [A-Za-z]{3} \d{2})'

    for line in lines:
        # Use regex positive lookahead to split concatenated transactions within one line
        splits = re.split(date_pattern, line)
        for s in splits:
            clean_s = s.strip()
            if clean_s and len(clean_s) > 5:  # minimum length guard
                rows.append(clean_s)

    return rows


def extract_transactions(pdf_path, debug=False):
    """
    Extract transactions from PDF, handling both normal tables and single-cell large text blobs.

    Returns a list of dictionaries with keys:
    Date, Vendor, Description, Debit Amount, Credit Amount, Balance
    """
    transactions = []

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            tables = page.extract_tables()
            
            for table_num, table in enumerate(tables, start=1):
                if debug:
                    print(f"\nDEBUG: Page {page_num}, Table {table_num} extracted with {len(table)} rows:")
                    pprint.pprint(table)

                # Check if single large cell row containing all transactions as blob
                if len(table) == 1 and len(table[0]) == 1 and len(table[0][0]) > 100:
                    text_blob = table[0][0]
                    if debug:
                        print(f"DEBUG: Single large text blob detected on Page {page_num}, Table {table_num}")

                    rows_text = split_text_blob_to_rows(text_blob)

                    if debug:
                        print(f"DEBUG: Split into {len(rows_text)} transaction rows.")

                    for row_text in rows_text:
                        # Split columns roughly on 2+ spaces or tab characters
                        cols = re.split(r'\s{2,}|\t', row_text)

                        if len(cols) < 3:
                            if debug:
                                print(f"DEBUG: Ignoring short row (fewer than 3 cols): {cols}")
                            continue  # Not enough columns to be transaction

                        date_str = cols[0].strip()

                        if not (re.match(r"\d{2}/\d{2}/\d{4}", date_str)
                                or re.match(r"\d{1,2} [A-Za-z]{3} \d{2}", date_str)):
                            if debug:
                                print(f"DEBUG: Ignoring row with invalid date: {date_str}")
                            continue

                        txn = {
                            "Date": parse_date(date_str),
                            "Vendor": cols[1].strip() if len(cols) > 1 else "",
                            "Description": cols[2].strip() if len(cols) > 2 else ""
                        }

                        debit_amt = ""
                        credit_amt = ""
                        # Attempt to parse debit/credit in any subsequent columns
                        for amt_col in cols[3:]:
                            d, c = parse_amount_with_dc(amt_col)
                            if d != "":
                                debit_amt = d
                            if c != "":
                                credit_amt = c

                        txn["Debit Amount"] = debit_amt
                        txn["Credit Amount"] = credit_amt
                        txn["Balance"] = ""  # Could add balance if available elsewhere

                        transactions.append(txn)

                else:
                    # Normal multi-row tables
                    for row in table:
                        if not row or len(row) < 2:
                            continue
                        
                        first_col = str(row[0]).strip()
                        # Date validation - accept dd/mm/yyyy or dd MMM yy formats
                        if not (re.match(r"\d{2}/\d{2}/\d{4}", first_col)
                                or re.match(r"\d{1,2} [A-Za-z]{3} \d{2}", first_col)):
                            if debug:
                                print(f"DEBUG: Skipping row with invalid date format in first col: {first_col}")
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

                        # Fallback: if both debit and credit empty and 4th col exists
                        if debit_amt == "" and credit_amt == "" and len(row) >= 4:
                            d, c = parse_amount_with_dc(row[3])
                            debit_amt = d
                            credit_amt = c

                        txn["Debit Amount"] = debit_amt
                        txn["Credit Amount"] = credit_amt

                        txn["Balance"] = str(row[5]).strip() if len(row) > 5 else ""

                        transactions.append(txn)

    if debug:
        print(f"\nDEBUG: Total transactions extracted: {len(transactions)}")

    return transactions
