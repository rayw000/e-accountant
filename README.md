# e-accountant

This repository contains utilities for processing company accounting
data. The `invoice_processor.py` script fetches invoice emails from a
configured mailbox, stores extracted information in a SQLite database
and optionally notifies a WeChat work (企业微信) group via webhook.

## Usage

Set the following environment variables:

- `EMAIL_HOST` – IMAP server host
- `EMAIL_PORT` – IMAP port (defaults to 993)
- `EMAIL_USER` – username
- `EMAIL_PASS` – password
- `WECHAT_WEBHOOK_URL` – webhook URL for 企业微信 (optional)
- `DB_PATH` – path to SQLite database (defaults to `invoices.db`)

Then run:

```bash
python3 invoice_processor.py
```

The script marks processed emails as read. Extracted invoice data is
stored as JSON in the `invoices` table of the database.

Note: PDF parsing requires additional libraries that may need to be
installed separately. The current implementation contains a placeholder
function `extract_invoice_from_pdf`.

## Docker

The application can also be run in a container. Build the image and pass
the required environment variables when running:

```bash
docker build -t e-accountant .

docker run -e EMAIL_HOST=imap.example.com \
           -e EMAIL_USER=user@example.com \
           -e EMAIL_PASS=secret \
           -e WECHAT_WEBHOOK_URL=https://example.com/webhook \
           e-accountant
```

`EMAIL_PORT` and `DB_PATH` can be specified the same way if you need to
override the defaults.
