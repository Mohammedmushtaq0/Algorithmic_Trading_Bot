import time
import hmac
import hashlib
import requests
import os
from dotenv import load_dotenv

# Load MEXC API keys
load_dotenv()
API_KEY = os.getenv("MEXC_API_KEY")
API_SECRET = os.getenv("MEXC_API_SECRET")

class MexcClient:
    def __init__(self, api_key, api_secret):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = 'https://api.mexc.com'

    def _sign(self, params):
        query_string = '&'.join([f"{k}={v}" for k, v in sorted(params.items())])
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature

    def _get(self, path, params={}):
        params['timestamp'] = int(time.time() * 1000)
        params['signature'] = self._sign(params)
        headers = {"X-MEXC-APIKEY": self.api_key}
        return requests.get(self.base_url + path, headers=headers, params=params).json()

    def _post(self, path, params={}):
        params['timestamp'] = int(time.time() * 1000)
        params['signature'] = self._sign(params)
        headers = {"X-MEXC-APIKEY": self.api_key}
        return requests.post(self.base_url + path, headers=headers, params=params).json()

    def get_account_info(self):
        return self._get('/api/v3/account')

    def place_market_order(self, symbol, side, quantity):
        return self._post('/api/v3/order', {
            "symbol": symbol,
            "side": side,
            "type": "MARKET",
            "quantity": quantity
        })

    def get_price(self, symbol):
        return requests.get(f"{self.base_url}/api/v3/ticker/price", params={"symbol": symbol}).json()


client = MexcClient(API_KEY, API_SECRET)

# Print BTC/USDT balances
def print_balances():
    account_info = client.get_account_info()
    btc_balance = 0
    usdt_balance = 0
    for asset in account_info.get("balances", []):
        if asset['asset'] == 'BTC':
            btc_balance = float(asset['free'])
        elif asset['asset'] == 'USDT':
            usdt_balance = float(asset['free'])
    print(f"BTC Balance: {btc_balance}")
    print(f"USDT Balance: {usdt_balance}")
    return btc_balance, usdt_balance


# Limit buy BTC with USDT
def buy_btc_with_usdt():
    print("\n[Maker-Style Limit Buy] Checking balances...")
    _, usdt_balance = print_balances()

    usdt_to_spend = round(usdt_balance - 5, 2)
    if usdt_to_spend < 5:
        print("Insufficient USDT to buy BTC.")
        return None

    price_data = client.get_price("BTCUSDT")
    market_price = float(price_data.get("price", 0))
    if market_price == 0:
        print("Failed to fetch BTC price.")
        return None

    limit_price = round(market_price - 0.1, 2)
    qty = round(usdt_to_spend / limit_price, 6)

    print(f"Placing LIMIT BUY for {qty} BTC @ {limit_price:.2f} USDT...")
    response = client._post('/api/v3/order', {
        "symbol": "BTCUSDT",
        "side": "BUY",
        "type": "LIMIT",
        "quantity": qty,
        "price": f"{limit_price:.2f}",
        "timeInForce": "GTC"
    })
    print("Order placed. Response:", response)
    print_balances()

    return limit_price  # ✅ Important fix


# Sell all BTC with limit order
def sell_all_btc():
    print("\n[Maker-Style Limit Sell] Checking balances...")
    btc_balance, _ = print_balances()
    if btc_balance <= 0:
        print("No BTC to sell.")
        return

    qty = float(f"{btc_balance:.6f}")

    price_data = client.get_price("BTCUSDT")
    market_price = float(price_data.get("price", 0))
    if market_price == 0:
        print("Failed to fetch BTC price.")
        return

    limit_price = round(market_price + 0.1, 2)

    print(f"Placing LIMIT SELL for {qty} BTC @ {limit_price:.2f} USDT...")
    response = client._post('/api/v3/order', {
        "symbol": "BTCUSDT",
        "side": "SELL",
        "type": "LIMIT",
        "quantity": qty,
        "price": f"{limit_price:.2f}",
        "timeInForce": "GTC"
    })
    print("Order placed. Response:", response)
    print_balances()
