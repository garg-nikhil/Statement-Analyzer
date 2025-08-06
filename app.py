import os
from flask import Flask, request, jsonify
import tempfile
from utils.pdf_extractor import extract_transactions
from utils.parser import segregate_by_vendor_type
from flask_cors import CORS

app = Flask(__name__)
CORS(app, origins=["https://garg-nikhil.github.io"])

@app.route('/process', methods=['POST'])
def process_pdf():
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    file = request.files['file']
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
        file.save(tmp.name)
        transactions = extract_transactions(tmp.name)
    segregated = segregate_by_vendor_type(transactions)
    return jsonify(segregated)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)