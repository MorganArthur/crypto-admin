#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
合约回测引擎，支持杠杆交易
用法示例:
    from futures_backtest_engine import FuturesBacktestEngine, create_strategy
    engine = FuturesBacktestEngine("data/BTC_USDT_ohlcv_1h.csv", start_date="2024-01-01", leverage=10)
    strategy = create_strategy("sma_cross", short_period=10, long_period=30)
    result = engine.run(strategy)
"""

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any

import pandas as pd
import numpy as np

# 导入现货回测引擎中的基类
from backtest_engine import BaseStrategy, Signal, Trade, BacktestResult, COLUMN_MAP


class FuturesBacktestEngine:
    def __init__(
        self,
        data_path: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        initial_capital: float = 10000.0,
        commission_rate: float = 0.001,
        leverage: int = 10,
    ):
        self.data_path = data_path
        self.start_date = start_date
        self.end_date = end_date
        self.initial_capital = initial_capital
        self.commission_rate = commission_rate
        self.leverage = leverage
        self.df: Optional[pd.DataFrame] = None
        self.time_col: str = "timestamp"

    def load_data(self) -> pd.DataFrame:
        if not os.path.exists(self.data_path):
            raise FileNotFoundError(f"数据文件不存在: {self.data_path}")

        df = pd.read_csv(self.data_path)

        # 映射列名（中文 -> 英文）
        mapped_columns = {}
        for c in df.columns:
            c_clean = c.lower().strip()
            mapped_columns[c] = COLUMN_MAP.get(c_clean, c_clean)
        df = df.rename(columns=mapped_columns)

        # 优先使用人类可读的日期字符串列，其次才是 timestamp
        time_col = None
        for candidate in ("datetime", "date", "time", "timestamp"):
            if candidate in df.columns:
                time_col = candidate
                break

        if time_col:
            if time_col == "timestamp":
                # 毫秒时间戳需要指定 unit='ms'
                df[time_col] = pd.to_datetime(df[time_col], unit="ms")
            else:
                df[time_col] = pd.to_datetime(df[time_col])
            df = df.sort_values(by=time_col).reset_index(drop=True)
        else:
            time_col = "index"
            df[time_col] = pd.to_datetime(df.index)

        if self.start_date:
            start_dt = pd.to_datetime(self.start_date)
            df = df[df[time_col] >= start_dt]
        if self.end_date:
            end_dt = pd.to_datetime(self.end_date)
            df = df[df[time_col] <= end_dt]

        if len(df) == 0:
            raise ValueError("过滤后数据为空，请检查时间范围")

        self.df = df
        self.time_col = time_col
        return df

    def run(self, strategy: BaseStrategy) -> BacktestResult:
        if self.df is None:
            self.load_data()

        strategy.init(self.df)

        capital = self.initial_capital
        position = 0.0  # 正数表示多头，负数表示空头
        equity = capital
        trades: List[Trade] = []
        equity_curve: List[Dict] = []
        current_trade: Optional[Trade] = None

        for i in range(len(self.df)):
            row = self.df.iloc[i]
            signal = strategy.next(i)
            price = float(row["close"])
            time_val = row[self.time_col]

            if isinstance(time_val, pd.Timestamp):
                time_str = time_val.strftime("%Y-%m-%d %H:%M:%S")
            else:
                time_str = str(time_val)

            # 计算最大可开仓数量（考虑杠杆）
            max_position_value = capital * self.leverage
            max_position_size = max_position_value / price if price > 0 else 0

            if signal == Signal.BUY and position <= 0:
                # 平空仓并开多仓
                if position < 0:
                    # 平空仓
                    buy_cost = abs(position) * price * (1 + self.commission_rate)
                    pnl = (abs(position) * price) - (abs(position) * current_trade.entry_price) if current_trade else 0
                    if current_trade:
                        current_trade.exit_time = time_str
                        current_trade.exit_price = price
                        current_trade.pnl = pnl
                        current_trade.pnl_pct = (pnl / (abs(current_trade.entry_price) * abs(current_trade.pnl))) * 100 if current_trade.pnl != 0 else 0
                        trades.append(current_trade)
                    
                    capital += pnl
                    position = 0
                    current_trade = None
                
                # 开多仓
                cost = min(capital * (1 - self.commission_rate), max_position_value)
                new_position = cost / price
                position = new_position
                capital -= cost
                current_trade = Trade(
                    entry_time=time_str,
                    entry_price=price,
                    direction="long",
                )

            elif signal == Signal.SELL and position >= 0:
                # 平多仓并开空仓
                if position > 0:
                    # 平多仓
                    sell_value = position * price * (1 - self.commission_rate)
                    if current_trade:
                        entry_cost = current_trade.entry_price * position
                        current_trade.exit_time = time_str
                        current_trade.exit_price = price
                        current_trade.pnl = sell_value - entry_cost
                        current_trade.pnl_pct = (current_trade.pnl / entry_cost) * 100
                        trades.append(current_trade)
                    
                    capital += sell_value
                    position = 0
                    current_trade = None
                
                # 开空仓
                cost = min(capital * (1 - self.commission_rate), max_position_value)
                new_position = -(cost / price)
                position = new_position
                capital -= cost
                current_trade = Trade(
                    entry_time=time_str,
                    entry_price=price,
                    direction="short",
                )

            # 计算当前权益（包含未实现盈亏）
            unrealized_pnl = position * price if position != 0 else 0
            equity = capital + unrealized_pnl
            
            equity_curve.append({
                "time": time_str,
                "equity": round(equity, 2),
                "price": round(price, 2),
            })

        # 结束时平仓
        if position != 0 and current_trade:
            last_row = self.df.iloc[-1]
            last_price = float(last_row["close"])
            last_time = last_row[self.time_col]
            if isinstance(last_time, pd.Timestamp):
                last_time_str = last_time.strftime("%Y-%m-%d %H:%M:%S")
            else:
                last_time_str = str(last_time)

            if position > 0:
                # 平多仓
                sell_value = position * last_price * (1 - self.commission_rate)
                entry_cost = current_trade.entry_price * position
                current_trade.exit_time = last_time_str
                current_trade.exit_price = last_price
                current_trade.pnl = sell_value - entry_cost
                current_trade.pnl_pct = (current_trade.pnl / entry_cost) * 100
                trades.append(current_trade)
                equity = sell_value
            else:
                # 平空仓
                buy_cost = abs(position) * last_price * (1 + self.commission_rate)
                entry_cost = abs(current_trade.entry_price) * abs(position)
                current_trade.exit_time = last_time_str
                current_trade.exit_price = last_price
                current_trade.pnl = entry_cost - buy_cost
                current_trade.pnl_pct = (current_trade.pnl / entry_cost) * 100
                trades.append(current_trade)
                equity = capital + (entry_cost - buy_cost)

        summary = self._calc_summary(equity, equity_curve, trades)

        return BacktestResult(
            summary=summary,
            equity_curve=equity_curve,
            trades=trades,
        )

    def _calc_summary(self, final_equity: float, equity_curve: List[Dict], trades: List[Trade]) -> Dict:
        total_return = (final_equity - self.initial_capital) / self.initial_capital * 100
        total_days = self._calc_total_days()
        annual_return = total_return * (365 / total_days) if total_days > 0 else 0
        max_drawdown = self._calc_max_drawdown(equity_curve)

        win_trades = [t for t in trades if t.pnl > 0]
        lose_trades = [t for t in trades if t.pnl <= 0]
        win_rate = len(win_trades) / len(trades) * 100 if trades else 0

        avg_win = sum(t.pnl for t in win_trades) / len(win_trades) if win_trades else 0
        avg_loss = abs(sum(t.pnl for t in lose_trades) / len(lose_trades)) if lose_trades else 0
        profit_factor = avg_win / avg_loss if avg_loss > 0 else 0

        # 夏普比率（简化版）
        returns = []
        for i in range(1, len(equity_curve)):
            prev = equity_curve[i - 1]["equity"]
            curr = equity_curve[i]["equity"]
            if prev > 0:
                returns.append((curr - prev) / prev)
        sharpe = 0.0
        if len(returns) > 1:
            ret_mean = np.mean(returns)
            ret_std = np.std(returns)
            if ret_std > 0:
                # 假设小时数据，年化系数 sqrt(365 * 24)
                sharpe = (ret_mean / ret_std) * np.sqrt(365 * 24)

        return {
            "initial_capital": self.initial_capital,
            "final_equity": round(final_equity, 2),
            "total_return_pct": round(total_return, 2),
            "annual_return_pct": round(annual_return, 2),
            "max_drawdown_pct": round(max_drawdown, 2),
            "total_trades": len(trades),
            "win_trades": len(win_trades),
            "lose_trades": len(lose_trades),
            "win_rate_pct": round(win_rate, 2),
            "profit_factor": round(profit_factor, 2),
            "sharpe_ratio": round(sharpe, 2),
        }

    def _calc_total_days(self) -> float:
        if self.df is None or len(self.df) == 0:
            return 0
        start = pd.to_datetime(self.df[self.time_col].iloc[0])
        end = pd.to_datetime(self.df[self.time_col].iloc[-1])
        return max((end - start).total_seconds() / 86400, 1)

    @staticmethod
    def _calc_max_drawdown(equity_curve: List[Dict]) -> float:
        peak = 0
        max_dd = 0
        for point in equity_curve:
            eq = point["equity"]
            if eq > peak:
                peak = eq
            dd = (peak - eq) / peak * 100 if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd
        return max_dd