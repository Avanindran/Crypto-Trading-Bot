import os
import requests
from dotenv import load_dotenv
from bot.data.roostoo_client import RoostooClient

load_dotenv()

# Initialize client to use your teammate's perfect signature math
client = RoostooClient(os.getenv("ROOSTOO_API_KEY"), os.getenv("ROOSTOO_API_SECRET"))

print("\n=== RAW API CALL LOGS FOR ADMIN ===")
url = "https://mock-api.roostoo.com/v3/balance"
params = {"timestamp": client._ts_ms()}
headers = client._signed_headers(params)

print(f"1. ENDPOINT: GET {url}")
print(f"2. PARAMS SENT: {params}")
print(f"3. SIGNATURE GENERATED: {headers['MSG-SIGNATURE']}")

# Make the raw HTTP request
response = requests.get(url, params=params, headers=headers)

print(f"4. HTTP STATUS CODE: {response.status_code}")
print(f"5. EXACT SERVER RESPONSE: {response.text}")
print("===================================\n")
