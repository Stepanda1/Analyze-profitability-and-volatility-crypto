from __future__ import annotations

import os
import time
from pathlib import Path

import pandas as pd
import requests

BASE_URL = "https://api.coingecko.com/api/v3"
START_DATE = "2025-06-15"
END_DATE_EXCLUSIVE = "2026-06-15"
OUTPUT_FILE = Path("data/raw_crypto_data.csv")

COINS = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "BNB": "binancecoin",
    "SOL": "solana",
    "XRP": "ripple",
    "DOGE": "dogecoin",
    "ADA": "cardano",
    "TRX": "tron",
}


def fetch_coin(coin_id: str, symbol: str) -> pd.DataFrame:
    """Download one coin and return one daily row per date."""
    url = f"{BASE_URL}/coins/{coin_id}/market_chart/range"
    params = {
        "vs_currency": "usd",
        "from": START_DATE,
        "to": END_DATE_EXCLUSIVE,
        "interval": "daily",
        "precision": "full",
    }

    headers = {"User-Agent": "crypto-analysis-student-project/1.0"}
    api_key = os.getenv("COINGECKO_API_KEY")
    if api_key:
        headers["x-cg-demo-api-key"] = api_key

    last_error: Exception | None = None
    for attempt in range(5):
        try:
            response = requests.get(url, params=params, headers=headers, timeout=60)
            if response.status_code == 429:
                time.sleep(15 * (attempt + 1))
                continue
            response.raise_for_status()
            payload = response.json()
            break
        except (requests.RequestException, ValueError) as error:
            last_error = error
            time.sleep(5 * (attempt + 1))
    else:
        raise RuntimeError(f"Не удалось загрузить {symbol}: {last_error}")

    prices = pd.DataFrame(payload["prices"], columns=["timestamp", "price"])
    caps = pd.DataFrame(payload["market_caps"], columns=["timestamp", "market_cap"])
    volumes = pd.DataFrame(payload["total_volumes"], columns=["timestamp", "total_volume"])

    frame = prices.merge(caps, on="timestamp").merge(volumes, on="timestamp")
    frame["date"] = pd.to_datetime(frame["timestamp"], unit="ms", utc=True).dt.date
    frame["symbol"] = symbol
    frame["coin_id"] = coin_id

    frame = frame[["date", "symbol", "coin_id", "price", "market_cap", "total_volume"]]
    frame["date"] = pd.to_datetime(frame["date"])
    frame = frame[
        (frame["date"] >= pd.Timestamp(START_DATE))
        & (frame["date"] < pd.Timestamp(END_DATE_EXCLUSIVE))
    ]
    frame = frame.drop_duplicates(subset=["symbol", "date"], keep="last")
    return frame.sort_values("date").reset_index(drop=True)


def main() -> None:
    frames: list[pd.DataFrame] = []

    for index, (symbol, coin_id) in enumerate(COINS.items(), start=1):
        print(f"[{index}/{len(COINS)}] Загружаю {symbol}...")
        frame = fetch_coin(coin_id, symbol)
        print(f"Получено наблюдений: {len(frame)}")
        frames.append(frame)
        time.sleep(3)

    data = pd.concat(frames, ignore_index=True)
    data = data.sort_values(["symbol", "date"]).reset_index(drop=True)

    counts = data.groupby("symbol")["date"].nunique()
    if set(counts.index) != set(COINS):
        raise RuntimeError("В итоговом файле отсутствуют некоторые криптовалюты")
    if not (counts == 365).all():
        raise RuntimeError(f"Ожидалось по 365 дат на монету, получено:\n{counts}")

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    data.to_csv(OUTPUT_FILE, index=False, date_format="%Y-%m-%d")
    print(f"Сохранено {len(data)} строк в {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
