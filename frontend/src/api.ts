import axios from "axios";

const API_BASE = "http://localhost:8000";

const api = axios.create({
  baseURL: API_BASE,
  timeout: 120000,
});

export interface FileInfo {
  name: string;
  path: string;
  type: string;
  size: number;
  modified: string;
}

export interface FileData {
  success: boolean;
  filename: string;
  total_rows: number;
  columns: string[];
  data: Record<string, any>[];
  message?: string;
}

export interface FetchRequest {
  symbol: string;
  timeframe: string;
}

export interface AnalyzeRequest {
  symbol: string;
  timeframe: string;
  use_deepseek: boolean;
}

export interface SchedulerStartRequest {
  symbols: string[];
  mode: string;
  timeframe: string;
  interval: number;
}

export interface SchedulerTask {
  task_id: string;
  running: boolean;
  config: {
    symbols: string[];
    mode: string;
    timeframe: string;
    interval: number;
  };
  logs: string[];
}

export interface StrategyInfo {
  name: string;
  description: string;
  params_schema: Record<string, {
    type: string;
    default: number | string;
    min?: number;
    max?: number;
    label: string;
  }>;
}

export interface BacktestRequest {
  symbol: string;
  timeframe: string;
  start_date?: string;
  end_date?: string;
  strategy: string;
  strategy_params: Record<string, number | string>;
  initial_capital: number;
}

export interface BacktestSummary {
  initial_capital: number;
  final_equity: number;
  total_return_pct: number;
  annual_return_pct: number;
  max_drawdown_pct: number;
  total_trades: number;
  win_trades: number;
  lose_trades: number;
  win_rate_pct: number;
  profit_factor: number;
  sharpe_ratio: number;
}

export interface TradeRecord {
  entry_time: string;
  entry_price: number;
  exit_time: string;
  exit_price: number;
  direction: string;
  pnl: number;
  pnl_pct: number;
}

export interface EquityPoint {
  time: string;
  equity: number;
  price: number;
}

export interface BacktestResult {
  success: boolean;
  message?: string;
  summary: BacktestSummary;
  equity_curve: EquityPoint[];
  trades: TradeRecord[];
}

export const listFiles = () => api.get<{ files: FileInfo[] }>("/api/files");

export const readFile = (filename: string, limit = 1000) =>
  api.get<FileData>(`/api/files/${encodeURIComponent(filename)}?limit=${limit}`);

export const fetchData = (req: FetchRequest) =>
  api.post<{ success: boolean; output: string; error: string }>("/api/fetch", req);

export const analyzeData = (req: AnalyzeRequest) =>
  api.post<{ success: boolean; output: string; error: string }>("/api/analyze", req);

export const schedulerCreate = (req: SchedulerStartRequest) =>
  api.post<{ success: boolean; message: string; task_id: string }>("/api/scheduler/tasks", req);

export const schedulerStopTask = (taskId: string) =>
  api.post<{ success: boolean; message: string }>(`/api/scheduler/tasks/${taskId}/stop`);

export const schedulerDeleteTask = (taskId: string) =>
  api.delete<{ success: boolean; message: string }>(`/api/scheduler/tasks/${taskId}`);

export const schedulerListTasks = () =>
  api.get<{ tasks: SchedulerTask[] }>("/api/scheduler/tasks");

export const listStrategies = () =>
  api.get<{ strategies: StrategyInfo[] }>("/api/strategies");

export const runBacktest = (req: BacktestRequest) =>
  api.post<BacktestResult>("/api/backtest", req);
