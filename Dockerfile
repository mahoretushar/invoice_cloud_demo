# Small official Python base image
FROM python:3.12-slim

WORKDIR /app

# Install libraries first, so Docker can reuse this layer when only the code changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY app.py .
COPY templates/ templates/

# Invoices are written here; Kubernetes mounts a server folder on top of it
RUN mkdir -p /app/invoice
ENV INVOICE_DIR=/app/invoice

EXPOSE 5000

# gunicorn is a production web server for Flask apps
# --access-logfile - prints one log line per request (visible in docker logs / kubectl logs)
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--access-logfile", "-", "app:app"]
