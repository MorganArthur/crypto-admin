import { useState } from 'react'
import { Layout, Menu, Typography } from 'antd'
import {
  DatabaseOutlined,
  ClockCircleOutlined,
  BarChartOutlined,
  LineChartOutlined,
  SettingOutlined,
  SwapOutlined,
} from '@ant-design/icons'
import DataView from './components/DataView'
import SchedulerPanel from './components/SchedulerPanel'
import AnalyzePanel from './components/AnalyzePanel'
import BacktestPanel from './components/BacktestPanel'
import StrategyPanel from './components/StrategyPanel'
import FuturesBacktestPanel from './components/FuturesBacktestPanel'

const { Sider, Content } = Layout
const { Title } = Typography

type MenuKey = 'data' | 'scheduler' | 'analyze' | 'backtest' | 'strategy' | 'futures_backtest'

function App() {
  const [activeKey, setActiveKey] = useState<MenuKey>('data')

  const renderContent = () => {
    switch (activeKey) {
      case 'data':
        return <DataView />
      case 'scheduler':
        return <SchedulerPanel />
      case 'analyze':
        return <AnalyzePanel />
      case 'backtest':
        return <BacktestPanel />
      case 'strategy':
        return <StrategyPanel />
      case 'futures_backtest':
        return <FuturesBacktestPanel />
      default:
        return <DataView />
    }
  }

  return (
    <Layout style={{ height: '100vh' }}>
      <Sider theme="light" width={220} style={{ borderRight: '1px solid #f0f0f0' }}>
        <div style={{ padding: '16px', borderBottom: '1px solid #f0f0f0' }}>
          <Title level={5} style={{ margin: 0 }}>Crypto Admin</Title>
        </div>
        <Menu
          mode="inline"
          selectedKeys={[activeKey]}
          onClick={({ key }) => setActiveKey(key as MenuKey)}
          items={[
            {
              key: 'data',
              icon: <DatabaseOutlined />,
              label: '数据查看',
            },
            {
              key: 'scheduler',
              icon: <ClockCircleOutlined />,
              label: '定时任务',
            },
            {
              key: 'analyze',
              icon: <BarChartOutlined />,
              label: '数据分析',
            },
            {
              key: 'strategy',
              icon: <SettingOutlined />,
              label: '策略管理',
            },
            {
              key: 'backtest',
              icon: <LineChartOutlined />,
              label: '现货回测',
            },
            {
              key: 'futures_backtest',
              icon: <SwapOutlined />,
              label: '合约回测',
            },
          ]}
        />
      </Sider>
      <Layout style={{ display: 'flex', flexDirection: 'column' }}>
        <Content style={{ padding: 24, background: '#fff', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          {renderContent()}
        </Content>
      </Layout>
    </Layout>
  )
}

export default App
