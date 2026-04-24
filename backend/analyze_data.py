#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
加密货币数据分析程序
自动扫描 data/ 目录下的 CSV，根据文件类型执行对应的分析并输出报告
支持调用 DeepSeek API 获取交易建议（做多/做空、开仓价、止盈止损）

用法：
    python ./backend/analyze_data.py
    python ./backend/analyze_data.py --symbol BTC/USDT --timeframe 1h
    python ./backend/analyze_data.py --symbol ETH/USDT --timeframe 4h --deepseek
    python ./backend/analyze_data.py --symbol BTC/USDT --deepseek
"""

import os
import glob
import json
import argparse
import urllib.request
from datetime import datetime

from dotenv import load_dotenv
import pandas as pd
import numpy as np

# 加载 .env 文件（如果存在）
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(_env_path):
    load_dotenv(_env_path)

# 数据目录
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def scan_csv_files():
    """扫描 data 目录下所有 CSV 文件，按类型分类"""
    pattern = os.path.join(DATA_DIR, "*.csv")
    files = glob.glob(pattern)

    groups = {
        'ohlcv': [],
        'ticker': [],
        'orderbook': [],
        'trades': [],
        'unknown': []
    }

    for f in files:
        basename = os.path.basename(f)
        if '_ohlcv_' in basename:
            groups['ohlcv'].append(f)
        elif '_ticker' in basename:
            groups['ticker'].append(f)
        elif '_orderbook' in basename:
            groups['orderbook'].append(f)
        elif '_trades' in basename:
            groups['trades'].append(f)
        else:
            groups['unknown'].append(f)

    return groups


def analyze_ohlcv(filepath: str, silent: bool = False):
    """分析 OHLCV K线数据，返回指标字典供 prompt 生成使用
    :param silent: 为 True 时仅计算不打印
    """
    df = pd.read_csv(filepath)
    if df.empty:
        if not silent:
            print(f"  [跳过] 空文件: {os.path.basename(filepath)}")
        return None

    symbol = df['交易对'].iloc[0] if '交易对' in df.columns else 'Unknown'
    timeframe = df['周期'].iloc[0] if '周期' in df.columns else 'Unknown'

    # 确保时间列正确解析
    if '时间' in df.columns:
        df['时间'] = pd.to_datetime(df['时间'])
        df = df.sort_values('时间')

    close = df['收盘价']
    high = df['最高价']
    low = df['最低价']
    volume = df['成交量']

    # 基础统计
    total_rows = len(df)
    start_time = str(df['时间'].iloc[0]) if '时间' in df.columns else 'N/A'
    end_time = str(df['时间'].iloc[-1]) if '时间' in df.columns else 'N/A'

    # 价格统计
    price_max = float(high.max())
    price_min = float(low.min())
    price_start = float(df['开盘价'].iloc[0])
    price_end = float(close.iloc[-1])
    total_return = (price_end - price_start) / price_start * 100 if price_start != 0 else 0

    # 收益率与波动
    df['收益率'] = close.pct_change()
    mean_return = float(df['收益率'].mean() * 100)
    volatility = float(df['收益率'].std() * 100)

    # ========== 均线系统 ==========
    df['MA5'] = close.rolling(window=5, min_periods=1).mean()
    df['MA7'] = close.rolling(window=7, min_periods=1).mean()
    df['MA10'] = close.rolling(window=10, min_periods=1).mean()
    df['MA20'] = close.rolling(window=20, min_periods=1).mean()
    df['MA30'] = close.rolling(window=30, min_periods=1).mean()
    df['MA60'] = close.rolling(window=60, min_periods=1).mean()
    ma5_latest = float(df['MA5'].iloc[-1])
    ma7_latest = float(df['MA7'].iloc[-1])
    ma10_latest = float(df['MA10'].iloc[-1])
    ma20_latest = float(df['MA20'].iloc[-1])
    ma30_latest = float(df['MA30'].iloc[-1])
    ma60_latest = float(df['MA60'].iloc[-1])

    # 均线多空判断
    if close.iloc[-1] > ma5_latest > ma10_latest > ma20_latest > ma30_latest:
        ma_signal = "强势多头"
    elif close.iloc[-1] > ma7_latest > ma30_latest:
        ma_signal = "多头排列"
    elif close.iloc[-1] < ma5_latest < ma10_latest < ma20_latest < ma30_latest:
        ma_signal = "强势空头"
    elif close.iloc[-1] < ma7_latest < ma30_latest:
        ma_signal = "空头排列"
    else:
        ma_signal = "震荡整理"

    # 均线乖离率
    ma20_bias = (close.iloc[-1] - ma20_latest) / ma20_latest * 100

    # ========== 最大回撤 & 波动 ==========
    cummax = close.cummax()
    drawdown = (close - cummax) / cummax
    max_drawdown = float(drawdown.min() * 100)

    # ========== 成交量指标 ==========
    total_volume = float(volume.sum())
    avg_volume = float(volume.mean())
    df['VMA5'] = volume.rolling(window=5, min_periods=1).mean()
    df['VMA10'] = volume.rolling(window=10, min_periods=1).mean()
    df['VMA20'] = volume.rolling(window=20, min_periods=1).mean()
    vma5_latest = float(df['VMA5'].iloc[-1])
    vma10_latest = float(df['VMA10'].iloc[-1])
    vma20_latest = float(df['VMA20'].iloc[-1])
    vol_trend = "放量" if vma5_latest > vma10_latest > vma20_latest else "缩量" if vma5_latest < vma10_latest < vma20_latest else "平量"

    # OBV 能量潮
    obv = [0]
    for i in range(1, len(close)):
        if close.iloc[i] > close.iloc[i - 1]:
            obv.append(obv[-1] + volume.iloc[i])
        elif close.iloc[i] < close.iloc[i - 1]:
            obv.append(obv[-1] - volume.iloc[i])
        else:
            obv.append(obv[-1])
    df['OBV'] = obv
    obv_latest = float(df['OBV'].iloc[-1])
    obv_ma = df['OBV'].rolling(window=20, min_periods=1).mean().iloc[-1]
    obv_signal = "买入" if obv_latest > obv_ma else "卖出"

    # ========== RSI (14周期) ==========
    delta = close.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window=14, min_periods=1).mean()
    avg_loss = loss.rolling(window=14, min_periods=1).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    df['RSI'] = 100 - (100 / (1 + rs))
    rsi_latest = float(df['RSI'].iloc[-1])
    rsi_status = "超买" if rsi_latest > 70 else "超卖" if rsi_latest < 30 else "中性"

    # ========== MACD ==========
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    df['MACD_DIF'] = ema12 - ema26
    df['MACD_DEA'] = df['MACD_DIF'].ewm(span=9, adjust=False).mean()
    df['MACD_HIST'] = (df['MACD_DIF'] - df['MACD_DEA']) * 2
    macd_dif = float(df['MACD_DIF'].iloc[-1])
    macd_dea = float(df['MACD_DEA'].iloc[-1])
    macd_hist = float(df['MACD_HIST'].iloc[-1])
    macd_signal = "金叉" if macd_dif > macd_dea and df['MACD_DIF'].iloc[-2] <= df['MACD_DEA'].iloc[-2] else \
                  "死叉" if macd_dif < macd_dea and df['MACD_DIF'].iloc[-2] >= df['MACD_DEA'].iloc[-2] else \
                  "多头" if macd_dif > macd_dea else "空头"

    # ========== 布林带 BOLL ==========
    df['BOLL_MID'] = close.rolling(window=20, min_periods=1).mean()
    df['BOLL_STD'] = close.rolling(window=20, min_periods=1).std()
    df['BOLL_UP'] = df['BOLL_MID'] + 2 * df['BOLL_STD']
    df['BOLL_DN'] = df['BOLL_MID'] - 2 * df['BOLL_STD']
    boll_up = float(df['BOLL_UP'].iloc[-1])
    boll_mid = float(df['BOLL_MID'].iloc[-1])
    boll_dn = float(df['BOLL_DN'].iloc[-1])
    boll_width = (boll_up - boll_dn) / boll_mid * 100
    boll_position = "上轨附近" if close.iloc[-1] > boll_up * 0.995 else \
                    "下轨附近" if close.iloc[-1] < boll_dn * 1.005 else "中轨附近"

    # ========== KDJ ==========
    low_min = low.rolling(window=9, min_periods=1).min()
    high_max = high.rolling(window=9, min_periods=1).max()
    rsv = (close - low_min) / (high_max - low_min) * 100
    rsv = rsv.fillna(50)
    df['K'] = rsv.ewm(com=2, adjust=False).mean()
    df['D'] = df['K'].ewm(com=2, adjust=False).mean()
    df['J'] = 3 * df['K'] - 2 * df['D']
    k_latest = float(df['K'].iloc[-1])
    d_latest = float(df['D'].iloc[-1])
    j_latest = float(df['J'].iloc[-1])
    kdj_signal = "金叉" if k_latest > d_latest and df['K'].iloc[-2] <= df['D'].iloc[-2] else \
                 "死叉" if k_latest < d_latest and df['K'].iloc[-2] >= df['D'].iloc[-2] else \
                 "多头" if k_latest > d_latest else "空头"

    # ========== ATR (平均真实波幅) ==========
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df['ATR'] = tr.rolling(window=14, min_periods=1).mean()
    atr_latest = float(df['ATR'].iloc[-1])
    atr_percent = atr_latest / close.iloc[-1] * 100

    # ========== 威廉指标 WR ==========
    wr = (high_max - close) / (high_max - low_min) * 100
    df['WR'] = wr
    wr_latest = float(df['WR'].iloc[-1])
    wr_status = "超卖" if wr_latest > 80 else "超买" if wr_latest < 20 else "中性"

    # ========== CCI 顺势指标 ==========
    tp = (high + low + close) / 3
    tp_sma = tp.rolling(window=20, min_periods=1).mean()
    tp_std = tp.rolling(window=20, min_periods=1).std()
    df['CCI'] = (tp - tp_sma) / (0.015 * tp_std)
    cci_latest = float(df['CCI'].iloc[-1])
    cci_status = "超买" if cci_latest > 100 else "超卖" if cci_latest < -100 else "中性"

    # ========== 支撑/阻力位 (近期高低点) ==========
    recent_highs = high.tail(20)
    recent_lows = low.tail(20)
    resistance = float(recent_highs.max())
    support = float(recent_lows.min())
    # 次高/次低作为次要阻力和支撑
    resistance2 = float(recent_highs.nlargest(2).iloc[-1])
    support2 = float(recent_lows.nsmallest(2).iloc[-1])

    # ========== 近期动量 ==========
    returns = close.pct_change()
    momentum_1h = float(returns.iloc[-1] * 100) if len(returns) >= 1 else 0
    momentum_4h = float(returns.tail(4).sum() * 100) if len(returns) >= 4 else 0
    momentum_24h = float(returns.tail(24).sum() * 100) if len(returns) >= 24 else 0
    momentum_7d = float(returns.tail(7 * 24).sum() * 100) if len(returns) >= 7 * 24 else float(returns.sum() * 100)

    # 最近K线数据（取50条用于prompt）
    recent_df = df.tail(50)[['时间', '开盘价', '最高价', '最低价', '收盘价', '成交量']].copy()
    recent_df['时间'] = recent_df['时间'].astype(str)
    recent_klines = recent_df.to_dict('records')

    # 组装返回字典
    data = {
        'symbol': symbol,
        'timeframe': timeframe,
        'total_rows': total_rows,
        'start_time': start_time,
        'end_time': end_time,
        'price_max': price_max,
        'price_min': price_min,
        'price_start': price_start,
        'price_end': price_end,
        'total_return': total_return,
        'mean_return': mean_return,
        'volatility': volatility,
        'max_drawdown': max_drawdown,
        'total_volume': total_volume,
        'avg_volume': avg_volume,
        # 均线
        'ma5': ma5_latest,
        'ma7': ma7_latest,
        'ma10': ma10_latest,
        'ma20': ma20_latest,
        'ma30': ma30_latest,
        'ma60': ma60_latest,
        'ma_signal': ma_signal,
        'ma20_bias': ma20_bias,
        # 成交量
        'vma5': vma5_latest,
        'vma10': vma10_latest,
        'vma20': vma20_latest,
        'vol_trend': vol_trend,
        'obv': obv_latest,
        'obv_signal': obv_signal,
        # RSI
        'rsi': rsi_latest,
        'rsi_status': rsi_status,
        # MACD
        'macd_dif': macd_dif,
        'macd_dea': macd_dea,
        'macd_hist': macd_hist,
        'macd_signal': macd_signal,
        # 布林带
        'boll_up': boll_up,
        'boll_mid': boll_mid,
        'boll_dn': boll_dn,
        'boll_width': boll_width,
        'boll_position': boll_position,
        # KDJ
        'kdj_k': k_latest,
        'kdj_d': d_latest,
        'kdj_j': j_latest,
        'kdj_signal': kdj_signal,
        # ATR
        'atr': atr_latest,
        'atr_percent': atr_percent,
        # WR
        'wr': wr_latest,
        'wr_status': wr_status,
        # CCI
        'cci': cci_latest,
        'cci_status': cci_status,
        # 支撑阻力
        'resistance': resistance,
        'resistance2': resistance2,
        'support': support,
        'support2': support2,
        # 动量
        'momentum_1h': momentum_1h,
        'momentum_4h': momentum_4h,
        'momentum_24h': momentum_24h,
        'momentum_7d': momentum_7d,
        'recent_klines': recent_klines,
    }

    if not silent:
        print(f"\n{'=' * 60}")
        print(f" 交易对: {symbol}  |  周期: {timeframe}  |  数据条数: {total_rows}")
        print(f"{'=' * 60}")
        print(f" 时间范围: {start_time}  ~  {end_time}")
        print(f" 价格区间: {price_min:,.2f}  ~  {price_max:,.2f}")
        print(f" 期初/期末价格: {price_start:,.2f} / {price_end:,.2f}")
        print(f" 总收益率: {total_return:+.2f}%")
        print(f" 平均收益率(每K线): {mean_return:+.4f}%")
        print(f" 波动率(标准差): {volatility:.4f}%")
        print(f" 最大回撤: {max_drawdown:.2f}%")
        print(f" 成交量合计: {total_volume:,.4f}  |  平均: {avg_volume:,.4f}")

        print(f"\n{'-' * 40}")
        print(" 均线系统")
        print(f"{'-' * 40}")
        print(f" MA5/MA10/MA20/MA30/MA60: {ma5_latest:,.2f} / {ma10_latest:,.2f} / {ma20_latest:,.2f} / {ma30_latest:,.2f} / {ma60_latest:,.2f}")
        print(f" 均线信号: {ma_signal}  |  MA20乖离率: {ma20_bias:+.2f}%")

        print(f"\n{'-' * 40}")
        print(" 动量指标")
        print(f"{'-' * 40}")
        print(f" RSI(14): {rsi_latest:.2f}  [{rsi_status}]")
        print(f" MACD: DIF={macd_dif:.4f} DEA={macd_dea:.4f} HIST={macd_hist:.4f}  [{macd_signal}]")
        print(f" KDJ: K={k_latest:.2f} D={d_latest:.2f} J={j_latest:.2f}  [{kdj_signal}]")
        print(f" WR(14): {wr_latest:.2f}  [{wr_status}]")
        print(f" CCI(20): {cci_latest:.2f}  [{cci_status}]")

        print(f"\n{'-' * 40}")
        print(" 布林带 & ATR")
        print(f"{'-' * 40}")
        print(f" 布林上轨/中轨/下轨: {boll_up:,.2f} / {boll_mid:,.2f} / {boll_dn:,.2f}")
        print(f" 布林宽度: {boll_width:.2f}%  |  价格位置: {boll_position}")
        print(f" ATR(14): {atr_latest:.2f}  ({atr_percent:.2f}%)")

        print(f"\n{'-' * 40}")
        print(" 成交量 & OBV")
        print(f"{'-' * 40}")
        print(f" VMA5/VMA10/VMA20: {vma5_latest:,.2f} / {vma10_latest:,.2f} / {vma20_latest:,.2f}")
        print(f" 量能趋势: {vol_trend}  |  OBV信号: {obv_signal}")

        print(f"\n{'-' * 40}")
        print(" 支撑阻力 & 近期动量")
        print(f"{'-' * 40}")
        print(f" 强阻力/次阻力: {resistance:,.4f} / {resistance2:,.4f}")
        print(f" 强支撑/次支撑: {support:,.4f} / {support2:,.4f}")
        print(f" 1h/4h/24h/7d动量: {momentum_1h:+.2f}% / {momentum_4h:+.2f}% / {momentum_24h:+.2f}% / {momentum_7d:+.2f}%")

        recent5 = df.tail(5)[['时间', '开盘价', '最高价', '最低价', '收盘价', '成交量']]
        print(f"\n{'-' * 40}")
        print(" 最近5条K线:")
        print(f"{'-' * 40}")
        print(recent5.to_string(index=False))

    return data


def analyze_ticker(filepath: str):
    """分析 Ticker 行情快照数据"""
    df = pd.read_csv(filepath)
    if df.empty:
        print(f"  [跳过] 空文件: {os.path.basename(filepath)}")
        return

    symbol = df['交易对'].iloc[0] if '交易对' in df.columns else 'Unknown'
    total_rows = len(df)

    print(f"\n{'=' * 60}")
    print(f" 交易对: {symbol}  |  Ticker 快照数: {total_rows}")
    print(f"{'=' * 60}")

    if total_rows == 1:
        row = df.iloc[0]
        print(f" 最新价: {row.get('最新价', 'N/A')}")
        print(f" 涨跌幅: {row.get('涨跌幅', 'N/A')}%")
        print(f" 买一/卖一: {row.get('买一价', 'N/A')} / {row.get('卖一价', 'N/A')}")
        print(f" 24h 最高/最低: {row.get('最高价', 'N/A')} / {row.get('最低价', 'N/A')}")
        print(f" 24h 成交量: {row.get('基础币成交量', 'N/A')}")
        return

    # 多条时做时间序列分析
    if '时间' in df.columns:
        df['时间'] = pd.to_datetime(df['时间'])
        df = df.sort_values('时间')

    latest = df.iloc[-1]
    earliest = df.iloc[0]

    print(f" 时间范围: {earliest.get('时间', 'N/A')}  ~  {latest.get('时间', 'N/A')}")
    print(f" 最新价: {latest.get('最新价', 'N/A')}")
    print(f" 涨跌幅: {latest.get('涨跌幅', 'N/A')}%")
    print(f" 买一/卖一: {latest.get('买一价', 'N/A')} / {latest.get('卖一价', 'N/A')}")

    if '最新价' in df.columns:
        df['最新价'] = pd.to_numeric(df['最新价'], errors='coerce')
        print(f" 期间最高/最低价: {df['最新价'].max()} / {df['最新价'].min()}")

    # 买卖价差趋势
    if '买一价' in df.columns and '卖一价' in df.columns:
        df['spread'] = pd.to_numeric(df['卖一价'], errors='coerce') - pd.to_numeric(df['买一价'], errors='coerce')
        print(f" 平均买卖价差: {df['spread'].mean():.6f}")
        print(f" 最新买卖价差: {df['spread'].iloc[-1]:.6f}")


def analyze_orderbook(filepath: str):
    """分析订单簿数据"""
    df = pd.read_csv(filepath)
    if df.empty:
        print(f"  [跳过] 空文件: {os.path.basename(filepath)}")
        return

    symbol = df['交易对'].iloc[0] if '交易对' in df.columns else 'Unknown'

    bids = df[df['方向'] == '买单'] if '方向' in df.columns else pd.DataFrame()
    asks = df[df['方向'] == '卖单'] if '方向' in df.columns else pd.DataFrame()

    print(f"\n{'=' * 60}")
    print(f" 交易对: {symbol}  |  订单簿分析")
    print(f"{'=' * 60}")
    print(f" 买单档位数: {len(bids)}  |  卖单档位数: {len(asks)}")

    if not bids.empty and '价格' in bids.columns and '数量' in bids.columns:
        bids['金额'] = bids['价格'] * bids['数量']
        print(f" 买单总数量: {bids['数量'].sum():,.4f}")
        print(f" 买单总金额: {bids['金额'].sum():,.2f}")
        print(f" 最高买价: {bids['价格'].max():,.6f}")

    if not asks.empty and '价格' in asks.columns and '数量' in asks.columns:
        asks['金额'] = asks['价格'] * asks['数量']
        print(f" 卖单总数量: {asks['数量'].sum():,.4f}")
        print(f" 卖单总金额: {asks['金额'].sum():,.2f}")
        print(f" 最低卖价: {asks['价格'].min():,.6f}")

    if not bids.empty and not asks.empty:
        spread = asks['价格'].min() - bids['价格'].max()
        mid_price = (asks['价格'].min() + bids['价格'].max()) / 2
        print(f" 买卖价差: {spread:.6f} ({spread / mid_price * 100:.4f}%)")
        print(f" 中间价: {mid_price:.6f}")

        # 前5档深度
        top5_bid_vol = bids.head(5)['数量'].sum() if '数量' in bids.columns else 0
        top5_ask_vol = asks.head(5)['数量'].sum() if '数量' in asks.columns else 0
        print(f" 前5档买单量: {top5_bid_vol:,.4f}  |  前5档卖单量: {top5_ask_vol:,.4f}")


def analyze_trades(filepath: str):
    """分析成交记录数据"""
    df = pd.read_csv(filepath)
    if df.empty:
        print(f"  [跳过] 空文件: {os.path.basename(filepath)}")
        return

    symbol = df['交易对'].iloc[0] if '交易对' in df.columns else 'Unknown'
    total = len(df)

    print(f"\n{'=' * 60}")
    print(f" 交易对: {symbol}  |  成交记录数: {total}")
    print(f"{'=' * 60}")

    buys = df[df['方向'] == '买入'] if '方向' in df.columns else pd.DataFrame()
    sells = df[df['方向'] == '卖出'] if '方向' in df.columns else pd.DataFrame()

    print(f" 买入笔数: {len(buys)}  |  卖出笔数: {len(sells)}")

    if '成交额' in df.columns:
        df['成交额'] = pd.to_numeric(df['成交额'], errors='coerce')
        print(f" 总成交额: {df['成交额'].sum():,.2f}")
        print(f" 平均单笔成交额: {df['成交额'].mean():,.2f}")
        print(f" 最大单笔成交额: {df['成交额'].max():,.2f}")

    if '价格' in df.columns:
        df['价格'] = pd.to_numeric(df['价格'], errors='coerce')
        print(f" 成交价格区间: {df['价格'].min():,.6f} ~ {df['价格'].max():,.6f}")

    if '数量' in df.columns:
        df['数量'] = pd.to_numeric(df['数量'], errors='coerce')
        print(f" 总成交数量: {df['数量'].sum():,.4f}")

    if not buys.empty and '成交额' in buys.columns:
        print(f" 买入总成交额: {buys['成交额'].sum():,.2f}")
    if not sells.empty and '成交额' in sells.columns:
        print(f" 卖出总成交额: {sells['成交额'].sum():,.2f}")


def analyze_all():
    """主入口：扫描并分析所有数据"""
    print(f"\n{'#' * 60}")
    print(f"# 加密货币数据分析报告")
    print(f"# 扫描目录: {DATA_DIR}")
    print(f"# 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'#' * 60}")

    groups = scan_csv_files()

    total_files = sum(len(v) for v in groups.values())
    print(f"\n发现 {total_files} 个 CSV 文件:")
    for k, v in groups.items():
        if v:
            print(f"  - {k}: {len(v)} 个")

    # 按优先级分析
    if groups['ohlcv']:
        print(f"\n{'#' * 60}")
        print(f"# OHLCV K线数据分析")
        print(f"{'#' * 60}")
        for f in sorted(groups['ohlcv']):
            analyze_ohlcv(f)

    if groups['ticker']:
        print(f"\n{'#' * 60}")
        print(f"# Ticker 行情数据分析")
        print(f"{'#' * 60}")
        for f in sorted(groups['ticker']):
            analyze_ticker(f)

    if groups['orderbook']:
        print(f"\n{'#' * 60}")
        print(f"# Orderbook 订单簿分析")
        print(f"{'#' * 60}")
        for f in sorted(groups['orderbook']):
            analyze_orderbook(f)

    if groups['trades']:
        print(f"\n{'#' * 60}")
        print(f"# Trades 成交记录分析")
        print(f"{'#' * 60}")
        for f in sorted(groups['trades']):
            analyze_trades(f)

    print(f"\n{'#' * 60}")
    print(f"# 分析完成")
    print(f"{'#' * 60}\n")


def generate_prompt(data: dict) -> str:
    """基于分析指标生成 DeepSeek Prompt"""
    klines_text = "\n".join(
        f"  {k['时间']} | 开:{k['开盘价']:.4f} 高:{k['最高价']:.4f} 低:{k['最低价']:.4f} 收:{k['收盘价']:.4f} 量:{k['成交量']:.4f}"
        for k in data['recent_klines']
    )

    prompt = f"""你是一位专业的加密货币量化分析师。请基于以下K线数据和技术指标，给出明确的交易建议。

