##


# BTC Volume-Spike Momentum Trading Strategy

A rule-based Bitcoin algorithmic trading strategy that combines **volume-spike detection, candle-direction momentum, ATR-based trailing stops, reversal logic, and systematic backtesting**.

The project was developed to investigate whether unusually high trading volume combined with directional price movement can be used to generate systematic BTC/USD trading signals.

> **Note:** This is a historical backtesting project for educational and research purposes. The reported results do not imply future profitability or suitability for live trading.

---

## Table of Contents

- [Overview](#overview)
- [Strategy](#strategy)
- [How It Works](#how-it-works)
  - [1. Volume Spike Detection](#1-volume-spike-detection)
  - [2. Candle Direction](#2-candle-direction)
  - [3. Position State Machine](#3-position-state-machine)
  - [4. ATR-Based Trailing Stop](#4-atr-based-trailing-stop)
  - [5. Three-Candle Adverse Exit](#5-three-candle-adverse-exit)
  - [6. Position Reversal](#6-position-reversal)
- [Signal Definitions](#signal-definitions)
- [System Architecture](#system-architecture)
- [Backtesting](#backtesting)
- [Lookahead-Bias Validation](#lookahead-bias-validation)
- [Results](#results)
- [Performance Analysis](#performance-analysis)
- [Visualization](#visualization)
- [Project Structure](#project-structure)
- [Requirements](#requirements)
- [Installation](#installation)
- [Usage](#usage)
- [Output](#output)
- [Limitations](#limitations)
- [Future Improvements](#future-improvements)
- [Disclaimer](#disclaimer)

---

# Overview

This project implements a systematic BTC trading strategy using historical daily OHLCV data.

The strategy attempts to exploit the following market hypothesis:

> **An unusually large increase in trading volume, combined with a directional candle, may indicate strong short-term momentum in that direction.**

The strategy therefore uses:

- Historical OHLCV data
- Volume statistics
- Candle direction
- 14-period Average True Range (ATR)
- 2× ATR trailing stops
- Three-candle adverse-movement exits
- Long/short position states
- Position reversal logic
- Transaction-cost-aware backtesting
- Performance statistics
- Lookahead-bias validation
- Interactive PnL visualization

The system processes historical BTC data, generates trading signals, passes those signals to the backtesting engine, and evaluates the resulting trades.

---

# Strategy

The strategy can be summarized as:
"
             BTC OHLCV DATA
                    |
                    v
          Calculate 14-period ATR
                    |
                    v
          Detect Volume Spike
                    |
                    v
          Check Candle Direction
              /             \
        Bullish              Bearish
           |                    |
           v                    v
         LONG                 SHORT
           |                    |
           +---------+----------+
                     |
                     v
             Manage Position
                     |
          +----------+----------+
          |          |          |
       ATR Stop   3 Bad      Reversal
                  Candles
          |          |          |
          +----------+----------+
                     |
                     v
                   EXIT "
