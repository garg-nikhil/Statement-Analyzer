import os
import tempfile
from flask import Flask, request, jsonify
from flask_cors import CORS
from utils.pdf_extractor import extract_transactions, extract_statement_month
import pandas as pd
import requests

# Edit this with your Google Apps Script webhook URL!
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
            month = extract_statement_month(tmp.name) or "Unknown"
            txns = extract_transactions(tmp.name)

        if not txns:
            return jsonify({"error": "No transactions found"}), 200

        # Convert to DataFrame and fill missing fields
        cols = ["Date", "Vendor", "Description", "Debit Amount", "Credit Amount", "Balance"]
        df = pd.DataFrame(txns)
        for col in cols:
            if col not in df.columns:
                df[col] = ""
        df = df[cols]

        # Prepare rows as lists for Google Sheets
        rows = df.values.tolist()
        payload = {
            "sheetName": month,
            "data": rows
        }

        # Send (append) to Google Sheets via Apps Script webhook
        resp = requests.post(GOOGLE_SHEETS_WEBHOOK, json=payload)

        # Show feedback to frontend
        return jsonify({
            "month": month,
            "rows_sent": len(rows),
            "google_sheets_response": resp.text
        }), 200
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
