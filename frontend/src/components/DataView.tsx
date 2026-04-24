import React, { useEffect, useState } from "react";
import {
  Table,
  Card,
  Select,
  Button,
  Spin,
  message,
  Tag,
  Space,
  Typography,
} from "antd";
import { ReloadOutlined, DatabaseOutlined } from "@ant-design/icons";
import { listFiles, readFile } from "../api";
import type { FileInfo, FileData } from "../api";

const { Title } = Typography;

const DataView: React.FC = () => {
  const [files, setFiles] = useState<FileInfo[]>([]);
  const [selectedFile, setSelectedFile] = useState<string>("");
  const [fileData, setFileData] = useState<FileData | null>(null);
  const [loadingFiles, setLoadingFiles] = useState(false);
  const [loadingData, setLoadingData] = useState(false);

  const loadFiles = async () => {
    setLoadingFiles(true);
    try {
      const res = await listFiles();
      setFiles(res.data.files);
      if (res.data.files.length > 0 && !selectedFile) {
        setSelectedFile(res.data.files[0].name);
      }
    } catch (e) {
      message.error("获取文件列表失败");
    } finally {
      setLoadingFiles(false);
    }
  };

  const loadFileData = async (filename: string) => {
    if (!filename) return;
    setLoadingData(true);
    try {
      const res = await readFile(filename, 500);
      if (res.data.success) {
        setFileData(res.data);
      } else {
        message.error(res.data.message || "读取文件失败");
      }
    } catch (e) {
      message.error("读取文件失败");
    } finally {
      setLoadingData(false);
    }
  };

  useEffect(() => {
    loadFiles();
  }, []);

  useEffect(() => {
    if (selectedFile) {
      loadFileData(selectedFile);
    }
  }, [selectedFile]);

  const getTypeColor = (type: string) => {
    switch (type) {
      case "ohlcv":
        return "blue";
      case "ticker":
        return "green";
      case "orderbook":
        return "orange";
      case "trades":
        return "purple";
      default:
        return "default";
    }
  };

  const columns =
    fileData?.columns.map((col) => ({
      title: col,
      dataIndex: col,
      key: col,
      ellipsis: true,
      width: 140,
    })) || [];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <Title level={4}>
        <DatabaseOutlined /> 数据查看
      </Title>

      <Card style={{ marginBottom: 16 }}>
        <Space>
          <span>选择文件:</span>
          <Select
            style={{ width: 320 }}
            value={selectedFile}
            onChange={setSelectedFile}
            loading={loadingFiles}
            showSearch
            optionFilterProp="label"
            options={files.map((f) => ({
              label: f.name,
              value: f.name,
            }))}
          />
          <Button icon={<ReloadOutlined />} onClick={loadFiles} loading={loadingFiles}>
            刷新列表
          </Button>
        </Space>

        {selectedFile && (
          <div style={{ marginTop: 12 }}>
            <Space>
              <Tag color={getTypeColor(
                files.find((f) => f.name === selectedFile)?.type || ""
              )}>
                {files.find((f) => f.name === selectedFile)?.type?.toUpperCase() || "UNKNOWN"}
              </Tag>
              <span>
                共 <strong>{fileData?.total_rows ?? "-"}</strong> 行
              </span>
              <span>
                列: {fileData?.columns.join(", ") ?? "-"}
              </span>
            </Space>
          </div>
        )}
      </Card>

      <div style={{ flex: 1, overflow: 'auto' }}>
        <Spin spinning={loadingData}>
          {fileData && (
            <Card>
              <Table
                dataSource={fileData.data.map((row, idx) => ({ ...row, key: idx }))}
                columns={columns}
                pagination={{ pageSize: 20 }}
                scroll={{ x: "max-content" }}
                size="small"
              />
            </Card>
          )}
        </Spin>
      </div>
    </div>
  );
};

export default DataView;
