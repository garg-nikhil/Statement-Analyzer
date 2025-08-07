import os
import tempfile
from flask import Flask, request, jsonify
from flask_cors import CORS
from utils.pdf_extractor import extract_transactions, extract_statement_month
import pandas as pd
import requests

# Your Google Apps Script Web App URL endpoint to update the sheets
GOOGLE_SHEETS_WEBHOOK = "https://script.google.com/macros/s/AKfycbzIA9BeJzkrEMCz1nvj_2nzmRGS7iFRfc0HMvJAeu0NCZqB0f9xFGmtmY2ee-ufZxMP/exec"

app = Flask(__name__)
CORS(app, origins=["https://garg-nikhil.github.io"])

@app.route("/process", methods=["POST"])
def process_pdf():
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file uploaded"}), 400
        
        file = request.files['file']

        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
            file.save(tmp.name)
            # Extract month name to decide which sheet tab to update
            month = extract_statement_month(tmp.name) or "Unknown"
            transactions = extract_transactions(tmp.name)

        if not transactions:
            return jsonify({"error": "No transactions found"}), 200

        # Normalize columns and order
        cols = ["Date", "Vendor", "Description", "Debit Amount", "Credit Amount", "Balance"]
        df = pd.DataFrame(transactions)
        for col in cols:
            if col not in df.columns:
                df[col] = ""
        df = df[cols]

        # Prepare data rows for Google Sheets API
        rows = df.values.tolist()

        payload = {
            "sheetName": month,
            "data": rows
        }

        # Send POST request to Google Apps Script webhook
        resp = requests.post(GOOGLE_SHEETS_WEBHOOK, json=payload)

        return jsonify({
            "month": month,
            "rows_sent": len(rows),
            "google_sheets_response": resp.text
        }), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
