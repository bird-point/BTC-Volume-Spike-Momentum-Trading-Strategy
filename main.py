# BTC-Volume-Spike-Momentum-Trading-Strategy


from pathlib import Path
import pandas as pd
import numpy as np
try:
    import talib as tb
    TALIB_AVAILABLE = True
except ImportError:
    TALIB_AVAILABLE = False

from backtester import BackTester
BASE_DIR = Path(__file__).resolve().parent
DATASET_CANDIDATES = [
    "btc_18_22_1d.csv",
    "BTC_2019_2023_1d.csv",
    "BTC_2019_2023_1d.csv.csv",
]


OUTPUT_FILE = BASE_DIR / "final_data.csv"

def find_dataset():

    for filename in DATASET_CANDIDATES:
        candidate = BASE_DIR / filename

        if candidate.exists():
            return candidate
    btc_csvs = list(BASE_DIR.glob("*btc*.csv")) + list(BASE_DIR.glob("*BTC*.csv"))

    if len(btc_csvs) == 1:
        return btc_csvs[0]

    if len(btc_csvs) > 1:
        print("Multiple BTC CSV files found:")
        for file in btc_csvs:
            print(f"  - {file.name}")
        for filename in DATASET_CANDIDATES:
            candidate = BASE_DIR / filename
            if candidate.exists():
                return candidate

        return btc_csvs[0]

    raise FileNotFoundError(
        "\nCould not find the BTC dataset.\n"
        f"Python is looking in:\n{BASE_DIR}\n\n"
        "Put your CSV file in the same folder as main.py.\n"
        "Expected filenames include:\n"
        "  - btc_18_22_1d.csv\n"
        "  - BTC_2019_2023_1d.csv\n"
    )
def calculate_atr(data, period=14):
    if TALIB_AVAILABLE:
        return tb.ATR(
            data["high"].astype(float),
            data["low"].astype(float),
            data["close"].astype(float),
            timeperiod=period
        )
    high = data["high"].astype(float)
    low = data["low"].astype(float)
    close = data["close"].astype(float)

    previous_close = close.shift(1)

    true_range = pd.concat(
        [
            high - low,
            (high - previous_close).abs(),
            (low - previous_close).abs()
        ],
        axis=1
    ).max(axis=1)
    atr = true_range.ewm(
        alpha=1 / period,
        adjust=False,
        min_periods=period
    ).mean()

    return atr

def process_data(data):
    required_columns = [
        "open",
        "high",
        "low",
        "close",
        "volume"
    ]

    missing_columns = [
        col for col in required_columns
        if col not in data.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Dataset is missing required columns: {missing_columns}\n"
            f"Available columns: {list(data.columns)}"
        )
    for col in required_columns:
        data[col] = pd.to_numeric(data[col], errors="coerce")
    data["ATR"] = calculate_atr(data, period=14)

    return data

