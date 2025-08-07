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
                    # For demo: assume row[0]=Date, row[1]=Vendor, row[2]=Desc, row[3]=Debit, row[4]=Credit
                    # But make it flexible
                    txn = {}
                    txn["Date"] = row[0]
                    txn["Vendor"] = row[1] if len(row) > 1 else ""
                    txn["Description"] = row[2] if len(row) > 2 else ""
                    # Try to extract Debit/Credit
                    debit, credit = "", ""
                    if len(row) >= 5:
                        debit = row[3] if row[3] else ""
                        credit = row[4] if row[4] else ""
                    elif len(row) >= 4:
                        amt = row[3]
                        # Heuristic: positive = credit, negative = debit
                        try:
                            amt_f = float(str(amt).replace(',', ''))
                            if amt_f < 0:
                                debit = abs(amt_f)
                            else:
                                credit = amt_f
                        except:
                            pass
                    txn["Debit Amount"] = debit
                    txn["Credit Amount"] = credit
                    txn["Balance"] = row[5] if len(row) > 5 else ""
                    transactions.append(txn)
    return transactions
