import React, { useEffect, useState } from "react";
import {
  Card,
  Button,
  Input,
  Select,
  InputNumber,
  message,
  Tag,
  List,
  Typography,
  Space,
  Spin,
  Divider,
  Row,
  Col,
  Popconfirm,
} from "antd";
import {
  PlusOutlined,
  PauseCircleOutlined,
  ClockCircleOutlined,
  ReloadOutlined,
  DeleteOutlined,
} from "@ant-design/icons";
import {
  schedulerCreate,
  schedulerStopTask,
  schedulerDeleteTask,
  schedulerListTasks,
} from "../api";
import type { SchedulerTask } from "../api";

const { Title, Text } = Typography;

const SchedulerPanel: React.FC = () => {
  const [tasks, setTasks] = useState<SchedulerTask[]>([]);
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);

  const [symbols, setSymbols] = useState<string[]>([
    "BTC/USDT",
    "ETH/USDT",
    "SOL/USDT",
    "SUI/USDT",
    "BNB/USDT",
    "币安人生/USDT",
    "DOGE/USDT",
  ]);
  const [mode, setMode] = useState<string>("ohlcv");
  const [timeframe, setTimeframe] = useState<string>("1h");
  const [intervalMinutes, setIntervalMinutes] = useState<number>(60);
  const [symbolInput, setSymbolInput] = useState<string>("");

  const fetchTasks = async () => {
    setLoading(true);
    try {
      const res = await schedulerListTasks();
      setTasks(res.data.tasks);
    } catch (e) {
      message.error("获取任务列表失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTasks();
    const timer = setInterval(fetchTasks, 3000);
    return () => clearInterval(timer);
  }, []);

  const handleCreate = async () => {
    if (symbols.length === 0) {
      message.warning("请至少添加一个交易对");
      return;
    }
    setCreating(true);
    try {
      const res = await schedulerCreate({ symbols, mode, timeframe, interval: intervalMinutes });
      if (res.data.success) {
        message.success(`${res.data.message} (ID: ${res.data.task_id})`);
      } else {
        message.warning(res.data.message);
      }
      await fetchTasks();
    } catch (e) {
      message.error("创建任务失败");
    } finally {
      setCreating(false);
    }
  };

  const handleStop = async (taskId: string) => {
    try {
      const res = await schedulerStopTask(taskId);
      if (res.data.success) {
        message.success(res.data.message);
      } else {
        message.warning(res.data.message);
      }
      await fetchTasks();
    } catch (e) {
      message.error("停止任务失败");
    }
  };

  const handleDelete = async (taskId: string) => {
    try {
      const res = await schedulerDeleteTask(taskId);
      if (res.data.success) {
        message.success(res.data.message);
      } else {
        message.warning(res.data.message);
      }
      await fetchTasks();
    } catch (e) {
      message.error("删除任务失败");
    }
  };

  const addSymbol = () => {
    const s = symbolInput.trim().toUpperCase();
    if (!s) return;
    if (!symbols.includes(s)) {
      setSymbols([...symbols, s]);
    }
    setSymbolInput("");
  };

  const removeSymbol = (s: string) => {
    setSymbols(symbols.filter((x) => x !== s));
  };

  return (
    <div>
      <Title level={4}>
        <ClockCircleOutlined /> 定时任务
      </Title>

      <Card title="新建任务" style={{ marginBottom: 16 }}>
        <Space direction="vertical" style={{ width: "100%" }}>
          <div>
            <Text strong>交易对:</Text>
            <div style={{ marginTop: 8 }}>
              <Space wrap>
                {symbols.map((s) => (
                  <Tag key={s} closable onClose={() => removeSymbol(s)} color="blue">
                    {s}
                  </Tag>
                ))}
              </Space>
            </div>
            <Space style={{ marginTop: 8 }}>
              <Input
                placeholder="如 BTC/USDT"
                value={symbolInput}
                onChange={(e) => setSymbolInput(e.target.value)}
                onPressEnter={addSymbol}
                style={{ width: 180 }}
              />
              <Button onClick={addSymbol}>添加</Button>
            </Space>
          </div>

          <Divider />

          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12 }}>
            <Space wrap>
              <div>
                <Text strong>数据类型:</Text>
                <Select
                  value={mode}
                  onChange={setMode}
                  style={{ width: 140, marginLeft: 8 }}
                  options={[
                    { label: "行情 (ticker)", value: "ticker" },
                    { label: "K线 (ohlcv)", value: "ohlcv" },
                    { label: "订单簿 (orderbook)", value: "orderbook" },
                    { label: "成交 (trades)", value: "trades" },
                  ]}
                />
              </div>
              {mode === "ohlcv" && (
                <div>
                  <Text strong>K线周期:</Text>
                  <Select
                    value={timeframe}
                    onChange={setTimeframe}
                    style={{ width: 120, marginLeft: 8 }}
                    options={[
                      { label: "1小时", value: "1h" },
                      { label: "4小时", value: "4h" },
                      { label: "1天", value: "1d" },
                    ]}
                  />
                </div>
              )}
              <div>
                <Text strong>间隔(分钟):</Text>
                <InputNumber
                  min={1}
                  max={1440}
                  value={intervalMinutes}
                  onChange={(v) => setIntervalMinutes(v || 60)}
                  style={{ width: 100, marginLeft: 8 }}
                />
              </div>
            </Space>

            <Space>
              <Button
                type="primary"
                icon={<PlusOutlined />}
                onClick={handleCreate}
                loading={creating}
              >
                添加定时任务
              </Button>
              <Button icon={<ReloadOutlined />} onClick={fetchTasks}>
                刷新列表
              </Button>
            </Space>
          </div>
        </Space>
      </Card>

      <Spin spinning={loading}>
        <Title level={5}>任务列表 ({tasks.length})</Title>
        <Row gutter={[16, 16]}>
          {tasks.map((task) => (
            <Col xs={24} md={12} lg={8} key={task.task_id}>
              <Card
                size="small"
                style={{ height: "100%", display: "flex", flexDirection: "column" }}
                bodyStyle={{ flex: 1, display: "flex", flexDirection: "column" }}
                title={
                  <Space>
                    <span>任务 {task.task_id}</span>
                    {task.running ? (
                      <Tag color="green">运行中</Tag>
                    ) : (
                      <Tag color="red">已停止</Tag>
                    )}
                  </Space>
                }
                extra={
                  <Space>
                    {task.running && (
                      <Button
                        size="small"
                        danger
                        icon={<PauseCircleOutlined />}
                        onClick={() => handleStop(task.task_id)}
                      >
                        停止
                      </Button>
                    )}
                    <Popconfirm
                      title="确认删除?"
                      description="删除后任务将不可恢复"
                      onConfirm={() => handleDelete(task.task_id)}
                      okText="删除"
                      cancelText="取消"
                    >
                      <Button size="small" icon={<DeleteOutlined />}>
                        删除
                      </Button>
                    </Popconfirm>
                  </Space>
                }
              >
                <div style={{ marginBottom: 8 }}>
                  <Text type="secondary">
                    每 <strong>{task.config.interval}</strong> 分钟更新{" "}
                    <strong>{task.config.symbols.join(", ")}</strong> 的{" "}
                    <strong>{task.config.mode?.toUpperCase?.() || "OHLCV"}</strong>
                    {task.config.mode === "ohlcv" && (
                      <span> <strong>{task.config.timeframe}</strong></span>
                    )}{" "}
                    数据
                  </Text>
                </div>

                <div
                  style={{
                    flex: 1,
                    background: "#f6f8fa",
                    padding: 10,
                    borderRadius: 4,
                    overflow: "auto",
                    fontFamily: "monospace",
                    fontSize: 12,
                    minHeight: 140,
                  }}
                >
                  {task.logs.length > 0 ? (
                    <List
                      dataSource={[...task.logs].reverse()}
                      renderItem={(log) => <div>{log}</div>}
                      size="small"
                    />
                  ) : (
                    <Text type="secondary">暂无日志</Text>
                  )}
                </div>
              </Card>
            </Col>
          ))}
        </Row>

        {tasks.length === 0 && (
          <Card style={{ marginTop: 16 }}>
            <Text type="secondary">暂无定时任务，请在上方添加</Text>
          </Card>
        )}
      </Spin>
    </div>
  );
};

export default SchedulerPanel;
