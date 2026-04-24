#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
回测引擎，支持多种策略扩展
用法示例:
    from backtest_engine import BacktestEngine, create_strategy
    engine = BacktestEngine("data/BTC_USDT_ohlcv_1h.csv", start_date="2024-01-01")
    strategy = create_strategy("sma_cross", short_period=10, long_period=30)
    result = engine.run(strategy)
"""

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any

import pandas as pd
import numpy as np


# ===================== 信号定义 =====================

class Signal:
    HOLD = 0
    BUY = 1
    SELL = -1


# ===================== 策略基类 =====================

class BaseStrategy(ABC):
    """
    策略基类，所有策略必须继承此类
    """
    name: str = "base"
    description: str = ""
    params_schema: Dict[str, Any] = {}

    def __init__(self, **kwargs):
        self.params = kwargs
        self.df: Optional[pd.DataFrame] = None

    def init(self, df: pd.DataFrame):
        """初始化，在回测开始前调用"""
        self.df = df.copy()
        self._calculate_indicators()

    @abstractmethod
    def _calculate_indicators(self):
        """计算技术指标"""
        pass

    @abstractmethod
    def next(self, i: int) -> int:
        """
        每一步决策，返回 Signal.BUY / SELL / HOLD
        i: 当前数据索引
        """
        pass


# ===================== 具体策略 =====================

class SmaCrossStrategy(BaseStrategy):
    """
    双均线交叉策略
    短期均线上穿长期均线 → 买入
    短期均线下穿长期均线 → 卖出
    """
    name = "sma_cross"
    description = "双均线交叉策略"
    params_schema = {
        "short_period": {"type": "int", "default": 10, "min": 2, "max": 100, "label": "短期均线周期"},
        "long_period": {"type": "int", "default": 30, "min": 5, "max": 200, "label": "长期均线周期"},
    }

    def _calculate_indicators(self):
        sp = self.params.get("short_period", 10)
        lp = self.params.get("long_period", 30)
        self.df["sma_short"] = self.df["close"].rolling(window=sp).mean()
        self.df["sma_long"] = self.df["close"].rolling(window=lp).mean()

    def next(self, i: int) -> int:
        if i < 1:
            return Signal.HOLD
        short_prev = self.df["sma_short"].iloc[i - 1]
        long_prev = self.df["sma_long"].iloc[i - 1]
        short_curr = self.df["sma_short"].iloc[i]
        long_curr = self.df["sma_long"].iloc[i]

        if pd.isna(short_prev) or pd.isna(long_prev):
            return Signal.HOLD

        # 金叉
        if short_prev <= long_prev and short_curr > long_curr:
            return Signal.BUY
        # 死叉
        if short_prev >= long_prev and short_curr < long_curr:
            return Signal.SELL

        return Signal.HOLD


class RsiStrategy(BaseStrategy):
    """
    RSI 策略
    RSI < 超卖线 → 买入
    RSI > 超买线 → 卖出
    """
    name = "rsi"
    description = "RSI 相对强弱指标策略"
    params_schema = {
        "period": {"type": "int", "default": 14, "min": 2, "max": 50, "label": "RSI周期"},
        "oversold": {"type": "int", "default": 30, "min": 10, "max": 40, "label": "超卖线"},
        "overbought": {"type": "int", "default": 70, "min": 60, "max": 90, "label": "超买线"},
    }

    def _calculate_indicators(self):
        period = self.params.get("period", 14)
        delta = self.df["close"].diff()
        gain = delta.where(delta > 0, 0.0)
        loss = (-delta).where(delta < 0, 0.0)
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        rs = avg_gain / avg_loss
        self.df["rsi"] = 100 - (100 / (1 + rs))

    def next(self, i: int) -> int:
        if i < 1:
            return Signal.HOLD
        rsi_curr = self.df["rsi"].iloc[i]
        rsi_prev = self.df["rsi"].iloc[i - 1]
        if pd.isna(rsi_curr) or pd.isna(rsi_prev):
            return Signal.HOLD

        oversold = self.params.get("oversold", 30)
        overbought = self.params.get("overbought", 70)

        if rsi_prev <= oversold and rsi_curr > oversold:
            return Signal.BUY
        if rsi_prev >= overbought and rsi_curr < overbought:
            return Signal.SELL

        return Signal.HOLD


# ===================== 策略注册中心 =====================

STRATEGY_REGISTRY: Dict[str, type] = {}


def register_strategy(cls: type):
    STRATEGY_REGISTRY[cls.name] = cls
    return cls


register_strategy(SmaCrossStrategy)
register_strategy(RsiStrategy)


def get_strategy_names() -> List[str]:
    return list(STRATEGY_REGISTRY.keys())


def get_strategy_info(name: str) -> Optional[Dict]:
    cls = STRATEGY_REGISTRY.get(name)
    if not cls:
        return None
    return {
        "name": cls.name,
        "description": cls.description,
        "params_schema": cls.params_schema,
    }


def create_strategy(name: str, **params) -> BaseStrategy:
    if name not in STRATEGY_REGISTRY:
        raise ValueError(f"未知策略: {name}，可用策略: {list(STRATEGY_REGISTRY.keys())}")
    return STRATEGY_REGISTRY[name](**params)


# ===================== 回测引擎 =====================

@dataclass
class Trade:
    entry_time: str
    entry_price: float
    exit_time: Optional[str] = None
    exit_price: Optional[float] = None
    direction: str = "long"
    pnl: float = 0.0
    pnl_pct: float = 0.0

    def to_dict(self) -> dict:
        return {
            "entry_time": self.entry_time,
            "entry_price": self.entry_price,
            "exit_time": self.exit_time,
            "exit_price": self.exit_price,
            "direction": self.direction,
            "pnl": round(self.pnl, 4),
            "pnl_pct": round(self.pnl_pct, 4),
        }


@dataclass
class BacktestResult:
    summary: Dict[str, Any] = field(default_factory=dict)
    equity_curve: List[Dict[str, Any]] = field(default_factory=list)
    trades: List[Trade] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "summary": self.summary,
            "equity_curve": self.equity_curve,
            "trades": [t.to_dict() for t in self.trades],
        }


# 中文列名映射（支持 fetch_crypto_data.py 导出的中文 CSV）
COLUMN_MAP = {
    "时间": "datetime",
    "时间戳": "timestamp",
    "timestamp": "timestamp",
    "datetime": "datetime",
    "date": "date",
    "time": "time",
    "开盘价": "open",
    "open": "open",
    "最高价": "high",
    "high": "high",
    "最低价": "low",
    "low": "low",
    "收盘价": "close",
    "close": "close",
    "成交量": "volume",
    "volume": "volume",
}


class BacktestEngine:
    def __init__(
        self,
        data_path: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        initial_capital: float = 10000.0,
        commission_rate: float = 0.001,
    ):
        self.data_path = data_path
        self.start_date = start_date
        self.end_date = end_date
        self.initial_capital = initial_capital
        self.commission_rate = commission_rate
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
        position = 0.0
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

            if signal == Signal.BUY and position == 0:
                cost = capital * (1 - self.commission_rate)
                position = cost / price
                capital = 0
                current_trade = Trade(
                    entry_time=time_str,
                    entry_price=price,
                    direction="long",
                )

            elif signal == Signal.SELL and position > 0:
                sell_value = position * price * (1 - self.commission_rate)
                if current_trade:
                    entry_cost = current_trade.entry_price * position
                    current_trade.exit_time = time_str
                    current_trade.exit_price = price
                    current_trade.pnl = sell_value - entry_cost
                    current_trade.pnl_pct = (current_trade.pnl / entry_cost) * 100
                    trades.append(current_trade)

                capital = sell_value
                position = 0
                current_trade = None

            equity = capital + position * price
            equity_curve.append({
                "time": time_str,
                "equity": round(equity, 2),
                "price": round(price, 2),
            })

        # 结束时平仓
        if position > 0 and current_trade:
            last_row = self.df.iloc[-1]
            last_price = float(last_row["close"])
            last_time = last_row[self.time_col]
            if isinstance(last_time, pd.Timestamp):
                last_time_str = last_time.strftime("%Y-%m-%d %H:%M:%S")
            else:
                last_time_str = str(last_time)

            sell_value = position * last_price * (1 - self.commission_rate)
            entry_cost = current_trade.entry_price * position
            current_trade.exit_time = last_time_str
            current_trade.exit_price = last_price
            current_trade.pnl = sell_value - entry_cost
            current_trade.pnl_pct = (current_trade.pnl / entry_cost) * 100
            trades.append(current_trade)
            equity = sell_value

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