## 交易对信息
- 交易对: {data['symbol']}
- 周期: {data['timeframe']}
- 数据时间范围: {data['start_time']} ~ {data['end_time']}
- 数据条数: {data['total_rows']}

## 价格与收益
- 最新收盘价: {data['price_end']:.4f}
- 期间最高/最低价: {data['price_max']:.4f} / {data['price_min']:.4f}
- 期初/期末价格: {data['price_start']:.4f} / {data['price_end']:.4f}
- 总收益率: {data['total_return']:+.2f}%
- 平均收益率(每K线): {data['mean_return']:+.4f}%
- 波动率(标准差): {data['volatility']:.4f}%
- 最大回撤: {data['max_drawdown']:.2f}%
- 1h/4h/24h/7d动量: {data['momentum_1h']:+.2f}% / {data['momentum_4h']:+.2f}% / {data['momentum_24h']:+.2f}% / {data['momentum_7d']:+.2f}%

## 均线系统
- MA5/MA10/MA20/MA30/MA60: {data['ma5']:.4f} / {data['ma10']:.4f} / {data['ma20']:.4f} / {data['ma30']:.4f} / {data['ma60']:.4f}
- 均线信号: {data['ma_signal']}
- MA20乖离率: {data['ma20_bias']:+.2f}%

