import React, { useEffect, useState } from "react";
import {
  Card,
  Button,
  Form,
  Input,
  Select,
  InputNumber,
  message,
  Typography,
  Space,
  Spin,
  Table,
  Modal,
  Tag,
  Alert,
  Divider,
} from "antd";
import { SettingOutlined, PlusOutlined, EditOutlined, DeleteOutlined, MinusCircleOutlined } from "@ant-design/icons";
import { listStrategies, createStrategy, updateStrategy, deleteStrategy } from "../api";
import type { StrategyInfo } from "../api";

const { Title, Text } = Typography;

const StrategyPanel: React.FC = () => {
  const [strategies, setStrategies] = useState<StrategyInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingStrategy, setEditingStrategy] = useState<StrategyInfo | null>(null);
  const [form] = Form.useForm();

  useEffect(() => {
    loadStrategies();
  }, []);

  const loadStrategies = async () => {
    setLoading(true);
    try {
      const res = await listStrategies();
      setStrategies(res.data.strategies);
    } catch (error) {
      message.error("获取策略列表失败");
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = () => {
    setEditingStrategy(null);
    form.resetFields();
    setModalVisible(true);
  };

  const handleEdit = (strategy: StrategyInfo) => {
    setEditingStrategy(strategy);
    
    // 将参数对象转换为数组格式，以便Form.List显示
    const paramsArray = Object.entries(strategy.params_schema || {}).map(([key, meta]: [string, any]) => ({
      key,
      label: meta.label || key,
      default: meta.default || 0,
      min: meta.min !== undefined ? meta.min : 0,
      max: meta.max !== undefined ? meta.max : 100,
    }));
    
    form.setFieldsValue({
      name: strategy.name,
      description: strategy.description,
      type: strategy.type || 'spot',
      params_schema: paramsArray,
    });
    setModalVisible(true);
  };

  const handleDelete = async (name: string) => {
    Modal.confirm({
      title: '确认删除',
      content: `确定要删除策略 "${name}" 吗？`,
      onOk: async () => {
        try {
          await deleteStrategy(name);
          message.success("策略删除成功");
          loadStrategies();
        } catch (error) {
          message.error("删除策略失败");
        }
      },
    });
  };

  const handleSubmit = async (values: any) => {
    try {
      // 将参数列表转换为对象格式
      const paramsSchema: Record<string, any> = {};
      if (values.params_schema && Array.isArray(values.params_schema)) {
        values.params_schema.forEach((param: any) => {
          if (param.key) {
            paramsSchema[param.key] = {
              type: "int",
              default: param.default || 0,
              min: param.min !== undefined ? param.min : 0,
              max: param.max !== undefined ? param.max : 100,
              label: param.label || param.key,
            };
          }
        });
      }
      
      const strategyData = {
        name: values.name,
        description: values.description,
        type: values.type,
        params_schema: paramsSchema,
      };
      
      if (editingStrategy) {
        await updateStrategy(editingStrategy.name, strategyData);
        message.success("策略更新成功");
      } else {
        await createStrategy(strategyData);
        message.success("策略创建成功");
      }
      setModalVisible(false);
      loadStrategies();
    } catch (error) {
      message.error(editingStrategy ? "更新策略失败" : "创建策略失败");
    }
  };

  const columns = [
    {
      title: '策略名称',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
    },
    {
      title: '类型',
      dataIndex: 'type',
      key: 'type',
      render: (type: string) => (
        <Tag color={type === 'futures' ? 'blue' : 'green'}>
          {type === 'futures' ? '合约' : '现货'}
        </Tag>
      ),
    },
    {
      title: '参数',
      key: 'params',
      render: (_: any, record: StrategyInfo) => (
        <div>
          {Object.entries(record.params_schema || {}).map(([key, meta]: [string, any]) => (
            <div key={key}>
              <Text strong>{meta.label}:</Text> {meta.default} ({meta.min}-{meta.max})
            </div>
          ))}
        </div>
      ),
    },
    {
      title: '操作',
      key: 'action',
      render: (_: any, record: StrategyInfo) => (
        <Space size="small">
          <Button 
            icon={<EditOutlined />} 
            onClick={() => handleEdit(record)}
            size="small"
          >
            编辑
          </Button>
          <Button 
            icon={<DeleteOutlined />} 
            danger
            onClick={() => handleDelete(record.name)}
            size="small"
          >
            删除
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <Title level={4}>
        <SettingOutlined /> 策略管理
      </Title>

      <Card 
        title="策略列表" 
        extra={
          <Button 
            type="primary" 
            icon={<PlusOutlined />} 
            onClick={handleCreate}
          >
            新建策略
          </Button>
        }
        style={{ marginBottom: 16 }}
      >
        <Spin spinning={loading}>
          <Table
            dataSource={strategies.map((s, idx) => ({ ...s, key: idx }))}
            columns={columns}
            pagination={{ pageSize: 10 }}
            size="small"
          />
        </Spin>
      </Card>

      <Modal
        title={editingStrategy ? "编辑策略" : "新建策略"}
        open={modalVisible}
        onCancel={() => setModalVisible(false)}
        footer={null}
        width={700}
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleSubmit}
        >
          <Form.Item
            name="name"
            label="策略名称"
            rules={[{ required: true, message: '请输入策略名称' }]}
          >
            <Input disabled={!!editingStrategy} />
          </Form.Item>

          <Form.Item
            name="description"
            label="策略描述"
            rules={[{ required: true, message: '请输入策略描述' }]}
          >
            <Input.TextArea rows={3} />
          </Form.Item>

          <Form.Item
            name="type"
            label="策略类型"
            rules={[{ required: true, message: '请选择策略类型' }]}
            initialValue="spot"
          >
            <Select>
              <Select.Option value="spot">现货</Select.Option>
              <Select.Option value="futures">合约</Select.Option>
            </Select>
          </Form.Item>

          <Divider orientation="left">策略参数配置</Divider>
          
          <Form.List name="params_schema">
            {(fields, { add, remove }) => (
              <>
                {fields.map(({ key, name, ...restField }) => (
                  <Space key={key} style={{ display: 'flex', marginBottom: 8 }} align="baseline">
                    <Form.Item
                      {...restField}
                      name={[name, 'key']}
                      rules={[{ required: true, message: '请输入参数名' }]}
                    >
                      <Input placeholder="参数名(如: period)" style={{ width: 150 }} />
                    </Form.Item>
                    <Form.Item
                      {...restField}
                      name={[name, 'label']}
                      rules={[{ required: true, message: '请输入参数标签' }]}
                    >
                      <Input placeholder="显示名称(如: RSI周期)" style={{ width: 150 }} />
                    </Form.Item>
                    <Form.Item
                      {...restField}
                      name={[name, 'default']}
                      rules={[{ required: true, message: '请输入默认值' }]}
                    >
                      <InputNumber placeholder="默认值" style={{ width: 100 }} min={0} />
                    </Form.Item>
                    <Form.Item
                      {...restField}
                      name={[name, 'min']}
                    >
                      <InputNumber placeholder="最小值" style={{ width: 100 }} min={0} />
                    </Form.Item>
                    <Form.Item
                      {...restField}
                      name={[name, 'max']}
                    >
                      <InputNumber placeholder="最大值" style={{ width: 100 }} min={0} />
                    </Form.Item>
                    <MinusCircleOutlined onClick={() => remove(name)} />
                  </Space>
                ))}
                <Form.Item>
                  <Button type="dashed" onClick={() => add()} block icon={<PlusOutlined />}>
                    添加参数
                  </Button>
                </Form.Item>
              </>
            )}
          </Form.List>

          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit">
                {editingStrategy ? "更新" : "创建"}
              </Button>
              <Button onClick={() => setModalVisible(false)}>
                取消
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default StrategyPanel;