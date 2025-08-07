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
            # Format: 01/08/2025 - 31/08/2025
            match = re.search(r'(\d{2}/\d{2}/\d{4})\s*-\s*(\d{2}/\d{2}/\d{4})', text)
            if match:
                dt = datetime.strptime(match.group(1), "%d/%m/%Y")
                return dt.strftime("%B %Y")  # e.g. "August 2025"
            # Format: August 2025
            match2 = re.search(
                r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})',
                text,
                re.IGNORECASE
            )
            if match2:
                dt = datetime.strptime(f"01 {match2.group(1)} {match2.group(2)}", "%d %B %Y")
                return dt.strftime("%B %Y")
    return None


def parse_amount_string(amount_str):
    """
    Parses an amount string that might end with 'Cr' or 'C' indicating credit.
    Returns (debit_amount, credit_amount) as floats or empty strings.
    """
    if not amount_str or not str(amount_str).strip():
        return "", ""

    amt = str(amount_str).strip().replace(',', '')
    credit_suffix_match = re.search(r'(Cr|C)$', amt, re.IGNORECASE)

    if credit_suffix_match:
        # Amount ends with Cr or C: credit amount
        num_str = amt[:-len(credit_suffix_match.group(0))].strip()
        try:
            credit = float(num_str)
        except ValueError:
            credit = 0.0
        return "", credit
    else:
        # Otherwise treat as debit amount
        try:
            debit = float(amt)
        except ValueError:
            debit = 0.0
        return debit, ""


def extract_transactions(pdf_path):
    """
    Attempts to extract transaction tables. 
    Adapts to the number of columns; returns a list of transaction dicts.
    """
    transactions = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    # Heuristic: skip header rows by checking if a date is present
                    # Change this regex/data logic as needed for your formats!
                    if not row or not re.match(r"\d{2}/\d{2}/\d{4}", str(row[0])):
                        continue
                    
                    txn = {}
                    txn["Date"] = row[0]
                    txn["Vendor"] = row[1] if len(row) > 1 else ""
                    txn["Description"] = row[2] if len(row) > 2 else ""

                    debit_amt, credit_amt = "", ""

                    # Logic for amount columns depending on row length
                    if len(row) >= 5:
                        # If both debit and credit amounts are separate columns,
                        # use parse_amount_string to correctly fill them
                        debit_amt, credit_amt = parse_amount_string(row[3])
                        # If credit column is also present and non-empty, override credit_amt
                        if row[4] is not None and str(row[4]).strip() != "":
                            _, credit_val = parse_amount_string(row[4])
                            if credit_val != "":
                                credit_amt = credit_val
                    elif len(row) >= 4:
                        # Single amount column, might have "Cr" or "C"
                        debit_amt, credit_amt = parse_amount_string(row[3])
                    else:
                        debit_amt, credit_amt = "", ""

                    txn["Debit Amount"] = debit_amt
                    txn["Credit Amount"] = credit_amt
                    txn["Balance"] = row[5] if len(row) > 5 else ""

                    transactions.append(txn)
    return transactions
