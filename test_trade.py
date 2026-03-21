import os
from dotenv import load_dotenv
from bot.data.roostoo_client import RoostooClient

# Load the API keys from your .env file
load_dotenv()

# Initialize the client with your teammate's security logic
client = RoostooClient(os.getenv("ROOSTOO_API_KEY"), os.getenv("ROOSTOO_API_SECRET"))

print("\n🚀 Firing Test Order to Roostoo API...")

try:
    # Attempt a raw market buy
# Attempt a market buy by omitting the price variable
    response = client.place_order(
        pair="BTC/USD", 
        side="BUY", 
        quantity=0.001
    )
    print("\n=== 🟢 API RESPONSE: SUCCESS ===")
    print(response)
    print("=================================\n")

except TypeError as e:
    print("\n=== 🟡 PARAMETER MISMATCH ===")
    print(f"Error: {e}")
    print("Your teammate might have named the variables differently (e.g., 'qty' instead of 'quantity').")

except Exception as e:
    print("\n=== 🔴 API RESPONSE: FAILED ===")
    print(e)
    print("=================================\n")
