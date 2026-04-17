# OKX + Hummingbot 部署备注

MVP 阶段默认的部署假设。

## 交易所目标

- 交易所：OKX
- 连接器 ID：`okx_perpetual`
- 第一个合约：`BTC-USDT-SWAP`

## 操作须知

根据 Hummingbot 的公开 OKX 文档，永续连接器用 `okx_perpetual`，并且 Hummingbot 要求 OKX 账户在连接前先按要求配置好。

MVP 阶段必须守住的几点：
- 第一个迭代只做 OKX 永续
- 使用单币种保证金模式
- 连接器重启前确认没有遗留的未平仓位
- 不开大杠杆，先在本地风控里加上限

## 推荐上线顺序

1. 给 OKX API key 配上最小必要权限
2. 把 Hummingbot 接到 `okx_perpetual`
3. 人工确认连接器 / 账户状态
4. 用 mock 的 proposal 跑本地风控引擎
5. 只有当决策日志看着对时，才接通 paper / 极小仓位的真实执行

## 凭据

永远不要把真实密钥提交到仓库。
只走本地环境变量或密钥管理工具。

本地最少需要的环境变量：
- `HBOT_ACCOUNT_NAME=primary`（或你实际的 Hummingbot 账户命名空间）
- `OKX_CONNECTOR_ID=okx_perpetual`
- `OKX_SYMBOL=BTC-USDT-SWAP`
- `HBOT_API_URL=http://localhost:8000`
- `HBOT_API_USERNAME=admin`
- `HBOT_API_PASSWORD=admin`

## 第一个合约策略

MVP 只交易一个合约：
- `BTC-USDT-SWAP`

满足以下条件之后才考虑扩到 ETH：
- 账户同步稳定
- 日志可信
- 拒绝 / 通过路径已经测过
