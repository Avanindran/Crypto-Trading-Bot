
import os
from dotenv import load_dotenv
from bot.data.roostoo_client import RoostooClient

def get_live_nav():
    load_dotenv()
    client = RoostooClient(os.getenv("ROOSTOO_API_KEY"), os.getenv("ROOSTOO_API_SECRET"))
    
    # Roostoo standard hackathon starting balance
    STARTING_BALANCE = 50000.0 
    
    try:
        print("Fetching balances and live market prices...")
        balances = client.get_balance()
        tickers = client.get_ticker() # Assuming your client has a standard get_ticker() method
        
        total_nav = 0.0
        
        print("\n" + "="*40)
        print(" " * 10 + "LIVE PORTFOLIO NAV")
        print("="*40)
        
        for coin, data in balances.items():
            total_coin = float(data.get("Free", 0)) + float(data.get("Locked", 0))
            
            if total_coin > 0:
                if coin == "USD":
                    usd_value = total_coin
                    print(f" USD Cash   : ${usd_value:,.2f}")
                    total_nav += usd_value
                else:
                    # Match the coin to the USD pair price (e.g., "BTC" -> "BTC/USD")
                    pair = f"{coin}/USD" 
                    if pair in tickers:
                        # Grab the LastPrice from the ticker dict
                        current_price = float(tickers[pair].get("LastPrice", 0))
                        coin_usd_value = total_coin * current_price
                        
                        print(f"{coin:<8} : {total_coin:<10.6f} (Val: ${coin_usd_value:,.2f})")
                        total_nav += coin_usd_value
                    else:
                        print(f"{coin}: Could not find live price for {pair}")

        # Calculate Final PnL
        pnl_dollars = total_nav - STARTING_BALANCE
        pnl_percent = (pnl_dollars / STARTING_BALANCE) * 100
        
        print("-" * 40)
        print(f" Total Equity (NAV) : ${total_nav:,.2f}")
        
        # Color formatting for terminal (Green for profit, Red for loss)
        if pnl_dollars >= 0:
            print(f" Total PnL          : \033[92m+${pnl_dollars:,.2f} (+{pnl_percent:.2f}%)\033[0m")
        else:
            print(f" Total PnL          : \033[91m-${abs(pnl_dollars):,.2f} ({pnl_percent:.2f}%)\033[0m")
        print("="*40 + "\n")

    except Exception as e:
        print(f"Failed to calculate NAV: {e}")

if __name__ == "__main__":
    get_live_nav()
