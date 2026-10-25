"""InvoiceProcessor Lambda function.

Trigger: S3 "object created" events for keys under invoice/ ending in .json.
For each new invoice it:
  1. reads the invoice JSON from S3,
  2. adds 18% GST and computes the grand total,
  3. writes a summary file to processed/<invoice id>_summary.json,
  4. sends an email notification through SNS (if SNS_TOPIC_ARN is set).

Writing to processed/ (not invoice/) matters: if the output went back into
invoice/, every summary would trigger the function again in an endless loop.
"""

import json
import os
from urllib.parse import unquote_plus

import boto3

s3 = boto3.client("s3")
sns = boto3.client("sns")
GST_RATE = 0.18
SNS_TOPIC_ARN = os.environ.get("SNS_TOPIC_ARN", "")


def lambda_handler(event, context):
    results = []
    for record in event["Records"]:  # one event can carry several files
        bucket = record["s3"]["bucket"]["name"]
        key = unquote_plus(record["s3"]["object"]["key"])
        print(f"New invoice detected: s3://{bucket}/{key}")

        invoice = json.loads(s3.get_object(Bucket=bucket, Key=key)["Body"].read())

        gst = round(invoice["amount"] * GST_RATE, 2)
        summary = {
            "invoice_id": invoice["invoice_id"],
            "customer": invoice["customer"],
            "item": invoice["item"],
            "amount": invoice["amount"],
            "gst_18_percent": gst,
            "grand_total": round(invoice["amount"] + gst, 2),
            "source_file": key,
            "processed_by": context.function_name if context else "local-test",
        }

        out_key = f"processed/{invoice['invoice_id']}_summary.json"
        s3.put_object(Bucket=bucket, Key=out_key, Body=json.dumps(summary, indent=2),
                      ContentType="application/json")
        print(f"Summary written: s3://{bucket}/{out_key}")

        if SNS_TOPIC_ARN:
            sns.publish(
                TopicArn=SNS_TOPIC_ARN,
                Subject=f"New invoice {invoice['invoice_id']}",
                Message=(
                    f"Invoice {invoice['invoice_id']} for {invoice['customer']}\n"
                    f"Item: {invoice['item']} x {invoice['quantity']}\n"
                    f"Amount: Rs {invoice['amount']:.2f}\n"
                    f"GST (18%): Rs {gst:.2f}\n"
                    f"Grand total: Rs {summary['grand_total']:.2f}\n"
                ),
            )
            print("Email notification sent through SNS")

        results.append(summary)

    return {"statusCode": 200, "body": json.dumps(results)}
