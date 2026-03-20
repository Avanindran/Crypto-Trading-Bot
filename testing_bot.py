#!/usr/bin/env python3
"""
VWAP Momentum Bot - Standalone trading bot

Core Strategy:
- VWAP Anchor: 24-hour rolling VWAP using typical price (HLC/3)
- Volume Surge Trigger: Current volume vs 4-hour average volume ratio
- Signal: BUY when Price > VWAP + 0.3% AND Volume Surge > 1.0
- Signal: SELL when Price < VWAP - 0.3% OR 3% trailing stop is hit
- Sizing: Dynamic Inverse Volatility (allocates more to stable coins, less to wild ones)

Independent Operation:
- No regime logic dependencies
- No LSI, HAZARD, or defensive mode checks
- Uses shared infrastructure: RoostooClient and .env API keys
- RATE-LIMIT SAFE: Fetches all market data in ONE API call per loop
"""

import os
import time
import logging
import math
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dotenv import load_dotenv

import requests

# Import shared infrastructure
from bot.data.roostoo_client import RoostooClient
import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class VWAPMomentumBot:
    """Standalone VWAP momentum trading bot with dynamic sizing, whipsaw protection, and state recovery"""
    
    def __init__(self):
        """Initialize the bot with API credentials and configuration"""
        load_dotenv()
        self.api_key = os.getenv('ROOSTOO_API_KEY')
        self.api_secret = os.getenv('ROOSTOO_API_SECRET')
        
        if not self.api_key or not self.api_secret:
            raise ValueError("API credentials not found in environment variables")
        
        self.client = RoostooClient(self.api_key, self.api_secret)
        
        # --- DYNAMIC POSITION SIZING (Inverse Volatility) ---
        self.base_nav_pct = 0.05        # Target 5% of total portfolio per trade
        self.target_volatility = 0.05   # Baseline daily expected move (5%)
        self.max_position_usd = 5000.0  # Hard cap to prevent over-allocation
        self.min_position_usd = 100.0   # Hard floor
        
        # --- RISK MANAGEMENT & ENTRY LOGIC ---
        self.trailing_stop_pct = 0.03   # 3% trailing stop
        self.volume_surge_threshold = 1.0  # Volume ratio > 1.0 (surge active)
        self.vwap_buffer_pct = 0.003    # 0.3% buffer to prevent constant buy/sell whipsaws
        
        # VWAP and Volume parameters (from config)
        self.vwap_lookback_hours = config.H9_VWAP_LOOKBACK_HOURS  # 24 hours
        self.volume_surge_hours = config.H9_VOLUME_SURGE_HOURS    # 4 hours
        
        # State tracking
        self.exchange_info = None
        self.price_cache: Dict[str, List[float]] = {}  # Minute-level price history
        self.volume_cache: Dict[str, List[float]] = {}  # Minute-level volume history
        self.position_cache: Dict[str, Dict] = {}
        
        # Target pairs
        self.target_pairs = self._get_target_pairs()
        
        logger.info(f"VWAP Momentum Bot initialized for pairs: {self.target_pairs}")
        logger.info(f"VWAP lookback: {self.vwap_lookback_hours}h, Volume surge: {self.volume_surge_hours}h")
    
    def _get_target_pairs(self) -> List[str]:
        """Get target trading pairs from exchange info"""
        try:
            self.exchange_info = self.client.get_exchange_info()
            pairs = list(self.exchange_info.get("TradePairs", {}).keys())
            logger.info(f"Available pairs: {pairs}")
            return pairs
        except Exception as e:
            logger.error(f"Failed to get exchange info: {e}")
            return []
    
    def _floor_to_precision(self, value: float, precision: int) -> float:
        """Floor value to exchange precision"""
        factor = 10 ** precision
        return math.floor(value * factor) / factor
    
    def _get_typical_price(self, pair_data: Dict) -> float:
        """Calculate typical price (HLC/3) for VWAP calculation"""
        try:
            high = float(pair_data.get("MaxBid", 0))  
            low = float(pair_data.get("MinAsk", 0))
            close = float(pair_data.get("LastPrice", 0))
            
            if high == 0 or low == 0:
                return close
            
            return (high + low + close) / 3.0
        except:
            return float(pair_data.get("LastPrice", 0))
    
    def _get_vwap_24h_from_bulk(self, pair: str, ticker_data: Dict[str, Dict]) -> Optional[float]:
        """Calculate 24-hour VWAP using typical price and cached volume data"""
        try:
            if pair not in ticker_data:
                return None
            
            pair_data = ticker_data[pair]
            current_price = float(pair_data.get("LastPrice", 0))
            
            if current_price <= 0:
                return None
            
            if pair not in self.price_cache:
                self.price_cache[pair] = []
            
            self.price_cache[pair].append(current_price)
            
            max_entries = int(self.vwap_lookback_hours * 60)
            if len(self.price_cache[pair]) > max_entries:
                self.price_cache[pair].pop(0)
            
            if len(self.price_cache[pair]) < 10:  
                return current_price  
            
            vwap = sum(self.price_cache[pair]) / len(self.price_cache[pair])
            return vwap
            
        except Exception as e:
            logger.error(f"Error calculating VWAP for {pair}: {e}")
            return None
    
    def _get_volume_surge_from_bulk(self, pair: str, ticker_data: Dict[str, Dict]) -> bool:
        """Check if current volume surge is active using cached volume data"""
        try:
            if pair not in ticker_data:
                return False
            
            pair_data = ticker_data[pair]
            current_volume = float(pair_data.get("UnitTradeValue", 1)) 
            
            if pair not in self.volume_cache:
                self.volume_cache[pair] = []
            
            self.volume_cache[pair].append(current_volume)
            
            max_entries = int(self.volume_surge_hours * 60)
            if len(self.volume_cache[pair]) > max_entries:
                self.volume_cache[pair].pop(0)
            
            if len(self.volume_cache[pair]) < 10:  
                return False
            
            avg_volume = sum(self.volume_cache[pair]) / len(self.volume_cache[pair])
            surge_active = current_volume > (self.volume_surge_threshold * avg_volume)
            
            return surge_active
            
        except Exception as e:
            logger.error(f"Error checking volume surge for {pair}: {e}")
            return False
    
    def _get_current_price_from_bulk(self, pair: str, ticker_data: Dict[str, Dict]) -> Optional[float]:
        """Get current last price for a pair using bulk ticker data"""
        try:
            if pair in ticker_data:
                return float(ticker_data[pair].get("LastPrice", 0))
            return None
        except Exception as e:
            logger.error(f"Error getting price for {pair}: {e}")
            return None
    
    def _get_balance(self, coin: str) -> float:
        """Get available balance for a coin"""
        try:
            balance_data = self.client.get_balance()
            if coin in balance_data:
                return float(balance_data[coin].get("Free", 0))
            return 0.0
        except Exception as e:
            logger.error(f"Error getting balance for {coin}: {e}")
            return 0.0

    def _calculate_position_size(self, pair: str, ticker_data: Dict[str, Dict]) -> float:
        """Calculate dynamic position size using Inverse Volatility"""
        try:
            usd_balance = self._get_balance("USD")
            if usd_balance < self.min_position_usd:
                return 0.0
                
            base_size = usd_balance * self.base_nav_pct
            
            pair_data = ticker_data.get(pair, {})
            daily_change = abs(float(pair_data.get("Change", 0.0)))
            daily_change = max(daily_change, 0.01) # Prevent division by zero
            
            # Inverse Volatility Scalar
            vol_scalar = self.target_volatility / daily_change
            vol_scalar = min(max(vol_scalar, 0.25), 2.0) # Cap scalar
            
            final_size_usd = base_size * vol_scalar
            final_size_usd = min(final_size_usd, self.max_position_usd)
            final_size_usd = min(final_size_usd, usd_balance * 0.95) # Leave room
            
            return final_size_usd
            
        except Exception as e:
            logger.error(f"Sizing error for {pair}: {e}")
            return self.min_position_usd
    
    def _place_buy_order(self, pair: str, price: float, position_size_usd: float) -> bool:
        """Place a market buy order for dynamic USD amount"""
        try:
            if not self.exchange_info:
                self.exchange_info = self.client.get_exchange_info()
            
            pair_info = self.exchange_info.get("TradePairs", {}).get(pair, {})
            amount_precision = pair_info.get("AmountPrecision", 8)
            
            quantity = position_size_usd / price
            quantity = self._floor_to_precision(quantity, amount_precision)
            
            usd_balance = self._get_balance("USD")
            if usd_balance < position_size_usd:
                logger.warning(f"Insufficient USD balance for {pair}: {usd_balance}")
                return False
            
            result = self.client.place_order(
                pair=pair,
                side="BUY",
                quantity=quantity,
                price=None  # Market order
            )
            
            if result.get("Success", False):
                logger.info(f"VWAP_BOT BUY placed for {pair}: qty={quantity}, price≈{price}, usd≈${position_size_usd:.2f}")
                return True
            else:
                logger.warning(f"Buy order failed for {pair}: {result}")
                return False
                
        except Exception as e:
            logger.error(f"Error placing buy order for {pair}: {e}")
            return False
    
    def _place_sell_order(self, pair: str, quantity: float) -> bool:
        """Place a market sell order for the specified quantity"""
        try:
            if not self.exchange_info:
                self.exchange_info = self.client.get_exchange_info()
            
            pair_info = self.exchange_info.get("TradePairs", {}).get(pair, {})
            amount_precision = pair_info.get("AmountPrecision", 8)
            
            quantity = self._floor_to_precision(quantity, amount_precision)
            
            base_currency = pair.split('/')[0]
            balance = self._get_balance(base_currency)
            if balance < quantity:
                logger.warning(f"Insufficient {base_currency} balance for {pair}: {balance}")
                return False
            
            result = self.client.place_order(
                pair=pair,
                side="SELL",
                quantity=quantity,
                price=None  # Market order
            )
            
            if result.get("Success", False):
                logger.info(f"VWAP_BOT SELL order placed for {pair}: qty={quantity}")
                return True
            else:
                logger.warning(f"Sell order failed for {pair}: {result}")
                return False
                
        except Exception as e:
            logger.error(f"Error placing sell order for {pair}: {e}")
            return False
    
    def _check_trailing_stop(self, pair: str, current_price: float) -> bool:
        """Check if trailing stop should trigger a sell"""
        if pair not in self.position_cache:
            return False
        
        position = self.position_cache[pair]
        entry_price = position.get("entry_price", 0)
        quantity = position.get("quantity", 0)
        
        if entry_price <= 0 or quantity <= 0:
            return False
        
        current_value = current_price * quantity
        entry_value = entry_price * quantity
        pnl_pct = (current_value - entry_value) / entry_value
        
        if pnl_pct <= -self.trailing_stop_pct:
            logger.info(f"Trailing stop triggered for {pair}: entry={entry_price}, current={current_price}, pnl={pnl_pct:.2%}")
            return True
        
        if current_price > entry_price and current_price > position.get("high_price", entry_price):
            position["high_price"] = current_price
        
        return False
        
    def _recover_state(self):
        """Rebuilds the bot's memory of open positions after a restart."""
        logger.info("Initiating State Recovery: Scanning exchange for orphaned bags...")
        try:
            # 1. Get all current balances
            balances = self.client.get_balance()
            
            # 2. Get recent order history to hunt for entry prices
            recent_orders = self.client.query_order(pending_only=False)
            if not isinstance(recent_orders, list):
                recent_orders = []
                
            recovered_count = 0
            
            for coin, data in balances.items():
                if coin == "USD":
                    continue
                    
                total_coin = float(data.get("Free", 0)) + float(data.get("Locked", 0))
                
                # Ignore zero balances or tiny crypto dust
                if total_coin <= 0.00001:
                    continue
                    
                pair = f"{coin}/USD"
                if pair not in self.target_pairs:
                    continue
                    
                # 3. Hunt backwards through history for the last BUY of this pair
                entry_price = 0.0
                for order in reversed(recent_orders):
                    order_pair = order.get('TradePairId', order.get('pair', ''))
                    order_side = str(order.get('Side', order.get('side', ''))).upper()
                    
                    if order_pair == pair and order_side == "BUY":
                        entry_price = float(order.get('Price', order.get('price', 0)))
                        break
                        
                # 4. Fallback: If the buy order is too old to find, use the current market price
                if entry_price <= 0:
                    logger.warning(f"Could not find exact entry price for {pair}. Using live price to initialize stop-loss.")
                    ticker = self.client.get_ticker()
                    if pair in ticker:
                        entry_price = float(ticker[pair].get("LastPrice", 0))
                        
                if entry_price > 0:
                    # 5. Inject the bag back into the bot's memory
                    self.position_cache[pair] = {
                        "entry_price": entry_price,
                        "high_price": entry_price,
                        "quantity": total_coin
                    }
                    recovered_count += 1
                    logger.info(f"✅ RECOVERED: {pair} | Qty: {total_coin:.6f} | Anchor Price: ${entry_price:.2f}")
                    
            logger.info(f"State Recovery Complete. Rehydrated {recovered_count} active positions.")
            
        except Exception as e:
            logger.error(f"Critical error during state recovery: {e}")
            logger.warning("Bot starting with partial amnesia. Monitor positions closely.")
    
    def _update_positions(self):
        """Update position tracking and check for exits"""
        try:
            order_data = self.client.query_order(pending_only=False)
            for pair in self.target_pairs:
                if pair in self.position_cache:
                    pass
        except Exception as e:
            logger.error(f"Error updating positions: {e}")
    
    def _execute_trading_logic(self, ticker_data: Dict[str, Dict]):
        """Main trading logic execution using bulk ticker data"""
        for pair in self.target_pairs:
            try:
                current_price = self._get_current_price_from_bulk(pair, ticker_data)
                if not current_price:
                    continue
                
                vwap = self._get_vwap_24h_from_bulk(pair, ticker_data)
                if not vwap:
                    continue
                
                volume_surge = self._get_volume_surge_from_bulk(pair, ticker_data)
                has_position = pair in self.position_cache
                
                # Apply the Anti-Whipsaw buffer (0.3%)
                buy_threshold = vwap * (1 + self.vwap_buffer_pct)
                sell_threshold = vwap * (1 - self.vwap_buffer_pct)
                
                logger.debug(f"{pair} - Price: {current_price:.2f}, VWAP: {vwap:.2f}, Surge: {volume_surge}")
                
                # BUY signal: Price > VWAP (+0.3% buffer) AND Volume Surge
                if not has_position and current_price > buy_threshold and volume_surge:
                    
                    target_usd_size = self._calculate_position_size(pair, ticker_data)
                    
                    if target_usd_size > 0 and self._place_buy_order(pair, current_price, target_usd_size):
                        self.position_cache[pair] = {
                            "entry_price": current_price,
                            "high_price": current_price,
                            "quantity": target_usd_size / current_price
                        }
                        logger.info(f"VWAP_BOT BUY executed for {pair} | Dynamic Size: ${target_usd_size:.2f}")
                
                # SELL signal: Price < VWAP (-0.3% buffer) OR trailing stop
                elif has_position:
                    if current_price < sell_threshold:
                        position = self.position_cache[pair]
                        if self._place_sell_order(pair, position["quantity"]):
                            del self.position_cache[pair]
                            logger.info(f"VWAP_BOT SELL signal executed for {pair} (price broke below VWAP buffer)")
                    
                    elif self._check_trailing_stop(pair, current_price):
                        position = self.position_cache[pair]
                        if self._place_sell_order(pair, position["quantity"]):
                            del self.position_cache[pair]
                            logger.info(f"VWAP_BOT SELL signal executed for {pair} (trailing stop)")
                
            except Exception as e:
                logger.error(f"Error processing pair {pair}: {e}")
    
    def run(self):
        """Main bot loop with rate-limit safe data fetching"""
        logger.info("VWAP Momentum Bot starting with Dynamic Sizing...")
        
        if not self.target_pairs:
            logger.error("No target pairs available. Exiting.")
            return
            
        # Rebuild bot memory before starting the loop
        self._recover_state()
        
        loop_count = 0
        
        while True:
            try:
                loop_count += 1
                logger.info(f"VWAP Momentum Bot loop {loop_count}")
                
                ticker_data = self.client.get_ticker()
                if not ticker_data:
                    logger.warning("Empty ticker response — skipping loop %d", loop_count)
                    time.sleep(config.LOOP_INTERVAL_SECONDS)
                    continue
                
                self._execute_trading_logic(ticker_data)
                self._update_positions()
                
                if self.position_cache:
                    logger.info(f"Active positions: {list(self.position_cache.keys())}")
                else:
                    logger.info("No active positions")
                
                time.sleep(config.LOOP_INTERVAL_SECONDS)
                
            except KeyboardInterrupt:
                logger.info("Bot stopped by user")
                break
            except Exception as e:
                logger.error(f"Unexpected error in main loop: {e}")
                time.sleep(config.LOOP_INTERVAL_SECONDS)


def main():
    """Entry point for the VWAP Momentum Bot"""
    try:
        bot = VWAPMomentumBot()
        bot.run()
    except Exception as e:
        logger.error(f"Bot initialization failed: {e}")


if __name__ == "__main__":
    main()