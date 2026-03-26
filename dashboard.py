import os
import sys
import time
from datetime import datetime
from dotenv import load_dotenv
from bot.data.roostoo_client import RoostooClient

def universal_data_hunter(data):
    """Recursively hunts through ANY data structure to find a list of trades"""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for k, v in data.items():
            if isinstance(v, list) and len(v) > 0 and isinstance(v[0], dict):
                return v
        for k, v in data.items():
            result = universal_data_hunter(v)
            if result: return result
    if isinstance(data, tuple):
        for item in data:
            result = universal_data_hunter(item)
            if result: return result
    return []

def run_dashboard():
    load_dotenv()
    client = RoostooClient(os.getenv("ROOSTOO_API_KEY"), os.getenv("ROOSTOO_API_SECRET"))
    STARTING_BALANCE = 1000000.0 
    
    while True:
        try:
            # 1. Clean Terminal Clear
            os.system('clear' if os.name == 'posix' else 'cls')
            
            print("\033[96m" + "="*95)
            print(f"  MCDONALDS TRACKER                                  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print("="*95 + "\033[0m")
            print("Fetching live exchange data...", end="\r") 
            
            # 2. Fetch Data
            balances = client.get_balance()
            tickers = client.get_ticker()
            raw_orders = client.query_order(pending_only=False)
            orders = universal_data_hunter(raw_orders)
            
            print("                              ", end="\r")
            
            # ---------------------------------------------------------
            # DATA PROCESSING: PER-ASSET METRICS
            # ---------------------------------------------------------
            asset_metrics = {}
            if orders:
                for order in orders:
                    pair = str(order.get('Pair', order.get('TradePairId', order.get('pair', 'UNKNOWN')))).upper()
                    if "/" not in pair: 
                        continue
                    coin = pair.split('/')[0]
                    side = str(order.get('Side', order.get('side', 'UNKNOWN'))).upper()
                    qty = float(order.get('Quantity', order.get('quantity', 0)))
                    price = float(order.get('Price', order.get('price', 0)))
                    
                    if coin not in asset_metrics:
                        asset_metrics[coin] = {'spent': 0.0, 'earned': 0.0}
                        
                    if side == "BUY":
                        asset_metrics[coin]['spent'] += (qty * price)
                    elif side == "SELL":
                        asset_metrics[coin]['earned'] += (qty * price)
            
            # ---------------------------------------------------------
            # SECTION 1: LIVE PORTFOLIO NAV
            # ---------------------------------------------------------
            total_nav = 0.0
            usd_total = 0.0
            
            # Find all unique coins we own OR have traded
            all_coins = set(list(balances.keys()) + list(asset_metrics.keys()))
            if "USD" in all_coins:
                all_coins.remove("USD")
                
            usd_data = balances.get("USD", {})
            usd_total = float(usd_data.get("Free", 0)) + float(usd_data.get("Locked", 0))
            total_nav += usd_total
            
            asset_rows = []
            
            for coin in all_coins:
                # Get Live Balance
                balance_data = balances.get(coin, {})
                total_coin = float(balance_data.get("Free", 0)) + float(balance_data.get("Locked", 0))
                
                # Get Live Price
                pair = f"{coin}/USD"
                pair_ticker = tickers.get(pair, {}) if isinstance(tickers, dict) else {}
                live_price = float(pair_ticker.get("LastPrice", 0))
                
                # Calculate Current Value
                coin_usd_value = total_coin * live_price
                total_nav += coin_usd_value
                
                # Calculate Individual PnL (Realized + Unrealized)
                spent = asset_metrics.get(coin, {}).get('spent', 0.0)
                earned = asset_metrics.get(coin, {}).get('earned', 0.0)
                coin_pnl = earned + coin_usd_value - spent
                
                # Add to display list if we hold the bag OR if we made/lost money on it
                if total_coin > 0.000001 or abs(coin_pnl) > 0.01:
                    asset_rows.append({
                        'coin': coin,
                        'qty': total_coin,
                        'price': live_price,
                        'value': coin_usd_value,
                        'pnl': coin_pnl
                    })
            
            pnl_dollars = total_nav - STARTING_BALANCE
            pnl_percent = (pnl_dollars / STARTING_BALANCE) * 100
            
            print("\n\033[93m[ LIVE PORTFOLIO NAV ]\033[0m")
            print(f"USD Cash     : ${usd_total:,.2f}")
            print(f"Asset Value  : ${total_nav - usd_total:,.2f}")
            print("-" * 40)
            print(f"Total Equity : ${total_nav:,.2f}")
            
            if pnl_dollars >= 0:
                print(f"Total PnL    : \033[92m+${pnl_dollars:,.2f} (+{pnl_percent:.2f}%)\033[0m")
            else:
                print(f"Total PnL    : \033[91m-${abs(pnl_dollars):,.2f} ({pnl_percent:.2f}%)\033[0m")
            
            # ---------------------------------------------------------
            # SECTION 2: PER-ASSET PNL TRACKER
            # ---------------------------------------------------------
            if asset_rows:
                print("\n\033[93m[ ASSET PERFORMANCE & PNL ]\033[0m")
                print(f"{'ASSET':<8} | {'NET POSITION':<15} | {'LIVE PRICE':<10} | {'CURRENT VALUE':<14} | {'TOTAL PNL'}")
                print("-" * 85)
                # Sort by Current Value, then by PnL
                asset_rows.sort(key=lambda x: (x['value'], x['pnl']), reverse=True)
                
                for row in asset_rows:
                    pnl_color = "\033[92m+" if row['pnl'] >= 0 else "\033[91m-"
                    pnl_str = f"{pnl_color}${abs(row['pnl']):,.2f}\033[0m"
                    print(f"{row['coin']:<8} | {row['qty']:<15.6f} | ${row['price']:<9.4f} | ${row['value']:<13,.2f} | {pnl_str}")
            
            # ---------------------------------------------------------
            # SECTION 3: RECENT EXECUTIONS
            # ---------------------------------------------------------
            if orders:
                print("\n\033[93m[ RECENT ACTIVITY (LAST 10 TRADES) ]\033[0m")
                try:
                    orders.sort(key=lambda x: int(x.get('CreateTimestamp', 0)))
                except:
                    pass
                    
                for order in orders[-10:]:
                    pair = str(order.get('Pair', order.get('TradePairId', order.get('pair', 'UNKNOWN')))).upper()
                    side = str(order.get('Side', order.get('side', 'UNKNOWN'))).upper()
                    qty = float(order.get('Quantity', order.get('quantity', 0)))
                    price = float(order.get('Price', order.get('price', 0)))
                    cost = qty * price
                    
                    # Extract timestamp and format to HH:MM:SS
                    raw_ts = float(order.get('CreateTimestamp', 0))
                    # Convert milliseconds to seconds if necessary
                    if raw_ts > 1e11:
                        raw_ts /= 1000
                    time_str = datetime.fromtimestamp(raw_ts).strftime('%Y-%m-%d %H:%M:%S') if raw_ts > 0 else "----/--/-- --:--:--"
                    
                    if side == "BUY":
                        print(f"\033[92m[BUY]\033[0m  {time_str} | {pair:<10} {qty:<12.4f} @ ${price:.4f} \033[90m(Cost: ${cost:,.2f})\033[0m")
                    else:
                        print(f"\033[91m[SELL]\033[0m {time_str} | {pair:<10} {qty:<12.4f} @ ${price:.4f} \033[90m(Earned: ${cost:,.2f})\033[0m")
            
            print("\033[96m" + "="*95 + "\033[0m")
            print("\033[90mUpdating every 60 seconds. Press Ctrl+C to stop.\033[0m")
            
            # 4. Wait 60 seconds before refreshing
            time.sleep(60)
            
        except KeyboardInterrupt:
            os.system('clear' if os.name == 'posix' else 'cls')
            print("\033[92mDashboard safely closed.\033[0m")
            sys.exit(0)
        except Exception as e:
            print(f"\n\033[91mFailed to load dashboard: {e}\033[0m\n")
            time.sleep(60)

if __name__ == "__main__":
    run_dashboard()
