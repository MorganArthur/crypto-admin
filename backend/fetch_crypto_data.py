#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
使用 ccxt 爬取加密货币数据并输出 CSV
支持功能：
  1. 获取交易所所有交易对的最新行情 (ticker)
  2. 获取指定交易对的 K线/OHLCV 数据
  3. 获取指定交易对的订单簿 (order book)
  4. 获取最近成交记录 (trades)

用法示例：
  python ./backend/fetch_crypto_data.py --mode ticker --symbol BTC/USDT
  python ./backend/fetch_crypto_data.py --mode ohlcv --symbol BTC/USDT --timeframe 1h
  python ./backend/fetch_crypto_data.py --mode ohlcv --symbol BTC/USDT --timeframe 4h
  python ./backend/fetch_crypto_data.py --mode ohlcv --symbol BTC/USDT --timeframe 1d
  python ./backend/fetch_crypto_data.py --mode orderbook --symbol BTC/USDT
  python ./backend/fetch_crypto_data.py --mode trades --symbol BTC/USDT
"""

import os
import sys
import argparse
from datetime import datetime
from typing import Optional

import ccxt
import pandas as pd

# CSV 输出目录
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)


def save_csv(df: pd.DataFrame, filename: str, append: bool = False, dedup_cols: Optional[list] = None) -> str:
    """保存 DataFrame 为 CSV 并返回文件路径
    :param append: 为 True 时追加数据，不覆盖已有文件
    :param dedup_cols: 去重依据的列名列表，如 ['时间戳']
    """
    filepath = os.path.join(DATA_DIR, filename)
    if append and os.path.exists(filepath):
        old_df = pd.read_csv(filepath)
        combined = pd.concat([old_df, df], ignore_index=True)
        if dedup_cols:
            before = len(combined)
            combined = combined.drop_duplicates(subset=dedup_cols, keep='last')
            after = len(combined)
            print(f"[i] 去重: {before} -> {after} 条 ({before - after} 条重复)")
        combined.to_csv(filepath, index=False, encoding='utf-8-sig')
        print(f"[OK] CSV 已更新（追加+去重）: {filepath}")
    else:
        df.to_csv(filepath, index=False, encoding='utf-8-sig')
        print(f"[OK] CSV 已保存: {filepath}")
    return filepath


def fetch_tickers(symbol: Optional[str] = None) -> pd.DataFrame:
    """
    获取行情数据 (ticker)
    - symbol 为 None 时获取交易所全部交易对
    - symbol 指定时获取单个交易对
    """
    exchange = ccxt.binance({'enableRateLimit': True})
    exchange.load_markets()

    if symbol:
        ticker = exchange.fetch_ticker(symbol)
        data = [{
            '交易对': ticker['symbol'],
            '时间戳': ticker['timestamp'],
            '时间': ticker['datetime'],
            '最高价': ticker['high'],
            '最低价': ticker['low'],
            '买一价': ticker['bid'],
            '买一量': ticker['bidVolume'],
            '卖一价': ticker['ask'],
            '卖一量': ticker['askVolume'],
            '加权均价': ticker['vwap'],
            '开盘价': ticker['open'],
            '收盘价': ticker['close'],
            '最新价': ticker['last'],
            '昨收': ticker['previousClose'],
            '涨跌额': ticker['change'],
            '涨跌幅': ticker['percentage'],
            '均价': ticker['average'],
            '基础币成交量': ticker['baseVolume'],
            '计价币成交量': ticker['quoteVolume'],
        }]
    else:
        tickers = exchange.fetch_tickers()
        data = []
        for sym, t in tickers.items():
            data.append({
                '交易对': sym,
                '时间戳': t.get('timestamp'),
                '时间': t.get('datetime'),
                '最高价': t.get('high'),
                '最低价': t.get('low'),
                '买一价': t.get('bid'),
                '卖一价': t.get('ask'),
                '最新价': t.get('last'),
                '涨跌额': t.get('change'),
                '涨跌幅': t.get('percentage'),
                '基础币成交量': t.get('baseVolume'),
                '计价币成交量': t.get('quoteVolume'),
            })

    df = pd.DataFrame(data)
    return df


def fetch_ohlcv(symbol: str, timeframe: str = '1h', since: Optional[int] = None) -> pd.DataFrame:
    """
    获取 K线/OHLCV 数据
    :param timeframe: 时间周期, 如 '1m', '5m', '15m', '1h', '4h', '1d', '1w'
    :param since: 起始时间戳（毫秒），若提供则从该时间开始获取数据（支持分页）
    """
    exchange = ccxt.binance({'enableRateLimit': True})
    exchange.load_markets()

    if symbol not in exchange.symbols:
        raise ValueError(f"交易所 binance 不支持交易对 {symbol}")

    if since is None:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=1000)
    else:
        # 分页获取，从 since 时间开始拉取到最新
        all_ohlcv = []
        current_since = since
        while True:
            batch = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=1000, since=current_since)
            if not batch:
                break
            all_ohlcv.extend(batch)
            if len(batch) < 1000:
                break
            # 使用最后一条时间戳 + 1ms 作为下一页起点，避免重复
            current_since = batch[-1][0] + 1
        ohlcv = all_ohlcv

    df = pd.DataFrame(ohlcv, columns=['时间戳', '开盘价', '最高价', '最低价', '收盘价', '成交量'])
    df['时间'] = pd.to_datetime(df['时间戳'], unit='ms')
    df['交易对'] = symbol
    df['周期'] = timeframe

    # 调整列顺序
    df = df[['交易对', '周期', '时间戳', '时间', '开盘价', '最高价', '最低价', '收盘价', '成交量']]
    return df


def fetch_order_book(symbol: str) -> pd.DataFrame:
    """
    获取订单簿数据 (Order Book)
    返回 bids 和 asks 合并的 DataFrame
    """
    exchange = ccxt.binance({'enableRateLimit': True})
    exchange.load_markets()

    if symbol not in exchange.symbols:
        raise ValueError(f"交易所 binance 不支持交易对 {symbol}")

    order_book = exchange.fetch_order_book(symbol, limit=1000)

    rows = []
    for i, (price, amount) in enumerate(order_book['bids'][:1000]):
        rows.append({
            '交易对': symbol,
            '方向': '买单',
            '价格': price,
            '数量': amount,
            '时间戳': order_book['timestamp'],
            '时间': order_book['datetime'],
            '序号': i + 1,
        })
    for i, (price, amount) in enumerate(order_book['asks'][:1000]):
        rows.append({
            '交易对': symbol,
            '方向': '卖单',
            '价格': price,
            '数量': amount,
            '时间戳': order_book['timestamp'],
            '时间': order_book['datetime'],
            '序号': i + 1,
        })

    df = pd.DataFrame(rows)
    return df


def fetch_trades(symbol: str) -> pd.DataFrame:
    """
    获取最近成交记录
    """
    exchange = ccxt.binance({'enableRateLimit': True})
    exchange.load_markets()

    if symbol not in exchange.symbols:
        raise ValueError(f"交易所 binance 不支持交易对 {symbol}")

    trades = exchange.fetch_trades(symbol, limit=1000)

    data = []
    for t in trades:
        data.append({
            '交易对': t['symbol'],
            '成交ID': t.get('id'),
            '时间戳': t['timestamp'],
            '时间': t['datetime'],
            '方向': '买入' if t['side'] == 'buy' else '卖出',
            '价格': t['price'],
            '数量': t['amount'],
            '成交额': t['cost'],
            '主动方': '吃单' if t.get('takerOrMaker') == 'taker' else '挂单' if t.get('takerOrMaker') == 'maker' else t.get('takerOrMaker'),
        })

    df = pd.DataFrame(data)
    return df


def list_exchanges():
    """列出 ccxt 支持的所有交易所"""
    print("ccxt 支持的交易所列表：")
    for ex in ccxt.exchanges:
        print(f"  - {ex}")


def main():
    parser = argparse.ArgumentParser(description="使用 ccxt 爬取加密货币数据")
    parser.add_argument('--mode', choices=['ticker', 'ohlcv', 'orderbook', 'trades', 'list-exchanges'],
                        default='ticker', help='爬取模式')
    parser.add_argument('--symbol', type=str, default='BTC/USDT', help='交易对, 如 BTC/USDT, ETH/USDT')
    parser.add_argument('--timeframe', type=str, default='4h', choices=['1h', '4h', '1d'], help='K线周期, 仅支持 1h 或 4h 或 1d')
    parser.add_argument('--output', type=str, default=None, help='自定义输出文件名')

    args = parser.parse_args()

    if args.mode == 'list-exchanges':
        list_exchanges()
        return

    # 生成默认文件名
    if args.output is None:
        if args.symbol:
            if args.mode == 'ohlcv':
                filename = f"{args.symbol.replace('/', '_')}_{args.mode}_{args.timeframe}.csv"
            else:
                filename = f"{args.symbol.replace('/', '_')}_{args.mode}.csv"
        else:
            filename = f"all_{args.mode}.csv"
    else:
        filename = args.output

    # 执行对应模式
    if args.mode == 'ticker':
        print("正在从 binance 获取行情数据 ...")
        df = fetch_tickers(args.symbol)
        save_csv(df, filename, append=True)
        print(f"共获取 {len(df)} 条行情数据")

    elif args.mode == 'ohlcv':
        # 若本地已有数据，读取最新时间戳作为同步起点
        since = None
        filepath = os.path.join(DATA_DIR, filename)
        if os.path.exists(filepath):
            try:
                existing_df = pd.read_csv(filepath)
                if not existing_df.empty and '时间戳' in existing_df.columns:
                    last_ts = int(existing_df['时间戳'].max())
                    since = last_ts + 1  # 加 1ms 避免重复获取最后一条
                    print(f"[i] 本地数据最新时间: {pd.to_datetime(last_ts, unit='ms')}，将从该时间点继续同步")
            except Exception as e:
                print(f"[WARN] 读取本地历史数据失败，将全量获取: {e}")

        print(f"正在从 binance 获取 {args.symbol} 的 {args.timeframe} K线数据 ...")
        df = fetch_ohlcv(args.symbol, args.timeframe, since=since)
        if df.empty:
            print("[i] 无新增数据，无需更新")
        else:
            save_csv(df, filename, append=True, dedup_cols=['时间戳'])
        print(f"共获取 {len(df)} 条 K线数据")

    elif args.mode == 'orderbook':
        print(f"正在从 binance 获取 {args.symbol} 的订单簿数据 ...")
        df = fetch_order_book(args.symbol)
        save_csv(df, filename)
        print(f"共获取 {len(df)} 条订单簿数据")

    elif args.mode == 'trades':
        print(f"正在从 binance 获取 {args.symbol} 的成交记录 ...")
        df = fetch_trades(args.symbol)
        save_csv(df, filename)
        print(f"共获取 {len(df)} 条成交记录")

    print("\n前 5 行数据预览：")
    print(df.head())


if __name__ == '__main__':
    main()
