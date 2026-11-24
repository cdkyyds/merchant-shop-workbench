# 工具与调用方式

本技能不要求脚本。优先由宿主直接调用 MCP 工具；宿主只有 HTTP 能力时，按下面的 JSON-RPC 示例直接调用。`scripts/skill.py` 只是给不能手写 JSON-RPC 的宿主做兜底，不是必须的。

## 一、小尊宝 MCP（拼多多）

- URL：`https://jingflowapi.zzbtool.com/zzbrelay/agent-relay/mcp`
- Header：`Authorization: zzb_...`
- 响应：JSON-RPC，工具结果在 `result.content[0].text`（一个 JSON 字符串，形如 `{"ok":true,"data":{...}}`）

### 直接调用示例

```bash
curl -s https://jingflowapi.zzbtool.com/zzbrelay/agent-relay/mcp \
  -H "Authorization: zzb_..." \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"list_pdd_shops_detail","arguments":{}}}'
```

### 工具表

| 工具 | 参数 | 返回 |
|---|---|---|
| `list_pdd_shops_detail` | `{}` | `rows[]`：shopId、shopName、loginStatus、goodsPack |
| `list_pdd_goods` | `shopId`、`status`(on_sale/off_sale/sold_out)、`keyword`、`goodsIds[]`、`page`、`pageSize`(≤50) | `rows[]`：goodsId、goodsName、onSale、quantity、status；`total`、`hasMore` |
| `preview_pdd_goods_sale` | `shopId`、`goodsIds[]`(1~50)、`action`(on_sale/off_sale) | `rows[]`：result=pending/skipped、message；`confirmToken`（约 5 分钟） |
| `confirm_pdd_goods_sale` | `confirmToken`、`confirmed:true` | `taskId`、`state` |
| `get_pdd_goods_sale_task` | `taskId` | `state`、`summary`、`rows[]` |

注意：

- `preview` 只生成预览，不执行；`confirm` 才提交；
- `confirmToken` 过期或商品变化会返回错误，必须重新预览；
- 单次最多 50 件，超出分批；
- 不提供删除商品接口，不要尝试。

## 二、飞影 MCP（生图）

- URL：`https://fyaimcp.feiyingai.com/mcp`
- 配置里只写 URL，不带 Key；连接后先 `set_fy_token` 登录。
- 响应是 SSE（`event: message` + `data: {...}`），会话 ID 在响应头 `mcp-session-id`。

### 调用顺序

1. `initialize`（获取 `mcp-session-id`）
2. `notifications/initialized`
3. `tools/call` `set_fy_token`，参数 `{"token":"<ApiKey>"}`
4. 调用生成/查询工具

### 工具表

| 工具 | 参数 | 返回 |
|---|---|---|
| `set_fy_token` | `token` | 登录状态、积分（不要展示 token） |
| `create_scene_image` | `imgUrl`（公网 HTTPS，最多 3 张）、`prompt`（可选）、`ratio`(1:1/3:4)、`num`(1~5) | `TaskNo` |
| `get_task_result` | `taskNo`、`needParams:true` | `Status`(0/1/3/5)、`Result.ImageUrls[]`、`FailReason` |
| `get_user_balance` | `{}` | 账号、积分（`Credit` 为分值，展示时 ÷100） |

飞影限制：

- 图片必须是公网 HTTPS URL；本地图先 `upload_media`（base64）；
- `num` 只能 1~5，要更多拆多次；
- 生成按积分扣费，积分不足不要代下单，打开 `https://feiyingai.com/#/recharge?apiKey={apiKey}` 让用户充值。

## 四、批量改价

| 工具 | 参数 | 返回 |
|---|---|---|
| `preview_pdd_goods_price` | `shopId`、`goodsIds[]`、`priceTypes`(multi_price/price)、`skuRange`(all/highest/lowest)、`skuPriceMin`/`skuPriceMax`（all 时）、`mode`(uniform/formula/decimal)、`newPrice` / `formula{priceRatio,plus,minus,resultRatio}` / `decimal` | `rows[]`：goodsId、goodsName、marketPrice、result、skuChanges[]；`confirmToken` |
| `confirm_pdd_goods_price` | `confirmToken`、`confirmed:true` | `taskId` |
| `get_pdd_goods_price_task` | `taskId` | `state`、`summary`、`rows[]` |

规则：单买价至少比拼团价多 1 元；参考价会被平台钳制；预览后商品变化要重新预览。

## 五、批量改标题

| 工具 | 参数 | 返回 |
|---|---|---|
| `preview_pdd_goods_title` | `shopId`、`goodsIds[]`、`targetType`(goods/sku)、`submitMode`(publish/draft)、`rules[]`、`skuKeywords[]`（sku 时可选） | `rows[]`：beforeName/afterName 或 skuChanges[]、result；`confirmToken` |
| `confirm_pdd_goods_title` | `confirmToken`、`confirmed:true` | `taskId` |
| `get_pdd_goods_title_task` | `taskId` | `state`、`summary`、`rows[]` |

规则类型：`replace`（search/replaceWith）、`affix`（prefix/suffix）、`remove_words`（words）、`filter`（modes：english/digits/spaces/all_commas/en_comma）。

## 六、批量删除（高风险）

| 工具 | 参数 | 返回 |
|---|---|---|
| `preview_pdd_goods_delete` | `shopId`、`goodsIds[]`、`source`(goods/draft)、`draftStatus`（草稿时）、`onSalePolicy`(skip/off_sale_and_delete) | `rows[]`：goodsId/commitId、goodsName、result、message；`confirmToken` |
| `confirm_pdd_goods_delete` | `confirmToken`、`confirmed:true` | `taskId` |
| `get_pdd_goods_delete_task` | `taskId` | `state`、`summary`、`rows[]` |

规则：删除不可恢复；默认 `onSalePolicy=skip`；必须二次确认；不要在用户未明确确认时执行。

## 七、工作日志

| 命令 | 参数 | 说明 |
|---|---|---|
| `worklog` | `action`、`shop`、`count`、`result`、`cost`、`detail-json`、`dir` | 追加写入 `worklogs/YYYY-MM-DD.md`，并打印日志 |

日志格式见 `references/worklog.md`。

## 八、错误映射


| 返回 | 含义 | 处理 |
|---|---|---|
| `SHOP_NOT_LOGGED_IN` | 店铺登录失效 | 让用户到小尊宝客户端重新登录 |
| `LIVE_NOT_LOGGED_IN` | 多多视频登录失效 | 让用户在客户端视频页扫码 |
| `INSUFFICIENT_POWER` | 算力/积分不足 | 让用户充值后再试 |
| `PRECONDITION_FAILED` | 预览后商品变化 | 重新预览 |
| `API_ERROR` | 平台接口失败 | 原样转述 message，不自动重试写操作 |
