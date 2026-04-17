# 架构说明

## 目标

做一个 AI 辅助的 OKX 永续交易副驾驶（copilot），对执行边界做严格约束。

## 系统边界

1. Hummingbot 层负责
- OKX 连通性
- 特定交易所的订单转换
- 订单生命周期管理
- 持仓同步
- 最终调用执行接口

2. 硬风控层负责
- 最大名义金额检查
- 最大杠杆检查
- 日内回撤硬停
- 滑点上限检查
- 拒绝不支持的连接器 / 格式异常的 proposal

3. AI 层负责
- 行情 regime 判断
- 定性的交易点评
- 给 confidence / caution 打分
- 建议暂停或降低交易频率

4. AI 层**明确不负责**
- 绕过风险上限
- 在不改代码 / 配置的情况下动杠杆上限
- 在 proposal 被拒后强行下单
- 关闭 kill switch

## MVP 请求流

1. 策略或运营者创建 `TradeProposal`
2. 控制平面读取 `AccountState`
3. `evaluate_trade(...)` 返回 `RiskDecision`
4. 拒绝 → 交易终止，拒绝原因写日志
5. 通过 → 可选附带 AI 定性点评
6. 通过的请求后续由 Hummingbot API 实际执行（后续阶段）

## 设计选择：AI 只是顾问，不是主权者

这是刻意为之。LLM 擅长综合和上下文，但不适合做资金的最终守门员。所以代码里把 AI 输出当成"建议元数据"，除非未来有经过独立评审的工作流才允许受限的自主权。

## 初期市场范围

- 交易所：OKX
- 连接器：`okx_perpetual`
- 合约：`BTC-USDT-SWAP`
- 持仓方式：单边、单合约、只开极小仓位

## 当前已实现的服务

- `hbot_client.py` — 带鉴权的 Hummingbot API 封装
- `account_sync.py` — 账户和敞口快照拉取

## 下一阶段要补的服务

- `proposal_service.py` — 把策略输出转成 `TradeProposal`
- `audit_log.py` — 追加写的决策与执行日志
- `ai_review.py` — prompt 适配器 + 结构化顾问响应
- `execution_service.py` — 把通过风控的订单发到 Hummingbot 的交易端点
