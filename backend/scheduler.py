#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
定时任务调度器：定时更新 OHLCV 数据
用法示例：
    python ./backend/scheduler.py --symbols BTC/USDT ETH/USDT --timeframe 4h --interval 300
    python ./backend/scheduler.py --symbols BTC/USDT --timeframe 1d --interval 1440
    python ./backend/scheduler.py --symbols BTC/USDT ETH/USDT SOL/USDT SUI/USDT BNB/USDT 币安人生/USDT DOGE/USDT --timeframe 1h --interval 60
    python ./backend/scheduler.py --symbols BTC/USDT ETH/USDT SOL/USDT SUI/USDT BNB/USDT 币安人生/USDT DOGE/USDT --timeframe 4h --interval 240
    python ./backend/scheduler.py --symbols BTC/USDT ETH/USDT SOL/USDT SUI/USDT BNB/USDT 币安人生/USDT DOGE/USDT --timeframe 1d --interval 1440
"""
import os
import sys
import argparse
import subprocess
import time
from datetime import datetime

import schedule


def run_fetch(symbol: str, timeframe: str):
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    fetch_script = os.path.join(backend_dir, "fetch_crypto_data.py")
    cmd = [
        sys.executable,
        fetch_script,
        "--mode", "ohlcv",
        "--symbol", symbol,
        "--timeframe", timeframe,
    ]
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 开始执行数据更新 ...")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, cwd=backend_dir)
        print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
    except subprocess.CalledProcessError as e:
        print(f"[ERR] 执行失败: {e}", file=sys.stderr)
        print(e.stdout)
        print(e.stderr, file=sys.stderr)


def run_fetch_batch(symbols: list, timeframe: str):
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 开始执行数据更新，目标交易对: {symbols}")
    for symbol in symbols:
        run_fetch(symbol, timeframe)
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 本次更新结束")


def main():
    parser = argparse.ArgumentParser(description="定时更新加密货币 OHLCV 数据")
    parser.add_argument('--symbols', '--symbol', nargs='+', default=['BTC/USDT'], dest='symbols', help='交易对列表，如 BTC/USDT ETH/USDT')
    parser.add_argument('--timeframe', type=str, default='4h', choices=['1h', '4h', '1d'], help='K线周期, 仅支持 1h 或 4h 或 1d')
    parser.add_argument('--interval', type=int, default=300, help='执行间隔（分钟）')
    args = parser.parse_args()

    schedule.every(args.interval).minutes.do(run_fetch_batch, args.symbols, args.timeframe)

    print(f"定时任务已启动：每 {args.interval} 分钟更新 {args.symbols} {args.timeframe} 数据")
    print("按 Ctrl+C 停止")

    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == '__main__':
    main()
