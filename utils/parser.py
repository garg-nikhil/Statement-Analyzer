import pandas as pd

# Adjust these headers based on your PDF format!
HEADERS = ['Date', 'Vendor', 'Description', 'Debit Amount', 'Credit Amount', 'Balance']

def segregate_by_vendor_type(transactions):
    df = pd.DataFrame(transactions, columns=HEADERS)
    debit = pd.to_numeric(df.get('Debit Amount', pd.Series([0]*len(df))).fillna(0), errors='coerce')
    credit = pd.to_numeric(df.get('Credit Amount', pd.Series([0]*len(df))).fillna(0), errors='coerce')
    df['type'] = debit.apply(lambda x: 'debit' if x > 0 else 'credit')
    df['amount'] = debit.where(debit > 0, credit)
    by_vendor = {}
    for _, row in df.iterrows():
        vendor = row['Vendor']
        entry = {
            "date": row['Date'],
            "amount": row['amount'],
            "desc": row['Description']
        }
        by_vendor.setdefault(vendor, {"credit": [], "debit": []})
        by_vendor[vendor][row['type']].append(entry)
    return by_vendor
