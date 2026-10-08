####

import numpy as np
import pandas as pd
from enum import Enum
import sys
from pathlib import Path
from datetime import timedelta
import matplotlib.pyplot as plt
import math
import plotly.graph_objects as go
from plotly.subplots import make_subplots
transaction_fee = 0.0015

sign = lambda x: int(x > 0) - int(x < 0)

class TradeType(Enum):

    LONG = 1

    SHORT = -1

    def __str__(self):

        return "LONG" if self == TradeType.LONG else "SHORT"

class TradePair:

    def __init__(self, symbol, qty, init_price, final_price, init_timestamp, final_timestamp):

        self.symbol = symbol

        self.qty = qty

        self.init_price = init_price

        self.final_price = final_price

        self.init_timestamp = init_timestamp

        self.final_timestamp = final_timestamp



    def __str__(self):

        return f"TRADED {self.symbol} {self.trade_type()} ${self.qty} @{self.init_price} to {self.final_price} in {self.init_timestamp} - {self.final_timestamp}"



    def trade_type(self):

        return TradeType.LONG if self.qty > 0 else TradeType.SHORT



    def pnl(self):

        return self.qty * (self.final_price - self.init_price) / self.init_price - transaction_fee * abs(self.qty)

        # return ""



    def is_win(self):

        return self.pnl() > 0



    def holding_time(self):

        return self.final_timestamp - self.init_timestamp



    def drawdown(self):

        peak_price = max(self.init_price, self.final_price)

        lowest_price = min(self.init_price, self.final_price)

        return (peak_price - lowest_price) / peak_price * 100



class Position:

    def __init__(self, symbol, qty, price, timestamp):

        self.symbol = symbol

        self.qty = qty

        self.price = price

        self.timestamp = timestamp



    def is_valid(self, signal):

        if self.qty == 0:

            return abs(signal) <= 1

        else:

            return sign(self.qty) * sign(signal) <= 0



    def open(self, price, qty, timestamp):

        self.qty = qty

        self.price = price

        self.timestamp = timestamp



    def close(self, price, timestamp):

        trade = TradePair(self.symbol, self.qty, self.price, price, self.timestamp, timestamp)



        self.qty = 0

        self.price = None

        self.timestamp = None



        return trade    



