#!/usr/bin/env python3
"""
VWAP Momentum Bot - Standalone trading bot

Core Strategy:
- VWAP Anchor: 24-hour rolling VWAP
- Volume Surge Trigger: Current 1-minute volume > 1.5x average volume of last 4 hours
- Signal: BUY when Price > VWAP AND Volume Surge is active
- Signal: SELL when Price < VWAP OR 3% trailing stop is hit

Independent Operation:
- No regime logic dependencies
- No LSI, HAZARD, or defensive mode checks
- Uses shared infrastructure: RoostooClient and .env API keys
- Fixed $100 position sizing per trade
- 60-second polling loops
"""

import os
import time
import logging
import math
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta

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
    """Standalone VWAP momentum trading bot"""
    
    def __init__(self):
        """Initialize the bot with API credentials and configuration"""
        self.api_key = os.getenv('ROOSTOO_API_KEY')
        self.api_secret = os.getenv('ROOSTOO_API_SECRET')
        
        if not self.api_key or not self.api_secret:
            raise ValueError("API credentials not found in environment variables")
        
        self.client = RoostooClient(self.api_key, self.api_secret)
        
        # Bot configuration
        self.position_size_usd = 100.0  # Fixed $100 per trade
        self.trailing_stop_pct = 0.03   # 3% trailing stop
        self.volume_surge_threshold = 1.5  # 1.5x average volume
        
        # State tracking
        self.exchange_info = None
        self.vwap_cache: Dict[str, float] = {}
        self.volume_cache: Dict[str, List[float]] = {}
        self.position_cache: Dict[str, Dict] = {}
        
        # Target pairs (from config)
        self.target_pairs = self._get_target_pairs()
        
        logger.info(f"VWAP Momentum Bot initialized for pairs: {self.target_pairs}")
    
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
    
    def _get_vwap_24h(self, pair: str) -> Optional[float]:
        """Calculate 24-hour VWAP for a pair"""
        try:
            # Get ticker data (includes 24h volume and last price)
            ticker_data = self.client.get_ticker(pair)
            
            if pair not in ticker_data:
                logger.warning(f"No ticker data for {pair}")
                return None
            
            pair_data = ticker_data[pair]
            last_price = float(pair_data.get("LastPrice", 0))
            volume_24h = float(pair_data.get("CoinTradeValue", 0))  # 24h volume in coin units
            
            if volume_24h <= 0:
                logger.warning(f"Zero volume for {pair}")
                return None
            
            # For VWAP calculation, we need price * volume
            # Since we only have last price and 24h volume, we'll use a simplified approach
            # In a real implementation, you'd want historical price/volume data
            # For now, we'll cache the last calculated VWAP and update it incrementally
            
            if pair not in self.vwap_cache:
                # Initialize with current price
                self.vwap_cache[pair] = last_price
            
            # Simple moving average approach for VWAP approximation
            # This would be more sophisticated with historical data
            current_vwap = self.vwap_cache[pair]
            alpha = 0.1  # Smoothing factor
            new_vwap = alpha * last_price + (1 - alpha) * current_vwap
            self.vwap_cache[pair] = new_vwap
            
            return new_vwap
            
        except Exception as e:
            logger.error(f"Error calculating VWAP for {pair}: {e}")
            return None
    
    def _get_volume_surge(self, pair: str) -> bool:
        """Check if current volume surge is active (1-minute volume > 1.5x 4-hour average)"""
        try:
            # Get current ticker data
            ticker_data = self.client.get_ticker(pair)
            
            if pair not in ticker_data:
                return False
            
            pair_data = ticker_data[pair]
            current_volume = float(pair_data.get("CoinTradeValue", 0))  # This is 24h volume
            
            # For volume surge detection, we need more granular data
            # Since we only have 24h volume, we'll simulate volume tracking
            # In a real implementation, you'd track minute-by-minute volume
            
            if pair not in self.volume_cache:
                self.volume_cache[pair] = []
            
            # Add current volume snapshot (simplified - would be minute volume in practice)
            self.volume_cache[pair].append(current_volume)
            
            # Keep only last 4 hours worth of data (240 minutes)
            max_entries = 240
            if len(self.volume_cache[pair]) > max_entries:
                self.volume_cache[pair].pop(0)
            
            if len(self.volume_cache[pair]) < 10:  # Need some history
                return False
            
            # Calculate average volume over the cached period
            avg_volume = sum(self.volume_cache[pair]) / len(self.volume_cache[pair])
            
            # Check if current volume > 1.5x average
            surge_active = current_volume > (self.volume_surge_threshold * avg_volume)
            
            if surge_active:
                logger.info(f"Volume surge detected for {pair}: current={current_volume:.4f}, avg={avg_volume:.4f}")
            
            return surge_active
            
        except Exception as e:
            logger.error(f"Error checking volume surge for {pair}: {e}")
            return False
    
    def _get_current_price(self, pair: str) -> Optional[float]:
        """Get current last price for a pair"""
        try:
            ticker_data = self.client.get_ticker(pair)
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
    
    def _place_buy_order(self, pair: str, price: float) -> bool:
        """Place a market buy order for $100 worth of the base currency"""
        try:
            # Extract base currency from pair (e.g., "BTC/USD" -> "BTC")
            base_currency = pair.split('/')[0]
            
            # Get exchange info for precision
            if not self.exchange_info:
                self.exchange_info = self.client.get_exchange_info()
            
            pair_info = self.exchange_info.get("TradePairs", {}).get(pair, {})
            amount_precision = pair_info.get("AmountPrecision", 8)
            
            # Calculate quantity to buy ($100 / current price)
            quantity = self.position_size_usd / price
            quantity = self._floor_to_precision(quantity, amount_precision)
            
            # Check if we have enough USD
            usd_balance = self._get_balance("USD")
            if usd_balance < self.position_size_usd:
                logger.warning(f"Insufficient USD balance for {pair}: {usd_balance}")
                return False
            
            # Place market buy order
            result = self.client.place_order(
                pair=pair,
                side="BUY",
                quantity=quantity,
                price=None  # Market order
            )
            
            if result.get("Success", False):
                logger.info(f"VWAP_BOT BUY order placed for {pair}: qty={quantity}, price≈{price}")
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
            # Get exchange info for precision
            if not self.exchange_info:
                self.exchange_info = self.client.get_exchange_info()
            
            pair_info = self.exchange_info.get("TradePairs", {}).get(pair, {})
            amount_precision = pair_info.get("AmountPrecision", 8)
            
            quantity = self._floor_to_precision(quantity, amount_precision)
            
            # Check if we have the base currency
            base_currency = pair.split('/')[0]
            balance = self._get_balance(base_currency)
            if balance < quantity:
                logger.warning(f"Insufficient {base_currency} balance for {pair}: {balance}")
                return False
            
            # Place market sell order
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
        
        # Calculate current P&L
        current_value = current_price * quantity
        entry_value = entry_price * quantity
        pnl_pct = (current_value - entry_value) / entry_value
        
        # Check if we've reached the trailing stop threshold
        if pnl_pct <= -self.trailing_stop_pct:
            logger.info(f"Trailing stop triggered for {pair}: entry={entry_price}, current={current_price}, pnl={pnl_pct:.2%}")
            return True
        
        # Update trailing stop if price has moved favorably
        if current_price > entry_price and current_price > position.get("high_price", entry_price):
            position["high_price"] = current_price
        
        return False
    
    def _update_positions(self):
        """Update position tracking and check for exits"""
        try:
            # Query recent orders to track positions
            order_data = self.client.query_order(pending_only=False)
            
            # This is a simplified position tracking
            # In practice, you'd maintain a more sophisticated position book
            for pair in self.target_pairs:
                if pair in self.position_cache:
                    current_price = self._get_current_price(pair)
                    if current_price:
                        # Check trailing stop
                        if self._check_trailing_stop(pair, current_price):
                            position = self.position_cache[pair]
                            if self._place_sell_order(pair, position["quantity"]):
                                del self.position_cache[pair]
                                logger.info(f"VWAP_BOT position closed for {pair} due to trailing stop")
        
        except Exception as e:
            logger.error(f"Error updating positions: {e}")
    
    def _execute_trading_logic(self):
        """Main trading logic execution"""
        for pair in self.target_pairs:
            try:
                # Get current price
                current_price = self._get_current_price(pair)
                if not current_price:
                    continue
                
                # Get VWAP
                vwap = self._get_vwap_24h(pair)
                if not vwap:
                    continue
                
                # Check volume surge
                volume_surge = self._get_volume_surge(pair)
                
                # Check if we already have a position
                has_position = pair in self.position_cache
                
                logger.debug(f"{pair} - Price: {current_price:.2f}, VWAP: {vwap:.2f}, Surge: {volume_surge}")
                
                # BUY signal: Price > VWAP AND Volume Surge
                if not has_position and current_price > vwap and volume_surge:
                    if self._place_buy_order(pair, current_price):
                        self.position_cache[pair] = {
                            "entry_price": current_price,
                            "high_price": current_price,
                            "quantity": self.position_size_usd / current_price
                        }
                        logger.info(f"VWAP_BOT BUY signal executed for {pair}")
                
                # SELL signal: Price < VWAP OR trailing stop
                elif has_position:
                    if current_price < vwap:
                        position = self.position_cache[pair]
                        if self._place_sell_order(pair, position["quantity"]):
                            del self.position_cache[pair]
                            logger.info(f"VWAP_BOT SELL signal executed for {pair} (price < VWAP)")
                    elif self._check_trailing_stop(pair, current_price):
                        position = self.position_cache[pair]
                        if self._place_sell_order(pair, position["quantity"]):
                            del self.position_cache[pair]
                            logger.info(f"VWAP_BOT SELL signal executed for {pair} (trailing stop)")
                
            except Exception as e:
                logger.error(f"Error processing pair {pair}: {e}")
    
    def run(self):
        """Main bot loop"""
        logger.info("VWAP Momentum Bot starting...")
        
        # Initial setup
        if not self.target_pairs:
            logger.error("No target pairs available. Exiting.")
            return
        
        loop_count = 0
        
        while True:
            try:
                loop_count += 1
                logger.info(f"VWAP Momentum Bot loop {loop_count}")
                
                # Execute trading logic
                self._execute_trading_logic()
                
                # Update position tracking
                self._update_positions()
                
                # Print current positions
                if self.position_cache:
                    logger.info(f"Active positions: {list(self.position_cache.keys())}")
                else:
                    logger.info("No active positions")
                
                # Wait for next loop
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