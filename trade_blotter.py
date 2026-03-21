import os
import sys
import json
from dotenv import load_dotenv
from bot.data.roostoo_client import RoostooClient

def universal_data_hunter(data):
    """Recursively hunts through ANY data structure to find a list of trades"""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        # Check if the dictionary itself is just a giant wrapper of orders
        for k, v in data.items():
            if isinstance(v, list) and len(v) > 0 and isinstance(v[0], dict):
                return v
        # Dig deeper into the dictionary
        for k, v in data.items():
            result = universal_data_hunter(v)
            if result: return result
    if isinstance(data, tuple):
        for item in data:
            result = universal_data_hunter(item)
            if result: return result
    return []

def analyze_pair(target_pair):
    load_dotenv()
    client = RoostooClient(os.getenv("ROOSTOO_API_KEY"), os.getenv("ROOSTOO_API_SECRET"))
    
    target_pair = target_pair.strip().upper()
    if "/" not in target_pair:
        target_pair = f"{target_pair}/USD"
    
    try:
        print(f"Fetching history and live market data for {target_pair}...")
        raw_orders = client.query_order(pending_only=False)
        tickers = client.get_ticker() 
        
        # --- THE DEEP HUNTER ---
        orders = universal_data_hunter(raw_orders)
        
        if not orders:
            print(f"DEBUG: I searched the entire API response and couldn't find a list. Raw data:")
            print(str(raw_orders)[:500] + "... (truncated)")
            return
        # -----------------------

        total_bought_qty = 0.0
        total_spent = 0.0
        total_sold_qty = 0.0
        total_earned = 0.0
        match_count = 0
        
        print("\n" + "="*55)
        print(f"   TRADE EXECUTION LOG: {target_pair}")
        print("="*55)

        for order in orders:
            pair = str(order.get('Pair', order.get('TradePairId', order.get('pair', '')))).upper()
            
            if pair == target_pair:
                match_count += 1
                side = str(order.get('Side', order.get('side', ''))).upper()
                qty = float(order.get('Quantity', order.get('quantity', 0)))
                price = float(order.get('Price', order.get('price', 0)))
                
                if side == "BUY":
                    total_bought_qty += qty
                    total_spent += (qty * price)
                    print(f"\033[92m[BUY]\033[0m  {qty:<12.4f} @ ${price:.4f} (Cost: ${qty*price:.2f})")
                elif side == "SELL":
                    total_sold_qty += qty
                    total_earned += (qty * price)
                    print(f"\033[91m[SELL]\033[0m {qty:<12.4f} @ ${price:.4f} (Earned: ${qty*price:.2f})")

        if match_count == 0:
            print(f"No executions found for {target_pair}.")
            print("="*55 + "\n")
            return

        # --- The PnL Math ---
        current_bag = total_bought_qty - total_sold_qty
        avg_buy_price = (total_spent / total_bought_qty) if total_bought_qty > 0 else 0
        avg_sell_price = (total_earned / total_sold_qty) if total_sold_qty > 0 else 0
        
        pair_ticker = tickers.get(target_pair, {}) if isinstance(tickers, dict) else {}
        live_price = float(pair_ticker.get('LastPrice', 0))
        current_value = current_bag * live_price if current_bag > 0 else 0.0
        
        total_pnl = total_earned + current_value - total_spent
        
        print("-" * 55)
        print(f"📊 PERFORMANCE METRICS: {target_pair}")
        print("-" * 55)
        print(f"Total Executions : {match_count}")
        print(f"Avg Buy Price    : ${avg_buy_price:.4f}")
        print(f"Avg Sell Price   : ${avg_sell_price:.4f}")
        
        clean_bag = max(0, round(current_bag, 6))
        print(f"Net Position     : {clean_bag} {target_pair.split('/')[0]}")
        
        if clean_bag > 0.0001 and live_price > 0:
            print(f"Live Asset Price : ${live_price:.4f}")
            print(f"Open Bag Value   : ${current_value:.2f}")

        if total_pnl >= 0:
            print(f"Total PnL        : \033[92m+${total_pnl:.2f}\033[0m")
        else:
            print(f"Total PnL        : \033[91m-${abs(total_pnl):.2f}\033[0m")
        
        print("="*55 + "\n")

    except Exception as e:
        print(f"Failed to analyze pair: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        target = sys.argv[1]
    else:
        target = input("Enter trading pair to analyze (e.g., BTC): ")
        
    analyze_pair(target)
