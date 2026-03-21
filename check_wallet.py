import os
from dotenv import load_dotenv
from bot.data.roostoo_client import RoostooClient

load_dotenv()
client = RoostooClient(os.getenv("ROOSTOO_API_KEY"), os.getenv("ROOSTOO_API_SECRET"))
print("\n--- RAW WALLET DATA ---")
print(client.get_balance())
print("-----------------------\n")
