import websockets
import asyncio
import time
import json
from main import print_balances, buy_btc_with_usdt, sell_all_btc  # Ensure these work correctly and return price

# Slot-wise price analysis logic
async def main(n=6):
    uri = "wss://wbs.mexc.com/ws"  # MEXC spot WebSocket endpoint
    subscribe_message = {
        "method": "SUBSCRIPTION",
        "params": ["spot@public.deals.v3.api@BTCUSDT"],
        "id": 123
    }

    async with websockets.connect(uri) as websocket:
        await websocket.send(json.dumps(subscribe_message))
        print("Subscribed to BTCUSDT trades...")

        risk_slot_prices = []
        slot_index = 0
        risk_chance = 0

        while slot_index < n:
            slot_start = time.time()
            slot_prices = []

            while time.time() - slot_start < 10:
                try:
                    message = await websocket.recv()
                    data = json.loads(message)

                    # Corrected data extraction:
                    # 'd' is a dict with 'deals' list inside
                    if (
                        isinstance(data, dict) and
                        'd' in data and
                        isinstance(data['d'], dict) and
                        'deals' in data['d'] and
                        isinstance(data['d']['deals'], list)
                    ):
                        for deal in data['d']['deals']:
                            if 'p' in deal:
                                price = float(deal['p'])
                                slot_prices.append(price)
                    else:
                        print("Non-trade message:", data)

                except Exception as e:
                    print("WebSocket error during slot collection:", e)
                    break

            if not slot_prices:
                print(f"No prices collected for slot {slot_index + 1}.")
                continue

            min_price = min(slot_prices)
            print(f"Slot {slot_index + 1} Min Price: {min_price}")

            if not risk_slot_prices:
                risk_slot_prices.append(min_price)
                slot_index += 1
                continue

            last_min = risk_slot_prices[-1]
            if min_price < last_min:
                risk_slot_prices.append(min_price)
                risk_chance -= 1
            else:
                diff_percent = ((min_price - last_min) / last_min) * 100
                if diff_percent <= 0.5:
                    risk_slot_prices.append(min_price)
                    risk_chance += 0.5
                else:
                    print(f"Min price increase ({diff_percent:.2f}%) exceeds 0.5%. Not appending.")
                    risk_chance += 1

            slot_index += 1

        return risk_slot_prices, risk_chance


# Main trading loop
async def trade_loop():
    while True:
        print("\n--- New Analysis Cycle ---")
        risk_slot_prices, risk_chance = await main()
        print("Final risk slot prices:", risk_slot_prices)
        print("Risk chance:", risk_chance)

        if risk_chance < 0:
            print("Buying BTC with all available USDT...")
            buy_price = buy_btc_with_usdt()  # Must return limit_price

            if buy_price is None:
                print("Buy failed. Skipping to next loop.")
                await asyncio.sleep(2)
                continue

            print("Waiting for price to increase by 0.1% to sell...")
            uri = "wss://wbs.mexc.com/ws"
            subscribe_msg = {
                "method": "SUBSCRIPTION",
                "params": ["spot@public.deals.v3.api@BTCUSDT"],
                "id": 456
            }

            try:
                async with websockets.connect(uri) as websocket:
                    await websocket.send(json.dumps(subscribe_msg))

                    while True:
                        try:
                            message = await websocket.recv()
                            data = json.loads(message)

                            if (
                                isinstance(data, dict) and
                                'd' in data and
                                isinstance(data['d'], dict) and
                                'deals' in data['d'] and
                                isinstance(data['d']['deals'], list) and
                                len(data['d']['deals']) > 0
                            ):
                                current_price = float(data['d']['deals'][0]['p'])

                                if current_price >= (buy_price * 1.001):  # 0.1% gain
                                    print(f"Price increased to {current_price}. Selling BTC...")
                                    sell_all_btc()
                                    break
                        except Exception as e:
                            print("WebSocket error during sell monitoring:", e)
                            break
            except Exception as e:
                print("WebSocket connection failed:", e)

        else:
            print("Risk chance is positive. No buy executed.")

        print("Sleeping before next cycle...\n")
        await asyncio.sleep(1)


# Entry point
if __name__ == "__main__":
    try:
        asyncio.run(trade_loop())
    except KeyboardInterrupt:
        print("\nExited cleanly with Ctrl+C.")