## 动量指标
- RSI(14): {data['rsi']:.2f} [{data['rsi_status']}]
- MACD: DIF={data['macd_dif']:.4f} DEA={data['macd_dea']:.4f} HIST={data['macd_hist']:.4f} [{data['macd_signal']}]
- KDJ: K={data['kdj_k']:.2f} D={data['kdj_d']:.2f} J={data['kdj_j']:.2f} [{data['kdj_signal']}]
- WR(14): {data['wr']:.2f} [{data['wr_status']}]
- CCI(20): {data['cci']:.2f} [{data['cci_status']}]

## 布林带 & ATR
- 布林上轨/中轨/下轨: {data['boll_up']:.4f} / {data['boll_mid']:.4f} / {data['boll_dn']:.4f}
- 布林宽度: {data['boll_width']:.2f}% | 价格位置: {data['boll_position']}
- ATR(14): {data['atr']:.4f} ({data['atr_percent']:.2f}%)

## 成交量 & OBV
- VMA5/VMA10/VMA20: {data['vma5']:,.2f} / {data['vma10']:,.2f} / {data['vma20']:,.2f}
- 量能趋势: {data['vol_trend']} | OBV信号: {data['obv_signal']}
- 成交量合计: {data['total_volume']:,.2f} | 平均: {data['avg_volume']:,.2f}

