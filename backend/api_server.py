#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FastAPI 后端服务，为前端提供 RESTful API
功能：
  1. 列出/读取 CSV 数据文件
  2. 触发数据爬取
  3. 触发数据分析
  4. 管理定时任务（启动/停止/状态）

用法：
    uvicorn backend.api_server:app --reload --port 8000
"""

import os
import sys
import glob
import json
import subprocess
import threading
import time
import uuid
from datetime import datetime
from typing import List, Optional, Dict
from urllib.parse import unquote

from fastapi import FastAPI, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# 确保 backend 目录在路径中
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BACKEND_DIR, "data")

# 导入回测引擎
sys.path.insert(0, BACKEND_DIR)
from backtest_engine import BacktestEngine, create_strategy, get_strategy_names, get_strategy_info

app = FastAPI(title="Crypto Admin API", version="1.0.0")

# CORS 配置，允许前端访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===================== 定时任务管理器 =====================

class SchedulerManager:
    def __init__(self, task_id: str):
        self.task_id = task_id
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._running = False
        self._config = {
            "symbols": ["BTC/USDT"],
            "timeframe": "1h",
            "interval": 60,
        }
        self._logs: List[str] = []
        self._max_logs = 200

    def _add_log(self, msg: str):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = f"[{ts}] {msg}"
        self._logs.append(entry)
        if len(self._logs) > self._max_logs:
            self._logs = self._logs[-self._max_logs:]
        print(f"[Task {self.task_id}] {entry}")

    def _run_scheduler(self):
        import schedule
        scheduler = schedule.Scheduler()
        mode = self._config.get("mode", "ohlcv")
        timeframe = self._config.get("timeframe", "1h")

        def job():
            self._add_log(f"定时任务执行: {self._config['symbols']} [{mode}]")
            for symbol in self._config["symbols"]:
                if self._stop_event.is_set():
                    break
                result = run_fetch_script(symbol, mode, timeframe if mode == "ohlcv" else None)
                self._add_log(f"  {symbol} 结果: {'成功' if result.get('success') else '失败'}")

        scheduler.every(self._config["interval"]).minutes.do(job)
        self._add_log(f"调度器已启动: 每 {self._config['interval']} 分钟更新 {self._config['symbols']} [{mode}]")

        while not self._stop_event.is_set():
            scheduler.run_pending()
            time.sleep(1)

        self._add_log("调度器线程已退出")
        self._running = False

    def start(self, symbols: List[str], mode: str, timeframe: str, interval: int) -> dict:
        if self._running:
            return {"success": False, "message": "定时任务已在运行中"}

        self._config = {
            "symbols": symbols,
            "mode": mode,
            "timeframe": timeframe,
            "interval": interval,
        }
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self._running = True
        self._thread.start()
        return {"success": True, "message": "定时任务已启动"}

    def stop(self) -> dict:
        if not self._running:
            return {"success": False, "message": "定时任务未在运行"}
        self._stop_event.set()
        self._running = False
        return {"success": True, "message": "定时任务已停止"}

    def status(self) -> dict:
        return {
            "task_id": self.task_id,
            "running": self._running,
            "config": self._config,
            "logs": self._logs[-50:],
        }


class TaskRegistry:
    PERSIST_FILE = os.path.join(BACKEND_DIR, "scheduler_tasks.json")

    def __init__(self):
        self._tasks: Dict[str, SchedulerManager] = {}
        self._lock = threading.Lock()
        self._load()

    def _save(self):
        data = []
        with self._lock:
            for task_id, task in self._tasks.items():
                data.append({
                    "task_id": task_id,
                    "symbols": task._config["symbols"],
                    "mode": task._config.get("mode", "ohlcv"),
                    "timeframe": task._config["timeframe"],
                    "interval": task._config["interval"],
                    "running": task._running,
                })
        try:
            with open(self.PERSIST_FILE, "w", encoding="utf-8") as f:
                json.dump({"tasks": data}, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[TaskRegistry] 保存任务配置失败: {e}")

    def _load(self):
        if not os.path.exists(self.PERSIST_FILE):
            return
        try:
            with open(self.PERSIST_FILE, "r", encoding="utf-8") as f:
                payload = json.load(f)
            for item in payload.get("tasks", []):
                task_id = item["task_id"]
                task = SchedulerManager(task_id)
                task._config = {
                    "symbols": item["symbols"],
                    "mode": item.get("mode", "ohlcv"),
                    "timeframe": item["timeframe"],
                    "interval": item["interval"],
                }
                if item.get("running", False):
                    task._stop_event.clear()
                    task._thread = threading.Thread(target=task._run_scheduler, daemon=True)
                    task._running = True
                    task._thread.start()
                    task._add_log("服务重启后自动恢复任务")
                with self._lock:
                    self._tasks[task_id] = task
            print(f"[TaskRegistry] 已恢复 {len(self._tasks)} 个定时任务")
        except Exception as e:
            print(f"[TaskRegistry] 加载任务配置失败: {e}")

    def create(self, symbols: List[str], mode: str, timeframe: str, interval: int) -> dict:
        task_id = str(uuid.uuid4())[:8]
        task = SchedulerManager(task_id)
        result = task.start(symbols, mode, timeframe, interval)
        if result["success"]:
            with self._lock:
                self._tasks[task_id] = task
            self._save()
        return {**result, "task_id": task_id}

    def stop(self, task_id: str) -> dict:
        with self._lock:
            task = self._tasks.get(task_id)
        if not task:
            return {"success": False, "message": "任务不存在"}
        result = task.stop()
        if result["success"]:
            self._save()
        return result

    def remove(self, task_id: str) -> dict:
        with self._lock:
            task = self._tasks.get(task_id)
        if not task:
            return {"success": False, "message": "任务不存在"}
        if task._running:
            task.stop()
        with self._lock:
            del self._tasks[task_id]
        self._save()
        return {"success": True, "message": "任务已删除"}

    def list_tasks(self) -> List[dict]:
        with self._lock:
            return [task.status() for task in self._tasks.values()]

    def get_task(self, task_id: str) -> Optional[dict]:
        with self._lock:
            task = self._tasks.get(task_id)
        return task.status() if task else None


task_registry = TaskRegistry()


# ===================== 辅助函数 =====================

def run_fetch_script(symbol: str, mode: str = "ohlcv", timeframe: Optional[str] = None) -> dict:
    """调用 fetch_crypto_data.py 获取数据"""
    fetch_script = os.path.join(BACKEND_DIR, "fetch_crypto_data.py")
    cmd = [
        sys.executable,
        fetch_script,
        "--mode", mode,
        "--symbol", symbol,
    ]
    if mode == "ohlcv" and timeframe:
        cmd.extend(["--timeframe", timeframe])
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, cwd=BACKEND_DIR)
        return {"success": True, "stdout": result.stdout, "stderr": result.stderr}
    except subprocess.CalledProcessError as e:
        return {"success": False, "stdout": e.stdout, "stderr": e.stderr}


def run_analyze_script(symbol: str, timeframe: str, use_deepseek: bool = False) -> dict:
    """调用 analyze_data.py 分析数据"""
    analyze_script = os.path.join(BACKEND_DIR, "analyze_data.py")
    cmd = [
        sys.executable,
        analyze_script,
        "--symbol", symbol,
        "--timeframe", timeframe,
    ]
    if use_deepseek:
        cmd.append("--deepseek")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, cwd=BACKEND_DIR)
        return {"success": True, "stdout": result.stdout, "stderr": result.stderr}
    except subprocess.CalledProcessError as e:
        return {"success": False, "stdout": e.stdout, "stderr": e.stderr}


# ===================== Pydantic 模型 =====================

class FetchRequest(BaseModel):
    symbol: str = "BTC/USDT"
    timeframe: str = "1h"


class AnalyzeRequest(BaseModel):
    symbol: str = "BTC/USDT"
    timeframe: str = "1h"
    use_deepseek: bool = False


class SchedulerStartRequest(BaseModel):
    symbols: List[str] = ["BTC/USDT"]
    mode: str = "ohlcv"
    timeframe: str = "1h"
    interval: int = 60  # 分钟


class BacktestRequest(BaseModel):
    symbol: str = "BTC/USDT"
    timeframe: str = "1h"
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    strategy: str = "sma_cross"
    strategy_params: Dict = {}
    initial_capital: float = 10000.0


# ===================== API 路由 =====================

@app.get("/")
def root():
    return {"message": "Crypto Admin API", "docs": "/docs"}


# ---- 文件管理 ----

@app.get("/api/files")
def list_files():
    """列出 data 目录下所有 CSV 文件"""
    pattern = os.path.join(DATA_DIR, "*.csv")
    files = glob.glob(pattern)
    result = []
    for f in sorted(files):
        basename = os.path.basename(f)
        stat = os.stat(f)
        file_type = "unknown"
        if "_ohlcv_" in basename:
            file_type = "ohlcv"
        elif "_ticker" in basename:
            file_type = "ticker"
        elif "_orderbook" in basename:
            file_type = "orderbook"
        elif "_trades" in basename:
            file_type = "trades"
        result.append({
            "name": basename,
            "path": f,
            "type": file_type,
            "size": stat.st_size,
            "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
        })
    return {"files": result}


@app.get("/api/files/{filename}")
def read_file(filename: str, limit: int = Query(1000, ge=1, le=5000)):
    """读取指定 CSV 文件内容"""
    filename = unquote(filename)
    filepath = os.path.join(DATA_DIR, filename)
    if not os.path.exists(filepath):
        return {"success": False, "message": "文件不存在"}
    if not filepath.endswith(".csv"):
        return {"success": False, "message": "仅支持 CSV 文件"}

    import pandas as pd
    import numpy as np
    try:
        df = pd.read_csv(filepath)
    except Exception as e:
        return {"success": False, "message": f"读取文件失败: {str(e)}"}
    total = len(df)
    preview = df.tail(limit).replace({np.nan: None, np.inf: None, -np.inf: None})
    return {
        "success": True,
        "filename": filename,
        "total_rows": total,
        "columns": list(df.columns),
        "data": preview.to_dict("records"),
    }


# ---- 数据爬取 ----

@app.post("/api/fetch")
def fetch_data(req: FetchRequest):
    """手动触发数据爬取"""
    result = run_fetch_script(req.symbol, req.timeframe)
    return {"success": result["success"], "output": result["stdout"], "error": result["stderr"]}


# ---- 数据分析 ----

@app.post("/api/analyze")
def analyze_data(req: AnalyzeRequest):
    """手动触发数据分析"""
    result = run_analyze_script(req.symbol, req.timeframe, req.use_deepseek)
    return {"success": result["success"], "output": result["stdout"], "error": result["stderr"]}


# ---- 定时任务 ----

@app.post("/api/scheduler/tasks")
def scheduler_create(req: SchedulerStartRequest):
    """创建并启动新的定时任务"""
    return task_registry.create(req.symbols, req.mode, req.timeframe, req.interval)


@app.post("/api/scheduler/tasks/{task_id}/stop")
def scheduler_stop_task(task_id: str):
    """停止指定定时任务"""
    return task_registry.stop(task_id)


@app.delete("/api/scheduler/tasks/{task_id}")
def scheduler_delete_task(task_id: str):
    """删除指定定时任务"""
    return task_registry.remove(task_id)


@app.get("/api/scheduler/tasks")
def scheduler_list_tasks():
    """列出所有定时任务"""
    return {"tasks": task_registry.list_tasks()}


# ---- 回测 ----

@app.get("/api/strategies")
def list_strategies():
    """列出所有可用策略及其参数说明"""
    result = []
    for name in get_strategy_names():
        info = get_strategy_info(name)
        if info:
            result.append(info)
    return {"strategies": result}


@app.post("/api/backtest")
def run_backtest(req: BacktestRequest):
    """运行策略回测"""
    # 构建文件路径
    safe_symbol = req.symbol.replace("/", "_")
    filename = f"{safe_symbol}_ohlcv_{req.timeframe}.csv"
    filepath = os.path.join(DATA_DIR, filename)

    if not os.path.exists(filepath):
        return {"success": False, "message": f"数据文件不存在: {filename}"}

    try:
        strategy = create_strategy(req.strategy, **req.strategy_params)
        engine = BacktestEngine(
            data_path=filepath,
            start_date=req.start_date or None,
            end_date=req.end_date or None,
            initial_capital=req.initial_capital,
            commission_rate=0.001,
        )
        result = engine.run(strategy)
        return {
            "success": True,
            "summary": result.summary,
            "equity_curve": result.equity_curve,
            "trades": [t.to_dict() for t in result.trades],
        }
    except Exception as e:
        return {"success": False, "message": str(e)}


# ===================== 主入口 =====================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