class BackTester:

    def __init__(self, symbol, signal_data_path, master_file_path = None, compound_flag = 0):



        self.compound_flag = compound_flag

        self.symbol = symbol



        self.data = self.preprocess_csv(signal_data_path)



        if "TP" not in self.data.columns:

            self.data["TP"] = 0

        if "SL" not in self.data.columns:

            self.data["SL"] = 0



        master_file_path = master_file_path if master_file_path else signal_data_path

        self.master_data = self.preprocess_csv(master_file_path)



        self.trades = []

        self.position = Position(symbol, 0, None, None)



        self.tp = 0

        self.sl = 0



    def preprocess_csv(self, file_path):

        data = pd.read_csv(file_path, header=0)

        data['datetime'] = pd.to_datetime(data['datetime'])

        data["nextdatetime"] = data["datetime"] + pd.Timedelta(minutes=1)

        data.set_index("datetime", inplace=True)

        return data



    def check_tp_sl(self, timestamp, next_timestamp):



        if self.position.qty == 0:

            return None



        if self.tp == 0 and self.sl == 0:

            return None



        trade = None



        for index, row in self.master_data.loc[timestamp : next_timestamp].iterrows():

            if self.position.qty > 0:

                if row["high"] >= self.tp and self.tp != 0:

                    trade = self.position.close(self.tp, row["nextdatetime"])

                    print("Triggered TP for long", file = sys.stderr)

                    break

                elif row["low"] <= self.sl and self.sl != 0:

                    trade = self.position.close(self.sl, row["nextdatetime"])

                    print("Triggered SL for long", file = sys.stderr)

                    break

            elif self.position.qty < 0:

                if row["low"] <= self.tp and self.tp != 0:

                    trade = self.position.close(self.tp, row["nextdatetime"])

                    print("Triggered TP for short", file = sys.stderr)

                    break

                elif row["high"] >= self.sl and self.sl != 0:

                    trade = self.position.close(self.sl, row["nextdatetime"])

                    print("Triggered SL for short", file = sys.stderr)

                    break



        return trade



    def get_trades(self, trade_amt):



        for index, row in self.data.iterrows():

            signal = row["signals"]

            closing_time = row["nextdatetime"]



            if not self.position.is_valid(signal):

                raise ValueError(f"Invalid signal {signal} for current position {sign(self.position.qty)} at {index}")



            trade = self.check_tp_sl(index, closing_time)



            if trade:

                self.trades.append(trade)

                trade_amt = (trade_amt + trade.pnl()) if self.compound_flag else trade_amt

                continue



            self.tp = row["TP"] if row["TP"] != 0 else self.tp

            self.sl = row["SL"] if row["SL"] != 0 else self.sl



            if row["TP"] == 0 and row["SL"] == 0:

                self.tp = self.sl = 0



            if signal == 0:

                continue

            elif signal == 1 or signal == -1:

                if self.position.qty == 0:

                    self.position.open(row["close"], sign(signal)*trade_amt, closing_time)

                else:

                    trade = self.position.close(row["close"], closing_time)

                    self.trades.append(trade)

                    trade_amt = (trade_amt + trade.pnl()) if self.compound_flag else trade_amt

            elif signal == 2 or signal == -2:

                trade = self.position.close(row["close"], closing_time)

                self.trades.append(trade)

                trade_amt = (trade_amt + trade.pnl()) if self.compound_flag else trade_amt

                self.position.open(row["close"], sign(signal)*trade_amt, closing_time)

            else:

                raise ValueError(f"Invalid signal {signal} at {index}")



    def get_statistics(self):

        total_trades = len(self.trades)

        if total_trades==0:

            return None

        winning_trades = [t for t in self.trades if t.is_win()]

        losing_trades = [t for t in self.trades if not t.is_win()]

        long_trades = [t for t in self.trades if t.trade_type() == TradeType.LONG]

        short_trades = [t for t in self.trades if t.trade_type() == TradeType.SHORT]



        gross_profit = sum(t.pnl() for t in winning_trades)

        gross_loss = sum(t.pnl() for t in losing_trades)

        net_profit = gross_profit + gross_loss

        transaction_costs = sum(transaction_fee * abs(t.qty) for t in self.trades)



        max_holding_time = max(t.holding_time() for t in self.trades)

        avg_holding_time = sum((t.holding_time() for t in self.trades), timedelta()) / total_trades



        largest_win = max(t.pnl() for t in winning_trades) if winning_trades else 0

        largest_loss = min(t.pnl() for t in losing_trades) if losing_trades else 0

        average_win = gross_profit / len(winning_trades) if winning_trades else 0

        average_loss = gross_loss / len(losing_trades) if losing_trades else 0



        winning_streak, losing_streak = self.get_streaks()



        max_drawdown, avg_drawdown = self.get_drawdown(np.array([t.pnl() for t in self.trades]))



        sharpe_ratio = self.get_sharpe_ratio()

        stats = {

            "static" : {

                'Total Trades': total_trades,

                'Leverage Applied': 1,

                'Winning Trades': len(winning_trades),

                'Losing Trades': len(losing_trades),

                'No. of Long Trades': len(long_trades),

                'No. of Short Trades': len(short_trades),

                'Benchmark Return(%)': self.get_benchmark_return() * 100,

                'Benchmark Return(on $1000)': self.get_benchmark_return() * 1000,

                'Win Rate': len(winning_trades) / total_trades * 100 if total_trades > 0 else 0,

                'Winning Streak': winning_streak,

                'Losing Streak': losing_streak,

                'Gross Profit': gross_profit,
                'Gross Loss': gross_loss,
                'Transaction Costs': transaction_costs,
                'Net Profit': net_profit,

                'Average Profit': net_profit / total_trades if total_trades > 0 else 0,

                'Maximum Drawdown(%)': max_drawdown,

                'Average Drawdown(%)': avg_drawdown,

                'Largest Win': largest_win,

                'Average Win': average_win,

                'Largest Loss': largest_loss,

                'Average Loss': average_loss,

                'Maximum Holding Time': max_holding_time,

                'Average Holding Time': avg_holding_time,

                'Maximum Adverse Excursion': None,

                'Average Adverse Excursion': None,

                'Sharpe Ratio': sharpe_ratio,

                'Sortino Ratio': None,

            },

            "compound" : {

                'Trades Executed': total_trades,

                'Total Profit': net_profit

            }

        }



        return stats["static"]



    def get_benchmark_return(self):

        """Calculate benchmark return from the stock data."""

        initial_price = self.data.iloc[0]["close"]

        final_price = self.data.iloc[-1]["close"]

        return (final_price - initial_price) / initial_price



    def get_streaks(self):

        """Calculate winning and losing streaks."""

        max_win_streak = max_loss_streak = 0

        current_win_streak = current_loss_streak = 0



        for t in self.trades:

            if t.is_win():

                current_win_streak += 1

                max_win_streak = max(max_win_streak, current_win_streak)

                current_loss_streak = 0

            else:

                current_loss_streak += 1

                max_loss_streak = max(max_loss_streak, current_loss_streak)

                current_win_streak = 0



        return max_win_streak, max_loss_streak



    def get_drawdown(self, pnl_array):

        """Calculate the maximum and avg drawdown for the portfolio.

        Pass pnl_array as np.array of trade PnLs."""



        cum_pnl_series = 1000 + pnl_array.cumsum()

        cumulative_max = pd.Series(cum_pnl_series).cummax()



        max_drawdown = np.min((cum_pnl_series - cumulative_max) / cumulative_max)

        avg_drawdown = np.mean((cum_pnl_series - cumulative_max) / cumulative_max)



        return abs(max_drawdown)*100, abs(avg_drawdown)*100



    def plot_drawdown(self):

        pnl_array = np.array([t.pnl() for t in self.trades])

        cum_pnl_series = 1000 + pnl_array.cumsum()

        cumulative_max = pd.Series(cum_pnl_series).cummax()



        drawdowns = (cum_pnl_series - cumulative_max) / cumulative_max

        drawdowns = drawdowns * 100



        times = [t.final_timestamp for t in self.trades]



        plt.figure(figsize=(12, 6))

        plt.plot(np.array(times), np.array(drawdowns), label="Drawdown", color="red")

        plt.title("Drawdown Over Time")

        plt.xlabel("Time")

        plt.ylabel("Drawdown (%)")

        plt.legend(loc="best")

        plt.show()



    def get_sharpe_ratio(self, risk_free_rate=0.0):

        """

        Calculate the annualised Sharpe Ratio using daily portfolio returns.



        Method:

        1. Build the intraday capital curve via calc_capital() (reuses existing logic).

        2. Resample to daily frequency, taking the last capital value of each day.

        3. Compute daily % returns: r_t = (C_t - C_{t-1}) / C_{t-1}

        4. Subtract the *daily* risk-free rate and annualise by sqrt(365).



        This satisfies all three requirements:

        - Time-normalised (daily) returns, not per-trade returns.

        - Returns expressed as ΔCapital / Capital, i.e. true portfolio returns.

        - Annualisation by sqrt(365) is valid because the sampling period is 1 day.

        """

        self.calc_capital()

        daily_capital = self.data["capital"].resample("1D").last().dropna()



        if len(daily_capital) < 2:

            return 0



        daily_returns = daily_capital.pct_change().dropna()

        daily_rf = (1 + risk_free_rate) ** (1 / 365) - 1



        excess_returns = daily_returns - daily_rf

        mean_excess = excess_returns.mean()

        std_excess = excess_returns.std()



        if std_excess == 0:

            return 0



        return mean_excess / std_excess * math.sqrt(365)



    def get_sortino_ratio(self, risk_free_rate=0.0):

        """Calculate the Sortino Ratio."""

        returns = [t.pnl() for t in self.trades]

        mean_return = np.mean(returns)

        downside_risk = np.std([r for r in returns if r < 0])



        return (mean_return - risk_free_rate) / downside_risk if downside_risk > 0 else 0



    def calc_pnl(self):

        if "pnl" in self.data.columns:

            return



        pnls = []



        curr_trade_idx = 0

        is_trade_open = False



        prev_row = None



        for index, row in self.data.iterrows():        

            if curr_trade_idx < len(self.trades):

                curr_trade = self.trades[curr_trade_idx]

                if curr_trade.final_timestamp <= index and is_trade_open:

                    is_trade_open = False

                    pnl = -transaction_fee * abs(curr_trade.qty)

                    curr_trade_idx += 1

                elif curr_trade.init_timestamp <= index:

                    is_trade_open = True

                    pnl = curr_trade.qty * (row["close"] - prev_row["close"]) / curr_trade.init_price

                else:

                    pnl = 0

            else:

                pnl = 0



            pnls.append(pnl)

            prev_row = row



        self.data["pnl"] = pnls



    def calc_capital(self):

        if "capital" not in self.data.columns:

            self.calc_pnl()

            self.data["capital"] = 1000 + self.data["pnl"].cumsum()



    def get_granular_sharpe_ratio(self, period="1D"):

        """

        Calculate the Sharpe Ratio for the portfolio by dividing into periods.

        period: str, a pandas frequency string (e.g., '1D', '6H', '30T', etc.)

        """



        self.calc_capital()

        offset = pd.to_timedelta(period)

        capitals = self.data["capital"]

        time_index = self.data.index

        pnls = []

        last_time = time_index[0]

        last_capital = capitals.iloc[0]

        for i in range(1, len(time_index)):

            current_time = time_index[i]



            if current_time - last_time >= offset:

                pnls.append(capitals.iloc[i] - last_capital)

                last_time = current_time

                last_capital = capitals.iloc[i]



        pnls = np.array(pnls)

        granular_sharpe = np.mean(pnls) / np.std(pnls) if len(pnls) > 0 else np.nan



        return granular_sharpe*np.sqrt(252)



    def get_granular_sharpe_ratio_window(self, window_size="6ME", period="1D"):

        """

        Calculate the Sharpe Ratio for the portfolio by dividing self.data into windows of a specified size.

        For each window, compute the Sharpe Ratio over periods.



        Args:

            window_size (str): Size of each window (e.g., '6M', '1Y', etc.).

            period (str): Frequency for PnL calculations within each window (e.g., '1D', '1H', etc.).



        Returns:

            list: A list of Sharpe Ratios for each window.

        """



        self.calc_capital()

        data_windows = [

            window for _, window in self.data.resample(window_size)

            if not window.empty

        ]

        sharpe_ratios = []

        for window_data in data_windows:

            offset = pd.to_timedelta(period)

            capitals = window_data["capital"]

            time_index = window_data.index

            pnls = []

            last_time = time_index[0]

            last_capital = capitals.iloc[0]

            for i in range(1, len(time_index)):

                current_time = time_index[i]



                if current_time - last_time >= offset:

                    pnls.append(capitals.iloc[i] - last_capital)

                    last_time = current_time

                    last_capital = capitals.iloc[i]

            pnls = np.array(pnls)

            sharpe_ratio = np.sqrt(252)*np.mean(pnls) / np.std(pnls) if len(pnls) > 0 else np.nan

            sharpe_ratios.append(sharpe_ratio)



        return sharpe_ratios



    def make_pnl_graph(self, output_path=None, auto_open=True):
        """
        Create an interactive Plotly backtest report and save it as a standalone
        HTML file. This avoids Plotly's temporary localhost server, which can
        produce ERR_CONNECTION_REFUSED in Edge/Chrome.
        """
        self.calc_capital()

        if self.data.empty:
            raise ValueError("No data available to plot.")

        # Resolve output path relative to this script unless explicitly supplied.
        if output_path is None:
            output_path = Path(__file__).resolve().parent / "pnl_graph.html"
        else:
            output_path = Path(output_path).expanduser().resolve()

        output_path.parent.mkdir(parents=True, exist_ok=True)

        pct_change = (
            (self.data["close"] / self.data["open"] - 1) * 100
        ).round(2).fillna(0)

        hover_text = pct_change.apply(lambda x: f"Change: {x:+.2f}%")

        # Two-panel interactive figure:
        #   1. Candlestick price chart with trade regions.
        #   2. Portfolio capital/equity curve.
        fig = make_subplots(
            rows=2,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.08,
            row_heights=[0.70, 0.30],
            subplot_titles=("Price / Trades", "Portfolio Capital")
        )

        fig.add_trace(
            go.Candlestick(
                x=self.data.index,
                open=self.data["open"],
                high=self.data["high"],
                low=self.data["low"],
                close=self.data["close"],
                text=hover_text,
                hovertemplate=(
                    "Time: %{x}<br>"
                    "Open: %{open}<br>"
                    "High: %{high}<br>"
                    "Low: %{low}<br>"
                    "Close: %{close}<br>"
                    "%{text}<extra></extra>"
                ),
                name="BTC"
            ),
            row=1,
            col=1
        )

        # Portfolio capital curve.
        fig.add_trace(
            go.Scatter(
                x=self.data.index,
                y=self.data["capital"],
                mode="lines",
                name="Capital",
                line=dict(width=2),
                hovertemplate=(
                    "Time: %{x}<br>"
                    "Capital: $%{y:,.2f}<extra></extra>"
                )
            ),
            row=2,
            col=1
        )

        # Mark trade entry/exit points.
        long_entries_x, long_entries_y = [], []
        short_entries_x, short_entries_y = [], []
        exits_x, exits_y = [], []

        # Shade each completed trade.
        data_low = self.data["low"].min()
        data_high = self.data["high"].max()

        for trade in self.trades:
            init_idx = self.data.index.get_indexer(
                [trade.init_timestamp], method="nearest"
            )[0]
            final_idx = self.data.index.get_indexer(
                [trade.final_timestamp], method="nearest"
            )[0]

            if not (0 <= init_idx < len(self.data)):
                continue
            if not (0 <= final_idx < len(self.data)):
                continue

            init_time = self.data.index[init_idx]
            final_time = self.data.index[final_idx]

            fill = "rgba(0, 180, 0, 0.08)" if trade.qty > 0 else "rgba(220, 0, 0, 0.08)"

            fig.add_shape(
                type="rect",
                x0=init_time,
                y0=data_low,
                x1=final_time,
                y1=data_high,
                fillcolor=fill,
                line=dict(width=0),
                layer="below",
                row=1,
                col=1
            )

            entry_price = self.data["close"].iloc[init_idx]
            exit_price = self.data["close"].iloc[final_idx]

            if trade.qty > 0:
                long_entries_x.append(init_time)
                long_entries_y.append(entry_price)
            else:
                short_entries_x.append(init_time)
                short_entries_y.append(entry_price)

            exits_x.append(final_time)
            exits_y.append(exit_price)

        if long_entries_x:
            fig.add_trace(
                go.Scatter(
                    x=long_entries_x,
                    y=long_entries_y,
                    mode="markers",
                    marker=dict(symbol="triangle-up", size=10),
                    name="Long Entry",
                    hovertemplate="Long Entry<br>Time: %{x}<br>Price: %{y}<extra></extra>"
                ),
                row=1,
                col=1
            )

        if short_entries_x:
            fig.add_trace(
                go.Scatter(
                    x=short_entries_x,
                    y=short_entries_y,
                    mode="markers",
                    marker=dict(symbol="triangle-down", size=10),
                    name="Short Entry",
                    hovertemplate="Short Entry<br>Time: %{x}<br>Price: %{y}<extra></extra>"
                ),
                row=1,
                col=1
            )

        if exits_x:
            fig.add_trace(
                go.Scatter(
                    x=exits_x,
                    y=exits_y,
                    mode="markers",
                    marker=dict(symbol="x", size=9),
                    name="Exit",
                    hovertemplate="Exit<br>Time: %{x}<br>Price: %{y}<extra></extra>"
                ),
                row=1,
                col=1
            )

        fig.add_hline(
            y=1000,
            line_dash="dash",
            annotation_text="Initial Capital: $1000",
            row=2,
            col=1
        )

        fig.update_layout(
            title=f"{self.symbol} Backtest Report",
            hovermode="x unified",
            dragmode="zoom",
            xaxis=dict(
                rangeslider=dict(visible=True),
                type="date"
            ),
            xaxis2=dict(type="date"),
            yaxis=dict(title="Price"),
            yaxis2=dict(title="Capital ($)"),
            template="plotly_white",
            height=900,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
            margin=dict(l=60, r=30, t=100, b=60)
        )

        # Remove the range slider from the capital panel; it is shared with
        # the upper x-axis.
        fig.update_xaxes(rangeslider_visible=True, row=1, col=1)
        fig.update_xaxes(rangeslider_visible=False, row=2, col=1)

        # Save a fully self-contained HTML file. No localhost server is needed.
        fig.write_html(
            str(output_path),
            include_plotlyjs=True,
            full_html=True,
            auto_open=auto_open
        )

        print(f"PnL graph saved to: {output_path}")
        return output_path