## 支撑与阻力
- 强阻力/次阻力: {data['resistance']:.4f} / {data['resistance2']:.4f}
- 强支撑/次支撑: {data['support']:.4f} / {data['support2']:.4f}

## 最近50条K线数据
{klines_text}

## 要求
请综合以上所有技术指标，判断当前是否适合做空或做多，给出：
1. 交易方向（做多 / 做空 / 观望）
2. 建议开仓价（具体数字）
3. 建议止盈价（平仓获利，具体数字）
4. 建议止损价（平仓止损，具体数字）
5. 简要理由（结合多个指标说明）

请务必以 JSON 格式返回，不要包含任何解释性文字：
{{
    "direction": "做多",
    "entry_price": 0.3500,
    "take_profit": 0.4200,
    "stop_loss": 0.3200,
    "reason": "KDJ金叉+MACD多头，价格接近布林下轨支撑，RSI中性偏多"
}}
"""
    return prompt


def call_deepseek(prompt: str, api_key: str = None, model: str = "deepseek-reasoner") -> dict:
    """调用 DeepSeek API 获取交易建议"""
    if api_key is None:
        api_key = os.environ.get("DEEPSEEK_API_KEY", "")

    if not api_key:
        print("\n[ERR] 未设置 DeepSeek API Key。可通过以下方式设置：")
        print("  1. .env 文件: 在 backend/.env 中写入 DEEPSEEK_API_KEY=your-key")
        print("  2. 环境变量: $env:DEEPSEEK_API_KEY = 'your-api-key'")
        print("  3. 命令行参数: --deepseek-key your-api-key")
        return None

    url = "https://api.deepseek.com/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "你是一位专业的加密货币量化分析师，擅长技术分析和短线交易决策。你只输出 JSON，不输出任何额外文字。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0,
        "seed": 42,
        "max_tokens": 512,
    }

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))

        content = result["choices"][0]["message"]["content"]
        # 尝试从 content 中提取 JSON
        try:
            # 如果 content 被 markdown 代码块包裹，先去掉
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            advice = json.loads(content)
        except Exception:
            advice = {"raw_response": content}

        return advice

    except urllib.error.HTTPError as e:
        print(f"\n[ERR] DeepSeek API HTTP 错误: {e.code}")
        try:
            err_body = json.loads(e.read().decode("utf-8"))
            print(f"       详情: {err_body}")
        except Exception:
            pass
        return None
    except Exception as e:
        print(f"\n[ERR] DeepSeek API 调用失败: {e}")
        return None


def analyze_symbol_timeframe(symbol: str, timeframe: str, use_deepseek: bool = False,
                              api_key: str = None, model: str = "deepseek-chat"):
    """分析指定交易对和周期的 OHLCV 数据，可选调用 DeepSeek 获取交易建议"""
    filename = f"{symbol.replace('/', '_')}_ohlcv_{timeframe}.csv"
    filepath = os.path.join(DATA_DIR, filename)

    if not os.path.exists(filepath):
        print(f"[ERR] 文件不存在: {filepath}")
        print(f"      可用文件:")
        groups = scan_csv_files()
        for f in sorted(groups['ohlcv']):
            print(f"        - {os.path.basename(f)}")
        return

    # 执行分析并获取指标字典
    data = analyze_ohlcv(filepath)
    if data is None:
        return

    # 调用 DeepSeek 获取交易建议
    if use_deepseek:
        print(f"\n{'-' * 60}")
        print(" 正在生成分析提示词并调用 DeepSeek API ...")
        print(f"{'-' * 60}")

        prompt = generate_prompt(data)
        # print("\n[发送的提示词]:\n", prompt)

        advice = call_deepseek(prompt, api_key=api_key, model=model)
        if advice:
            print(f"\n{'=' * 60}")
            print(" DeepSeek 交易建议")
            print(f"{'=' * 60}")
            if "direction" in advice:
                print(f" 交易方向 : {advice.get('direction', 'N/A')}")
                print(f" 建议开仓价: {advice.get('entry_price', 'N/A')}")
                print(f" 建议止盈价: {advice.get('take_profit', 'N/A')}")
                print(f" 建议止损价: {advice.get('stop_loss', 'N/A')}")
                print(f" 理由     : {advice.get('reason', 'N/A')}")
            else:
                # 非结构化输出
                for k, v in advice.items():
                    print(f" {k}: {v}")
            print(f"{'=' * 60}")


def main():
    parser = argparse.ArgumentParser(description="加密货币数据分析程序")
    parser.add_argument('--symbol', type=str, default='BTC/USDT', help='指定交易对，如 BTC/USDT')
    parser.add_argument('--timeframe', type=str, default='1h', choices=['1h', '4h', '1d'],
                        help='指定K线周期')
    parser.add_argument('--all', action='store_true', help='分析 data 目录下所有 CSV 文件')
    parser.add_argument('--deepseek', action='store_true',
                        help='调用 DeepSeek API 获取交易建议（需配置 API Key）')
    parser.add_argument('--deepseek-key', type=str, default=None,
                        help='DeepSeek API Key（也可通过环境变量 DEEPSEEK_API_KEY 设置）')
    parser.add_argument('--deepseek-model', type=str, default='deepseek-chat',
                        help='DeepSeek 模型名称，默认 deepseek-chat')
    args = parser.parse_args()

    if args.all:
        analyze_all()
    else:
        analyze_symbol_timeframe(
            args.symbol,
            args.timeframe,
            use_deepseek=args.deepseek,
            api_key=args.deepseek_key,
            model=args.deepseek_model,
        )


if __name__ == '__main__':
    main()
