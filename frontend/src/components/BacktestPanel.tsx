import React, { useEffect, useState } from "react";
import {
  Card,
  Button,
  Select,
  DatePicker,
  InputNumber,
  message,
  Typography,
  Space,
  Spin,
  Table,
  Row,
  Col,
  Statistic,
  Tag,
  Alert,
  Empty,
} from "antd";
import { LineChartOutlined, PlayCircleOutlined } from "@ant-design/icons";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { listFiles, listStrategies, runBacktest } from "../api";
import type { StrategyInfo, BacktestResult } from "../api";

const { Title, Text } = Typography;

function extractSymbolsFromFiles(files: { name: string }[]): string[] {
  const symbols = new Set<string>();
  for (const f of files) {
    const name = f.name;
    const markers = ["_ohlcv_", "_ticker", "_orderbook", "_trades"];
    for (const m of markers) {
      const idx = name.indexOf(m);
      if (idx !== -1) {
        const raw = name.substring(0, idx);
        symbols.add(raw.replace(/_/g, "/"));
        break;
      }
    }
  }
  return Array.from(symbols).sort();
}

const BacktestPanel: React.FC = () => {
  const [symbols, setSymbols] = useState<string[]>([]);
  const [symbol, setSymbol] = useState<string>("BTC/USDT");
  const [timeframe, setTimeframe] = useState<string>("1h");
  const [strategies, setStrategies] = useState<StrategyInfo[]>([]);
  const [strategy, setStrategy] = useState<string>("sma_cross");
  const [strategyParams, setStrategyParams] = useState<Record<string, number>>({});
  const [dateRange, setDateRange] = useState<[string | null, string | null]>([null, null]);
  const [initialCapital, setInitialCapital] = useState<number>(10000);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [error, setError] = useState<string>("");

  useEffect(() => {
    listFiles()
      .then((res) => {
        const syms = extractSymbolsFromFiles(res.data.files);
        setSymbols(syms);
        if (syms.length > 0 && !syms.includes(symbol)) {
          setSymbol(syms[0]);
        }
      })
      .catch(() => message.error("获取文件列表失败"));

    listStrategies()
      .then((res) => {
        setStrategies(res.data.strategies);
        if (res.data.strategies.length > 0) {
          const first = res.data.strategies[0];
          setStrategy(first.name);
          initStrategyParams(first);
        }
      })
      .catch(() => message.error("获取策略列表失败"));
  }, []);

  const initStrategyParams = (s: StrategyInfo) => {
    const params: Record<string, number> = {};
    Object.entries(s.params_schema).forEach(([key, meta]) => {
      params[key] = meta.default as number;
    });
    setStrategyParams(params);
  };

  const handleStrategyChange = (val: string) => {
    setStrategy(val);
    const s = strategies.find((x) => x.name === val);
    if (s) {
      initStrategyParams(s);
    }
  };

  const handleParamChange = (key: string, val: number | null) => {
    if (val === null) return;
    setStrategyParams((prev) => ({ ...prev, [key]: val }));
  };

  const handleRunBacktest = async () => {
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const res = await runBacktest({
        symbol,
        timeframe,
        start_date: dateRange[0] || undefined,
        end_date: dateRange[1] || undefined,
        strategy,
        strategy_params: strategyParams,
        initial_capital: initialCapital,
      });
      if (res.data.success) {
        setResult(res.data);
        message.success("回测完成");
      } else {
        setError(res.data.message || "回测失败");
      }
    } catch (e: any) {
      setError(e.message || "请求失败");
    } finally {
      setLoading(false);
    }
  };

  const currentStrategy = strategies.find((s) => s.name === strategy);

  const renderParamInputs = () => {
    if (!currentStrategy) return null;
    return (
      <Space wrap>
        {Object.entries(currentStrategy.params_schema).map(([key, meta]) => (
          <div key={key}>
            <Text strong style={{ marginRight: 8 }}>
              {meta.label}:
            </Text>
            <InputNumber
              min={meta.min}
              max={meta.max}
              value={strategyParams[key] ?? (meta.default as number)}
              onChange={(val) => handleParamChange(key, val)}
              style={{ width: 120 }}
            />
          </div>
        ))}
      </Space>
    );
  };

  const statCards = result
    ? [
        {
          title: "总收益率",
          value: result.summary.total_return_pct,
          suffix: "%",
          color: result.summary.total_return_pct >= 0 ? "#cf1322" : "#389e0d",
        },
        {
          title: "年化收益率",
          value: result.summary.annual_return_pct,
          suffix: "%",
          color: undefined,
        },
        {
          title: "最大回撤",
          value: result.summary.max_drawdown_pct,
          suffix: "%",
          color: "#faad14",
        },
        {
          title: "交易次数",
          value: result.summary.total_trades,
          suffix: "次",
          color: undefined,
        },
        {
          title: "胜率",
          value: result.summary.win_rate_pct,
          suffix: "%",
          color: undefined,
        },
        {
          title: "夏普比率",
          value: result.summary.sharpe_ratio,
          suffix: "",
          color: undefined,
        },
        {
          title: "盈亏比",
          value: result.summary.profit_factor,
          suffix: "",
          color: undefined,
        },
        {
          title: "最终权益",
          value: result.summary.final_equity,
          suffix: " USDT",
          color: undefined,
        },
      ]
    : [];

  const tradeColumns = [
    { title: "开仓时间", dataIndex: "entry_time", key: "entry_time" },
    { title: "平仓时间", dataIndex: "exit_time", key: "exit_time" },
    {
      title: "方向",
      dataIndex: "direction",
      key: "direction",
      render: (v: string) => <Tag color="blue">{v === "long" ? "做多" : v}</Tag>,
    },
    {
      title: "开仓价",
      dataIndex: "entry_price",
      key: "entry_price",
      render: (v: number) => v.toFixed(2),
    },
    {
      title: "平仓价",
      dataIndex: "exit_price",
      key: "exit_price",
      render: (v: number) => v.toFixed(2),
    },
    {
      title: "盈亏",
      dataIndex: "pnl",
      key: "pnl",
      render: (v: number) => (
        <Text style={{ color: v >= 0 ? "#cf1322" : "#389e0d" }}>
          {v >= 0 ? `+${v.toFixed(2)}` : v.toFixed(2)}
        </Text>
      ),
    },
    {
      title: "盈亏%",
      dataIndex: "pnl_pct",
      key: "pnl_pct",
      render: (v: number) => (
        <Text style={{ color: v >= 0 ? "#cf1322" : "#389e0d" }}>
          {v >= 0 ? `+${v.toFixed(2)}%` : `${v.toFixed(2)}%`}
        </Text>
      ),
    },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <Title level={4}>
        <LineChartOutlined /> 策略回测
      </Title>

      <Card title="回测参数配置" style={{ marginBottom: 16 }}>
        <Space direction="vertical" size="middle" style={{ width: "100%" }}>
          <Space wrap>
            <div>
              <Text strong style={{ marginRight: 8 }}>
                交易对:
              </Text>
              <Select
                value={symbol}
                onChange={setSymbol}
                style={{ width: 160 }}
                options={symbols.map((s) => ({ label: s, value: s }))}
              />
            </div>
            <div>
              <Text strong style={{ marginRight: 8 }}>
                K线周期:
              </Text>
              <Select
                value={timeframe}
                onChange={setTimeframe}
                style={{ width: 120 }}
                options={[
                  { label: "1小时", value: "1h" },
                  { label: "4小时", value: "4h" },
                  { label: "1天", value: "1d" },
                ]}
              />
            </div>
            <div>
              <Text strong style={{ marginRight: 8 }}>
                策略:
              </Text>
              <Select
                value={strategy}
                onChange={handleStrategyChange}
                style={{ width: 180 }}
                options={strategies.map((s) => ({
                  label: s.description,
                  value: s.name,
                }))}
              />
            </div>
            <div>
              <Text strong style={{ marginRight: 8 }}>
                开始:
              </Text>
              <DatePicker
                format="YYYY-MM-DD"
                placeholder="开始日期"
                onChange={(_, date) =>
                  setDateRange((prev) => [date, prev[1]])
                }
              />
            </div>
            <div>
              <Text strong style={{ marginRight: 8 }}>
                结束:
              </Text>
              <DatePicker
                format="YYYY-MM-DD"
                placeholder="结束日期"
                onChange={(_, date) =>
                  setDateRange((prev) => [prev[0], date])
                }
              />
            </div>
            <div>
              <Text strong style={{ marginRight: 8 }}>
                初始资金:
              </Text>
              <InputNumber
                min={100}
                value={initialCapital}
                onChange={(val) => setInitialCapital(val || 10000)}
                style={{ width: 160 }}
                addonAfter="USDT"
              />
            </div>
          </Space>

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
            <div>
              <Text strong style={{ marginRight: 8 }}>
                策略参数:
              </Text>
              {renderParamInputs()}
            </div>

            <Button
              type="primary"
              icon={<PlayCircleOutlined />}
              onClick={handleRunBacktest}
              loading={loading}
              size="large"
            >
              运行回测
            </Button>
          </div>
        </Space>
      </Card>

      {error && (
        <Alert
          message="回测失败"
          description={error}
          type="error"
          showIcon
          style={{ marginBottom: 16 }}
        />
      )}

      <div style={{ flex: 1, overflowY: 'auto', overflowX: 'hidden' }}>
        <Spin spinning={loading}>
          {result && (
            <div>
              <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
                {statCards.map((card) => (
                  <Col xs={12} sm={8} md={6} lg={6} xl={3} key={card.title}>
                    <Card size="small">
                      <Statistic
                        title={card.title}
                        value={card.value}
                        suffix={card.suffix}
                        valueStyle={{ color: card.color }}
                        precision={2}
                      />
                    </Card>
                  </Col>
                ))}
              </Row>

              <Card title="权益曲线" style={{ marginBottom: 16 }}>
                {result.equity_curve.length > 0 ? (
                  <ResponsiveContainer width="100%" height={400}>
                    <AreaChart data={result.equity_curve}>
                      <defs>
                        <linearGradient id="colorEquity" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#1890ff" stopOpacity={0.3} />
                          <stop offset="95%" stopColor="#1890ff" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis
                        dataKey="time"
                        tickFormatter={(val: string) => val.slice(5, 16)}
                        minTickGap={30}
                      />
                      <YAxis domain={["auto", "auto"]} />
                      <Tooltip
                        formatter={(value) => [Number(value).toFixed(2), "权益"]}
                        labelFormatter={(label) => String(label)}
                      />
                      <Legend />
                      <Area
                        type="monotone"
                        dataKey="equity"
                        stroke="#1890ff"
                        fillOpacity={1}
                        fill="url(#colorEquity)"
                        dot={false}
                        name="权益"
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                ) : (
                  <Empty description="无权益曲线数据" />
                )}
              </Card>

              <Card title="交易记录">
                <Table
                  dataSource={result.trades.map((t, idx) => ({ ...t, key: idx }))}
                  columns={tradeColumns}
                  pagination={{ pageSize: 10 }}
                  size="small"
                />
              </Card>
            </div>
          )}
        </Spin>
      </div>
    </div>
  );
};

export default BacktestPanel;
