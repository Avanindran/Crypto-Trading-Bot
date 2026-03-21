import os
from dotenv import load_dotenv
from bot.data.roostoo_client import RoostooClient

def get_trade_history():
    load_dotenv()
    client = RoostooClient(os.getenv("ROOSTOO_API_KEY"), os.getenv("ROOSTOO_API_SECRET"))
    
    try:
        print("Connecting to exchange to fetch official trade history...")
        # Fetch all historical orders
        orders = client.query_order(pending_only=False)
        
        print("\n" + "="*40)
        print(" "*12 + "OFFICIAL TRADE LOG")
        print("="*40)
        
        if not orders:
            print("No trades found on the exchange yet.")
        elif isinstance(orders, list):
            # Print the 20 most recent trades
            for order in orders[-20:]:
                # Safely extract variables (handles different API dictionary keys)
                pair = order.get('TradePairId', order.get('pair', 'UNKNOWN'))
                side = str(order.get('Side', order.get('side', 'UNKNOWN'))).upper()
                qty = order.get('Quantity', order.get('quantity', 0))
                price = order.get('Price', order.get('price', 'MARKET'))
                
                # Color coding (Green for BUY, Red for SELL)
                if side == "BUY":
                    print(f"\033[92m[{side}]\033[0m {qty:<10} {pair:<10} @ {price}")
                else:
                    print(f"\033[91m[{side}]\033[0m {qty:<10} {pair:<10} @ {price}")
        else:
            # Fallback just in case Roostoo returns a weird dictionary format
            print(f"Raw Order Data: {orders}")
            
        print("="*40 + "\n")
        
    except Exception as e:
        print(f"Failed to fetch trade history: {e}")

if __name__ == "__main__":
    get_trade_history()
