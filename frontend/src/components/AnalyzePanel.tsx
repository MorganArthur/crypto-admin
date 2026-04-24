import React, { useEffect, useState } from "react";
import {
  Card,
  Button,
  Select,
  message,
  Typography,
  Space,
  Alert,
  Tag,
} from "antd";
import { BarChartOutlined, CopyOutlined } from "@ant-design/icons";
import { analyzeData, listFiles } from "../api";

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

const AnalyzePanel: React.FC = () => {
  const [symbol, setSymbol] = useState<string>("BTC/USDT");
  const [timeframe, setTimeframe] = useState<string>("1h");
  const [analyzing, setAnalyzing] = useState(false);
  const [output, setOutput] = useState<string>("");
  const [error, setError] = useState<string>("");
  const [symbols, setSymbols] = useState<string[]>([]);

  const extractAdvice = (text: string) => {
    const lines = text.split("\n");
    const advice: Record<string, string> = {};
    let inAdvice = false;
    for (const line of lines) {
      if (line.includes("DeepSeek 交易建议")) {
        inAdvice = true;
        continue;
      }
      if (inAdvice && line.trim().startsWith("=")) {
        if (Object.keys(advice).length > 0) {
          break;
        }
        continue;
      }
      if (inAdvice) {
        const m = line.match(/^\s*(.+?)\s*[:：]\s*(.+?)\s*$/);
        if (m) {
          advice[m[1].trim()] = m[2].trim();
        }
      }
    }
    return Object.keys(advice).length > 0 ? advice : null;
  };

  useEffect(() => {
    listFiles()
      .then((res) => {
        const syms = extractSymbolsFromFiles(res.data.files);
        setSymbols(syms);
        if (syms.length > 0 && !syms.includes(symbol)) {
          setSymbol(syms[0]);
        }
      })
      .catch(() => {
        message.error("获取文件列表失败");
      });
  }, []);

  const handleAnalyze = async () => {
    setAnalyzing(true);
    setOutput("");
    setError("");
    try {
      const res = await analyzeData({ symbol, timeframe, use_deepseek: true });
      setOutput(res.data.output || "分析完成，无输出");
      if (res.data.error) {
        setError(res.data.error);
      }
    } catch (e: any) {
      setError(e.message || "请求失败");
    } finally {
      setAnalyzing(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <Title level={4}>
        <BarChartOutlined /> 数据分析
      </Title>

      <Card title="操作面板" style={{ marginBottom: 16 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <Space>
            <div>
              <Text strong>交易对:</Text>
              <Select
                value={symbol}
                onChange={setSymbol}
                style={{ width: 160, marginLeft: 8 }}
                options={symbols.map((s) => ({ label: s, value: s }))}
              />
            </div>
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
          </Space>

          <Button
            type="primary"
            icon={<BarChartOutlined />}
            onClick={handleAnalyze}
            loading={analyzing}
          >
            运行分析程序
          </Button>
        </div>
      </Card>

      {error && (
        <Alert
          message="错误"
          description={error}
          type="error"
          showIcon
          style={{ marginBottom: 16 }}
        />
      )}

      <div style={{ flex: 1, overflow: 'hidden' }}>
        <Card
          title="输出结果"
          extra={
            output ? (
              <Button
                size="small"
                icon={<CopyOutlined />}
                onClick={() => {
                  navigator.clipboard.writeText(output);
                  message.success("已复制到剪贴板");
                }}
              >
                复制
              </Button>
            ) : null
          }
          loading={analyzing}
          style={{ height: '100%', display: 'flex', flexDirection: 'column' }}
          styles={{ body: { flex: 1, overflow: 'auto' } }}
        >
          {output ? (
            <div>
              {(() => {
                const advice = extractAdvice(output);
                if (advice) {
                  const directionColor =
                    advice["交易方向"]?.includes("多")
                      ? "red"
                      : advice["交易方向"]?.includes("空")
                      ? "green"
                      : "default";
                  return (
                    <div style={{ marginBottom: 16 }}>
                      <Card
                        size="small"
                        title={<span style={{ fontWeight: 600 }}>DeepSeek 交易建议</span>}
                        style={{
                          borderLeft: `4px solid ${directionColor === "red" ? "#cf1322" : directionColor === "green" ? "#389e0d" : "#8c8c8c"}`,
                        }}
                      >
                        <Space size="large" wrap>
                          <div>
                            <Text type="secondary">交易方向</Text>
                            <div>
                              <Tag color={directionColor} style={{ fontSize: 14, padding: "2px 8px" }}>
                                {advice["交易方向"] || "-"}
                              </Tag>
                            </div>
                          </div>
                          <div>
                            <Text type="secondary">建议开仓价</Text>
                            <div>
                              <Text strong style={{ fontSize: 16 }}>
                                {advice["建议开仓价"] || "-"}
                              </Text>
                            </div>
                          </div>
                          <div>
                            <Text type="secondary">止盈价</Text>
                            <div>
                              <Text strong style={{ fontSize: 16, color: "#cf1322" }}>
                                {advice["建议止盈价"] || "-"}
                              </Text>
                            </div>
                          </div>
                          <div>
                            <Text type="secondary">止损价</Text>
                            <div>
                              <Text strong style={{ fontSize: 16, color: "#389e0d" }}>
                                {advice["建议止损价"] || "-"}
                              </Text>
                            </div>
                          </div>
                        </Space>
                        {advice["理由"] && (
                          <div style={{ marginTop: 12 }}>
                            <Text type="secondary">理由：</Text>
                            <Text>{advice["理由"]}</Text>
                          </div>
                        )}
                      </Card>
                    </div>
                  );
                }
                return null;
              })()}
              <pre
                style={{
                  background: "#f6f8fa",
                  padding: 16,
                  borderRadius: 6,
                  whiteSpace: "pre-wrap",
                  wordWrap: "break-word",
                  fontFamily: "monospace",
                  fontSize: 13,
                  margin: 0,
                }}
              >
                {output}
              </pre>
            </div>
          ) : (
            <Text type="secondary">点击上方按钮执行操作，结果将显示在这里</Text>
          )}
        </Card>
      </div>
    </div>
  );
};

export default AnalyzePanel;
