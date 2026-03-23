#!/usr/bin/env python3
"""
Sync market data and trade history from a local MT5 terminal to the hosted API.

This script must run on the same Windows machine where MetaTrader 5 is installed
and logged in, because the Render backend cannot access the desktop terminal.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import requests


PROJECT_ROOT = Path(__file__).resolve().parent
BACKEND_PATH = PROJECT_ROOT / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.append(str(BACKEND_PATH))

from core.mt5_importer import MT5DataImporter  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sync local MetaTrader 5 data to the EAOptimizer cloud API."
    )
    parser.add_argument(
        "--api-url",
        default=os.getenv("EAOPTIMIZER_REMOTE_API_URL", "").strip(),
        help="Public base URL of the hosted API, e.g. https://eaoptimizer.onrender.com",
    )
    parser.add_argument("--symbol", default="XAUUSD", help="Trading symbol to sync.")
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="How many days of MT5 history should be collected.",
    )
    parser.add_argument(
        "--mt5-path",
        default=os.getenv("MT5_PATH"),
        help="Optional path to terminal64.exe if MT5 is not in the default location.",
    )
    parser.add_argument(
        "--skip-market",
        action="store_true",
        help="Skip market data upload and send only trade history.",
    )
    parser.add_argument(
        "--skip-trades",
        action="store_true",
        help="Skip trade history upload and send only market data.",
    )
    return parser.parse_args()


def write_temp_csv(dataframe, prefix: str) -> str:
    temp_file = tempfile.NamedTemporaryFile(
        delete=False, suffix=".csv", prefix=f"{prefix}_"
    )
    temp_file.close()
    dataframe.to_csv(temp_file.name, index=False)
    return temp_file.name


def upload_file(api_url: str, endpoint: str, file_path: str, symbol: str) -> dict:
    with open(file_path, "rb") as file_handle:
        response = requests.post(
            f"{api_url.rstrip('/')}{endpoint}",
            files={"file": (os.path.basename(file_path), file_handle, "text/csv")},
            data={"symbol": symbol},
            timeout=180,
        )

    response.raise_for_status()
    return response.json()


def main() -> int:
    args = parse_args()

    if not args.api_url:
        print("Missing --api-url or EAOPTIMIZER_REMOTE_API_URL.", file=sys.stderr)
        return 1

    if args.skip_market and args.skip_trades:
        print("Cannot skip both market and trades uploads.", file=sys.stderr)
        return 1

    importer = MT5DataImporter()
    date_to = datetime.now()
    date_from = date_to - timedelta(days=args.days)

    print(f"Connecting to local MT5 terminal for {args.symbol}...")
    result = importer.import_from_mt5_terminal(
        mt5_path=args.mt5_path,
        symbol=args.symbol,
        date_from=date_from,
        date_to=date_to,
    )

    temp_files: list[str] = []
    try:
        if not args.skip_market:
            market_csv = write_temp_csv(result["market_data"], "market_data")
            temp_files.append(market_csv)
            market_result = upload_file(
                args.api_url, "/api/import/market-data", market_csv, args.symbol
            )
            print(
                f"Market data uploaded: {market_result.get('records_imported', 0)} rows"
            )

        if not args.skip_trades and len(result["trades"]) > 0:
            trades_csv = write_temp_csv(result["trades"], "trades")
            temp_files.append(trades_csv)
            trades_result = upload_file(
                args.api_url, "/api/import/trades", trades_csv, args.symbol
            )
            print(
                f"Trade history uploaded: {trades_result.get('records_imported', 0)} trades"
            )
        elif not args.skip_trades:
            print("No trades returned by MT5 for the selected period.")

    finally:
        importer.disconnect()
        for temp_file in temp_files:
            if os.path.exists(temp_file):
                os.remove(temp_file)

    print("Sync completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