if __name__ == "__main__":
    BASE_DIR = Path(__file__).resolve().parent
    signal_file = BASE_DIR / "final_data.csv"
    master_file = BASE_DIR / "final_data.csv"

    print("=" * 60)
    print("BACKTEST STARTING")
    print("=" * 60)
    print(f"Signal data : {signal_file}")
    print(f"Master data : {master_file}")

    if not signal_file.exists():
        raise FileNotFoundError(
            f"Could not find {signal_file}. "
            "Place final_data.csv in the same folder as backtest.py."
        )

    bt = BackTester(
        "BTC",
        signal_data_path=str(signal_file),
        master_file_path=str(master_file),
        compound_flag=1
    )

    # Initial capital / trade amount = $1000.
    bt.get_trades(1000)

    print(f"Rows processed: {len(bt.data)}")
    print(f"Trades executed: {len(bt.trades)}")
    print()

    stats = bt.get_statistics()

    if stats is None:
        print("No completed trades were generated.")
    else:
        print("=" * 60)
        print("BACKTEST STATISTICS")
        print("=" * 60)

        for key, val in stats.items():
            print(f"{key}: {val}")

    print()
    print("Generating PnL graph...")

    graph_path = bt.make_pnl_graph(
        output_path=BASE_DIR / "pnl_graph.html",
        auto_open=True
    )

    print("=" * 60)
    print("BACKTEST COMPLETE")
    print("=" * 60)
    print(f"Interactive graph: {graph_path}")
