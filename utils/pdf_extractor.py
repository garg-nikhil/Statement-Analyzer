import pdfplumber

def extract_transactions(pdf_path):
    transactions = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                for row in table[1:]:  # Skip header row
                    transactions.append(row)
    return transactions
