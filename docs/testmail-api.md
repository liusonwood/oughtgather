# TestMail.app API 文档

> 来源：https://testmail.app/docs  
> 更新日期：2026-06-14

---

## 核心概念

### Namespace（命名空间）
- 全局唯一的标识符，例如 `acmeinc`
- 构成收件地址格式：`{namespace}.{tag}@inbox.testmail.app`
- 每个 namespace 下可以容纳无限多个 mailbox
- Namespace 在用户账号级别唯一分配

### Tag（标签）
- 动态后缀，例如 `acmeinc.john.smith@inbox.testmail.app` 中的 `john.smith`
- 无需预先注册，可以随意使用
- 用途：分类、过滤、并行测试隔离

### API Key（密钥）
- 所有 API 调用都需要
- 绑定到一个或多个 namespace
- 在 [TestMail Console](https://testmail.app/console) 获取

---

## API 端点

### 1. JSON API

```
GET https://api.testmail.app/api/json
```

#### 必需参数

| 参数 | 类型 | 说明 |
|------|------|------|
| `apikey` | string | API 密钥 |
| `namespace` | string | 要查询的命名空间 |

#### 可选参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `pretty` | bool | `false` | 美化 JSON 输出 |
| `headers` | bool | `false` | 在响应中包含原始邮件头 |
| `spam_report` | bool | `false` | 包含 `spam_score` 和 `spam_report` 字段 |
| `tag` | string | — | 精确匹配标签 |
| `tag_prefix` | string | — | 按标签前缀匹配 |
| `timestamp_from` | int (ms) | — | 起始时间戳（Unix 毫秒），只返回此时间之后收到的邮件 |
| `timestamp_to` | int (ms) | — | 结束时间戳（Unix 毫秒），只返回此时间之前收到的邮件 |
| `limit` | int | `10` | 返回邮件数量上限（范围 0–100） |
| `offset` | int | `0` | 跳过的邮件数（范围 0–9899） |
| `livequery` | bool | `false` | 等待新邮件到达（匹配 1 封后返回，1 分钟无结果则 307 重定向） |

#### 响应格式

```json
{
  "result": "success",        // 或 "fail"
  "message": null,            // 失败时的错误信息
  "count": 5,                 // 本次返回的邮件数
  "limit": 10,                // 请求的 limit
  "offset": 0,                // 请求的 offset
  "emails": [
    {
      "subject": "邮件标题",
      "from": "sender@example.com",
      "to": "namespace.tag@inbox.testmail.app",
      "html": "<html>...</html>",
      "text": "纯文本内容",
      "timestamp": "2026-06-14T08:00:00Z",
      "attachments": [...],
      "tag": "daily"
    }
  ]
}
```

---

### 2. GraphQL API

```
POST https://api.testmail.app/api/graphql
```

#### 认证方式

通过 `Authorization` Header 传递：

```
Authorization: Bearer YOUR_APIKEY
```

#### 主要功能

- **高级过滤**（`advanced_filters`）：按 `from`、`subject`、正文等字段过滤
  ```graphql
  advanced_filters: [
    { field: subject, match: exact, action: include, value: "Welcome" }
  ]
  ```
- **自定义排序**（`advanced_sorts`）：
  ```graphql
  advanced_sorts: [{ field: tag, order: asc }]
  ```
- **Live Queries**：设置 `livequery: true`
- **字段选择**：只请求需要的字段
  ```graphql
  inbox(namespace: "myns") {
    emails { subject from html }
  }
  ```

完整 schema 见 [GraphQL Playground](https://api.testmail.app/api/graphql)

---

## 使用示例

### 基础查询

```bash
curl "https://api.testmail.app/api/json?apikey=YOUR_KEY&namespace=myns&tag=daily&limit=10"
```

### Live Query（等待新邮件）

```bash
# 使用 timestamp_from 避免获取旧邮件
curl "https://api.testmail.app/api/json?apikey=YOUR_KEY&namespace=myns&timestamp_from=$(date +%s)000&livequery=true"
```

> Live Query 返回 HTTP 307 重定向，客户端需跟随重定向。建议设置测试超时（如 5 分钟）。

### 并行测试隔离

每个测试用例使用唯一的 `tag`（如随机后缀）+ `timestamp_from`，避免互相干扰：

```python
import time, uuid

tag = f"test-{uuid.uuid4().hex[:8]}"
timestamp_from = int(time.time() * 1000)  # 当前时间（毫秒）

# 1. 用 {namespace}.{tag}@inbox.testmail.app 注册
# 2. 查询该 tag 的邮件
```

---

## 限制与注意事项

### 邮件保留策略

| 计划 | 保留天数 |
|------|----------|
| Free | 1 天 |
| Starter | 3 天 |
| Business+ | 30 天 |

> 不提供手动删除 API，邮件到期自动清除。

### 频率限制

| 计划 | 限制 |
|------|------|
| Free | 1,000/小时，10,000/天，100,000/月 |
| 付费 | 持续 >5 req/sec 会触发临时黑名单 |
| 全局 | 单 IP >10 req/sec 持续数分钟会触发限制 |

### 性能建议

- `tag` 和 `timestamp` 过滤最快
- 避免对 >30KB 的字段做通配符搜索
- 遇到 `429` 错误时等待重试
- 遇到 `5xx` 错误时使用指数退避

### 垃圾邮件测试

- 基于 SpamAssassin
- 评分 ≥5 表示可能是垃圾邮件
- 通过 `spam_report=true` 参数获取报告

---

## 官方 SDK / 客户端

### JavaScript / TypeScript
- `@testmail.app/graphql-request`（推荐 GraphQL 客户端）

### Python
- `gql`（GraphQL 客户端）

### 其他语言
- Go: `genqlient`
- Java: Apollo
- Ruby/C#: `graphql-client`

### 测试框架集成示例
- Cypress、Selenium、TestCafe（JavaScript）
- 官方文档提供 Java、C#、Python、Go、PHP、Ruby、bash 示例

---

## 常见问题排查

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 查询返回空结果 | 查询了旧邮件 | 使用 `timestamp_from` 限定时间范围 |
| Live Query 超时 | 邮件投递延迟 | 增大测试超时时间（如 5 分钟） |
| `429` 错误 | 频率超限 | 降低请求频率，增加重试间隔 |
| `5xx` 错误 | 服务端临时问题 | 指数退避重试 |
| Live Query 307 循环 | 1 分钟无匹配邮件 | 客户端需跟随 307 重定向，设置总超时 |

---

## 参考链接

- [官方文档](https://testmail.app/docs)
- [API Reference](https://testmail.app/docs/reference/api)
- [GraphQL Playground](https://api.testmail.app/api/graphql)
- [Console（获取 API Key）](https://testmail.app/console)
