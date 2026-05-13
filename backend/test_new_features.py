#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试策略管理和合约回测API
"""

import requests
import json

BASE_URL = "http://localhost:8000"

def test_strategies_api():
    print("=== 测试策略管理API ===")
    
    # 1. 获取策略列表
    print("\n1. 获取策略列表...")
    response = requests.get(f"{BASE_URL}/api/strategies")
    if response.status_code == 200:
        strategies = response.json()["strategies"]
        print(f"   找到 {len(strategies)} 个策略:")
        for strategy in strategies:
            print(f"   - {strategy['name']}: {strategy['description']} (类型: {strategy.get('type', 'spot')})")
    else:
        print(f"   错误: {response.status_code}")
        return False
    
    # 2. 创建自定义策略
    print("\n2. 创建自定义策略...")
    new_strategy = {
        "name": "test_custom_strategy",
        "description": "测试自定义策略",
        "type": "futures",
        "params_schema": {
            "param1": {
                "type": "int",
                "default": 10,
                "min": 1,
                "max": 100,
                "label": "测试参数1"
            }
        }
    }
    
    response = requests.post(f"{BASE_URL}/api/strategies", json=new_strategy)
    if response.status_code == 200:
        result = response.json()
        print(f"   创建结果: {result}")
    else:
        print(f"   错误: {response.status_code}, {response.text}")
    
    # 3. 再次获取策略列表，确认新策略已添加
    print("\n3. 再次获取策略列表...")
    response = requests.get(f"{BASE_URL}/api/strategies")
    if response.status_code == 200:
        strategies = response.json()["strategies"]
        print(f"   现在共有 {len(strategies)} 个策略")
        strategy_names = [s["name"] for s in strategies]
        if "test_custom_strategy" in strategy_names:
            print("   ✓ 自定义策略已成功添加")
        else:
            print("   ✗ 自定义策略未找到")
    else:
        print(f"   错误: {response.status_code}")
    
    return True

def test_futures_backtest_api():
    print("\n=== 测试合约回测API ===")
    
    # 测试合约回测
    print("\n1. 运行合约回测...")
    backtest_request = {
        "symbol": "BTC/USDT",
        "timeframe": "1h",
        "strategy": "futures_sma_cross",
        "strategy_params": {
            "short_period": 10,
            "long_period": 30
        },
        "initial_capital": 10000,
        "leverage": 10
    }
    
    response = requests.post(f"{BASE_URL}/api/futures_backtest", json=backtest_request)
    if response.status_code == 200:
        result = response.json()
        if result.get("success"):
            print("   ✓ 合约回测成功")
            summary = result.get("summary", {})
            print(f"   总收益率: {summary.get('total_return_pct', 0):.2f}%")
            print(f"   交易次数: {summary.get('total_trades', 0)}")
            print(f"   胜率: {summary.get('win_rate_pct', 0):.2f}%")
        else:
            print(f"   回测失败: {result.get('message', '未知错误')}")
    else:
        print(f"   错误: {response.status_code}, {response.text}")

if __name__ == "__main__":
    try:
        test_strategies_api()
        test_futures_backtest_api()
        print("\n=== 测试完成 ===")
    except Exception as e:
        print(f"\n测试过程中出现错误: {e}")