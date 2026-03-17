# API connector is in bot/data/roostoo_client.py:
#   RoostooClient — HMAC-SHA256 signing, all 7 endpoints, 3-retry exponential backoff
#   floor_to_precision() — order precision helper (always floors, never rounds up)
#   validate_order_params() — checks precision + minimum order notional