def strat(data):
    data["trade_type"] = "HOLD"
    data["signals"] = 0
    position = 0
    num_wrong = 0
    trailing_stop = 0.0
    trailing_stop_multiplier = 2
    for i in range(14, len(data)):
        recent_volume = data.loc[i - 5:i, "volume"]

        volume_mean = np.mean(recent_volume)
        volume_std = np.std(recent_volume)

        vol_spike = volume_mean + 1.5 * volume_std
        if position == 0:
            if data.loc[i, "volume"] > vol_spike:
                if data.loc[i, "close"] > data.loc[i, "open"]:
                    data.loc[i, "signals"] = 1
                    position = 1
                    data.loc[i, "trade_type"] = "LONG"
                    trailing_stop = (
                        data.loc[i, "close"]
                        - data.iloc[i]["ATR"] * trailing_stop_multiplier
                    )

                elif data.loc[i, "close"] < data.loc[i, "open"]:
                    data.loc[i, "signals"] = -1
                    position = -1
                    data.loc[i, "trade_type"] = "SHORT"
                    trailing_stop = (
                        data.loc[i, "close"]
                        + data.iloc[i]["ATR"] * trailing_stop_multiplier
                    )

        elif position == 1:
            trend_rev = (
                data.loc[i, "volume"] >= vol_spike
                and data.loc[i, "close"] < data.loc[i, "open"]
            )

            if data.loc[i, "close"] <= data.loc[i - 1, "close"]:
                num_wrong += 1
            else:
                num_wrong = 0

            if trend_rev:

                data.loc[i, "signals"] = -2

                position = -1

                trailing_stop = (
                    data.loc[i, "close"]
                    + data.iloc[i]["ATR"] * trailing_stop_multiplier
                )

                num_wrong = 0

                data.loc[i, "trade_type"] = "REVERSE_LONG_TO_SHORT"

            elif num_wrong == 3:

                data.loc[i, "signals"] = -1

                position = 0

                num_wrong = 0

                data.loc[i, "trade_type"] = "CLOSE"
            else:

                if data.iloc[i]["close"] < trailing_stop:

                    data.loc[i, "signals"] = -1

                    position = 0

                    data.loc[i, "trade_type"] = "CLOSE"

                else:
                    new_stop = (
                        data.iloc[i]["close"]
                        - data.iloc[i]["ATR"] * trailing_stop_multiplier
                    )

                    trailing_stop = max(
                        trailing_stop,
                        new_stop
                    )

        elif position == -1:

            trend_rev = (
                data.loc[i, "volume"] >= vol_spike
                and data.loc[i, "close"] > data.loc[i, "open"]
            )

            if data.loc[i, "close"] >= data.loc[i - 1, "close"]:
                num_wrong += 1
            else:
                num_wrong = 0

            if trend_rev:

                data.loc[i, "signals"] = 2

                position = 1

                trailing_stop = (
                    data.loc[i, "close"]
                    - data.iloc[i]["ATR"] * trailing_stop_multiplier
                )

                num_wrong = 0

                data.loc[i, "trade_type"] = "REVERSE_SHORT_TO_LONG"

            elif num_wrong == 3:

                data.loc[i, "signals"] = 1

                position = 0

                num_wrong = 0

                data.loc[i, "trade_type"] = "CLOSE"

            else:

                if data.iloc[i]["close"] > trailing_stop:

                    data.loc[i, "signals"] = 1

                    position = 0

                    data.loc[i, "trade_type"] = "CLOSE"

                else:
                    new_stop = (
                        data.iloc[i]["close"]
                        + data.iloc[i]["ATR"] * trailing_stop_multiplier
                    )

                    trailing_stop = min(
                        trailing_stop,
                        new_stop
                    )

    return data

def main():

    dataset_path = find_dataset()

    print("=" * 60)
    print("BTC TRADING STRATEGY BACKTEST")
    print("=" * 60)

    print(f"\nScript directory : {BASE_DIR}")
    print(f"Dataset          : {dataset_path.name}")
    print(f"TA-Lib available : {TALIB_AVAILABLE}")

    data = pd.read_csv(dataset_path)

    print(f"Rows loaded      : {len(data)}")
    print(f"Columns           : {list(data.columns)}")
    processed_data = process_data(data)

    result_data = strat(processed_data)

    result_data.to_csv(
        OUTPUT_FILE,
        index=False
    )

    print(f"\nStrategy data saved to:")
    print(OUTPUT_FILE)

    bt = BackTester(
        "BTC",
        signal_data_path=str(OUTPUT_FILE),
        master_file_path=str(OUTPUT_FILE),
        compound_flag=1
    )

    
    bt.get_trades(1000)

    print("\n" + "=" * 60)
    print("TRADES")
    print("=" * 60)

    if len(bt.trades) == 0:

        print("No completed trades were generated.")

    else:

        for trade in bt.trades:

            print(trade)
            print(f"PnL: {trade.pnl():.2f}")
            print("-" * 60)
    print("\n" + "=" * 60)
    print("PERFORMANCE STATISTICS")
    print("=" * 60)

    stats = bt.get_statistics()

    if stats is None:

        print("No statistics available because no trades were completed.")

    else:

        for key, val in stats.items():
            print(f"{key}: {val}")

    print("\n" + "=" * 60)
    print("LOOKAHEAD BIAS CHECK")
    print("=" * 60)

    lookahead_bias = False
    signals_checked = 0

    for i in range(len(result_data)):
        if result_data.loc[i, "signals"] != 0:

            signals_checked += 1

            temp_data = data.iloc[:i + 1].copy()
            temp_data = process_data(temp_data)
            temp_data = strat(temp_data)

            original_signal = result_data.loc[i, "signals"]
            recalculated_signal = temp_data.loc[i, "signals"]

            if recalculated_signal != original_signal:

                print(
                    f"LOOKAHEAD BIAS DETECTED "
                    f"at index {i}: "
                    f"original={original_signal}, "
                    f"recalculated={recalculated_signal}"
                )

                lookahead_bias = True

    print(f"Signals checked: {signals_checked}")

    if lookahead_bias:

        print("RESULT: LOOKAHEAD BIAS DETECTED")

    else:

        print("RESULT: NO LOOKAHEAD BIAS DETECTED")

    print("\nGenerating PnL graph...")

    bt.make_pnl_graph()

if __name__ == "__main__":
    main()
