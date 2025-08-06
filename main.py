from flask import Flask, request, jsonify
import pdfplumber
import pandas as pd
import tempfile

app = Flask(__name__)

@app.route('/process', methods=['POST'])
def process_pdf():
    file = request.files['file']
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
        file.save(tmp.name)
        with pdfplumber.open(tmp.name) as pdf:
            # Extract tables as before
            transactions = []
            for page in pdf.pages:
                for table in page.extract_tables():
                    for row in table[1:]:  # skip header
                        transactions.append(row)
        # Additional processing (add your parser/segregator here)
    # Return processed JSON (structure by vendor/credit/debit)
    return jsonify({"success": True, "data": transactions})

if __name__ == '__main__':
    app.run()
