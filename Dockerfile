# Use official Python image.
FROM python:3.11-slim

# Set work directory.
WORKDIR /app

# Install dependencies.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code.
COPY . .

# Environment variables may be provided at runtime.
# Default command runs the invoice processor.
ENTRYPOINT ["python", "invoice_processor.py"]
