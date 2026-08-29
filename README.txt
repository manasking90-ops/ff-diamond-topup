FF Diamond Top-Up Center — Flask storefront

Run locally:
  pip install -r requirements.txt
  python app.py

Production configuration should be supplied with environment variables:
  SECRET_KEY
  UPI_ID
  ADMIN_USER
  ADMIN_PASS
  SHOP_NAME

The payment page intentionally contains a placeholder QR until a real merchant QR is configured. Payment proof is manually reviewed in /admin.
