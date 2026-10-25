"""Invoice Cloud Demo: a small Flask web app.

Every time the "Generate Invoice" button is pressed, the app:
  1. creates an invoice with a unique ID,
  2. saves it as a JSON file inside the local `invoice/` folder,
  3. uploads the same file to S3 under the `invoice/` prefix (only if S3_BUCKET is set).

The S3 upload then triggers the Lambda function in `lambda/lambda_function.py`.
"""

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, redirect, render_template, request, url_for

INVOICE_DIR = Path(os.environ.get("INVOICE_DIR", "invoice"))
S3_BUCKET = os.environ.get("S3_BUCKET", "")          # empty = run without AWS
AWS_REGION = os.environ.get("AWS_REGION", "ap-south-1")
APP_VERSION = os.environ.get("APP_VERSION", "v1")

INVOICE_DIR.mkdir(parents=True, exist_ok=True)
app = Flask(__name__)


def new_invoice_id():
    # Example: INV-20261025-143205-7F3A  (date, time, 4 random hex characters)
    now = datetime.now(timezone.utc)
    return f"INV-{now:%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:4].upper()}"


def upload_to_s3(file_path):
    """Copy one invoice file to s3://S3_BUCKET/invoice/<file name>."""
    if not S3_BUCKET:
        return "S3 not configured (local mode): file saved only in the invoice folder"
    import boto3  # imported here so the app also runs on a laptop without AWS

    key = f"invoice/{file_path.name}"
    boto3.client("s3", region_name=AWS_REGION).upload_file(
        str(file_path), S3_BUCKET, key, ExtraArgs={"ContentType": "application/json"}
    )
    return f"Uploaded to s3://{S3_BUCKET}/{key}"


@app.route("/")
def home():
    files = sorted(INVOICE_DIR.glob("*.json"), reverse=True)[:10]
    return render_template(
        "index.html",
        invoices=[f.name for f in files],
        message=request.args.get("message", ""),
        bucket=S3_BUCKET or "not configured",
        version=APP_VERSION,
        host=os.environ.get("HOSTNAME", "local"),
    )


@app.route("/invoice", methods=["POST"])
def create_invoice():
    quantity = int(request.form.get("quantity", 1))
    unit_price = float(request.form.get("unit_price", 0))
    invoice = {
        "invoice_id": new_invoice_id(),
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "customer": request.form.get("customer", "Walk-in Customer").strip(),
        "email": request.form.get("email", "").strip(),
        "item": request.form.get("item", "Item").strip(),
        "quantity": quantity,
        "unit_price": unit_price,
        "amount": round(quantity * unit_price, 2),
    }

    file_path = INVOICE_DIR / f"{invoice['invoice_id']}.json"
    file_path.write_text(json.dumps(invoice, indent=2))

    try:
        status = upload_to_s3(file_path)
    except Exception as err:  # show the error on the page instead of crashing
        status = f"Saved locally, but S3 upload failed: {err}"

    return redirect(url_for("home", message=f"{file_path.name} created. {status}"))


@app.route("/health")
def health():
    return {"status": "ok", "version": APP_VERSION}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
