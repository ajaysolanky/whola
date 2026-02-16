# Theme-Compliant AMP Chat MVP

## Setup

```bash
./venv/bin/pip install -r requirements.py
cp .env.example .env
# Edit .env with your real values (OPENROUTER_API_KEY, APP_SECRET, SMTP_*, BASE_URL)
```

## Run server

```bash
./venv/bin/python /Users/ajaysolanky/Documents/coding/whola/server.py
```

The app auto-loads values from `.env` on startup.

## Create campaign

```bash
curl -X POST http://127.0.0.1:8000/api/v1/demo/campaigns \
  -H 'Content-Type: application/json' \
  -d '{
    "brand_id": "acme",
    "name": "Acme Demo",
    "subject": "Find your perfect trail pack",
    "from_email": "demo@yourdomain.com",
    "reply_to": "demo@yourdomain.com",
    "recipients": [{"email": "customer@example.com", "first_name": "Chris"}]
  }'
```

## Send campaign

```bash
curl -X POST http://127.0.0.1:8000/api/v1/demo/campaigns/<campaign_id>/send
```

## Preview themed template

```bash
open http://127.0.0.1:8000/demo/preview-page/acme
```

## Campaign example gallery (realistic campaign context)

```bash
open http://127.0.0.1:8000/demo/examples
```

Use this page to switch brand + campaign preset and preview a more realistic email campaign layout with embedded chat.

## One-command create+send script

```bash
./scripts/demo_create_and_send.py \
  --brand-id acme \
  --name "Acme Demo" \
  --subject "Find your perfect trail pack" \
  --from-email demo@yourdomain.com \
  --reply-to demo@yourdomain.com \
  --recipient customer@example.com:Chris
```

## Tests

```bash
./venv/bin/python -m pytest -q
```
