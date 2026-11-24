---
slug: merchant-shop-workbench
name: merchant-shop-workbench
displayName: 商家工作台（拼多多/抖店）
version: 0.1.0
summary: 电商商家的 AI 工作台：查店铺/商品、批量上下架/改价/改标题/删除、AI 商品图；先预览再执行，自动生成商品级工作日志。支持小尊宝与飞影，后续可扩展晓风上货。
description: 面向拼多多、抖店等电商商家的 AI 工作台。通过小尊宝完成店铺与商品查询、批量上下架、批量改价、批量改标题、批量删除（高风险，默认只预览）；通过飞影生成商品图等素材。所有写操作先预览、经用户确认后执行，并输出带商品明细的工作日志。凭证由用户自备，上游费用各扣各的。平台可扩展：后续接入晓风上货等，使用方式不变。
license: MIT
tags:
  - 拼多多
  - 抖店
  - 电商
  - 商家工作台
  - 店铺
  - 商品
  - 批量
  - 上下架
  - 改价
  - 改标题
  - 删除
  - 商品图
  - 工作日志
  - MCP
---

# 商家工作台（拼多多/抖店）

## 这是什么

把商家的日常操作变成一句话：查店铺、查商品、批量上下架、改价、改标题、删除、生成商品图，并输出用户能看懂的**工作日志**（含商品级明细）。

**本技能不自带“命令”**。它是一份使用说明：告诉 AI 用哪个 MCP 工具、怎么鉴权、写操作怎么确认、日志怎么写。工具由宿主直接调用。

## 使用前准备（用户必须自己提供）

- `ZZB_TOKEN`：小尊宝设备 Token（客户端 → AI 接入 → 复制设备凭证，`zzb_` 开头）
- `FY_TOKEN`：飞影 ApiKey（飞影后台复制）

细节见 `references/auth.md`。

## 怎么调用（按宿主能力选一种）

### 方式 A：宿主已接 MCP（推荐）

宿主把两个 MCP 的工具直接暴露给模型，模型按工具名调用，不需要脚本：

- 小尊宝：`https://jingflowapi.zzbtool.com/zzbrelay/agent-relay/mcp`，Header `Authorization: zzb_...`
- 飞影：`https://fyaimcp.feiyingai.com/mcp`，连上后先调 `set_fy_token`

工具名、参数、必填项**以 MCP 的 `tools/list` 为准**。宿主接上 MCP 后会自动出现全部工具，后续 MCP 新增工具也不需要改本技能。需要查看时，可以用可选脚本 `scripts/skill.py list-tools --platform zzb|fy`。

### 方式 B：宿主只有 HTTP/curl 能力

按 `references/tools.md` 的示例直接发 JSON-RPC：

- 小尊宝：`initialize` → `tools/call`（Header 带 token）
- 飞影：`initialize`（拿 `mcp-session-id`）→ `notifications/initialized` → `tools/call`（先 `set_fy_token`）

### 方式 C：宿主不能发 JSON-RPC，但有 Python（兜底，可选）

包内附带 `scripts/skill.py`，只是把上面的调用封了一层，方便不擅长手写 JSON-RPC 的宿主。**它不是必须的**，也不改变“工具本身就是接口”这件事。

## 常用动作对应的工具

| 想做什么 | 小尊宝工具 | 说明 |
|---|---|---|
| 查店铺 | `list_pdd_shops_detail` | 店铺、登录状态、商品功能包 |
| 查商品 | `list_pdd_goods` | 按状态/关键词/ID，分页 ≤50 |
| 上下架 | `preview_pdd_goods_sale` → `confirm_pdd_goods_sale` → `get_pdd_goods_sale_task` | 先预览拿 confirmToken |
| 改价 | `preview_pdd_goods_price` → `confirm_pdd_goods_price` → `get_pdd_goods_price_task` | 统一价/公式/小数位 |
| 改标题 | `preview_pdd_goods_title` → `confirm_pdd_goods_title` → `get_pdd_goods_title_task` | 商品标题或 SKU |
| 删除 | `preview_pdd_goods_delete` → `confirm_pdd_goods_delete` → `get_pdd_goods_delete_task` | 不可恢复，默认只预览 |
| 生成商品图 | 飞影 `set_fy_token` → `create_scene_image` → `get_task_result` | 积分扣费 |

其余工具直接用 MCP 工具名调用，用同样的方式。

## 写操作规则（必须遵守）

1. **先预览**：调用 `preview_*`，拿到 `confirmToken` 和商品明细；
2. **给用户看明细**：商品ID、名称、初始状态、调整后状态、跳过原因；
3. **问用户确认**：明确问“确认执行这 N 件吗？”；
4. **再执行**：用户确认后才调 `confirm_*`；
5. **查任务**：用 `get_*_task` 轮询到结束，汇报成功/失败/原因；
6. **写工作日志**：按 `references/worklog.md` 输出，含明细。

删除额外规则：必须二次确认、写明“删除不可恢复”、默认只预览不执行。

## 工作日志

每次操作结束给用户一条可读日志：时间、店铺、动作、数量、成功/失败/跳过、失败原因、商品明细表、费用说明。格式见 `references/worklog.md`。

## 费用

- 上游：小尊宝（功能包/算力）、飞影（积分）按各自规则从用户账户扣；
- 本技能：不代收上游费用；若上架为付费技能（SkillPay），那是技能本身的费用，与上游账单分开。

## 边界

- 小尊宝依赖本机客户端在线；店铺离线只能查缓存，写操作返回登录失效；
- 不返回商品图片 URL；飞影图片需公网 HTTPS；
- 不提供提现、付款、登录改密、邀请推广；
- 不做“自动重试写操作”。

## 参考文件

- `references/auth.md`：两个凭证怎么拿、怎么配
- `references/tools.md`：直接 HTTP 调用示例与错误码
- `references/workflow.md`：查询/上下架/改价/改标题/删除/生图流程
- `references/worklog.md`：工作日志格式
- `references/pricing.md`：计费边界
- `references/examples.md`：对话示例

工具清单不写死在本技能里：小尊宝和飞影的 MCP 各自提供 `tools/list`，技能只负责鉴权、流程、安全规则和日志格式。以后接晓风上货，同样只加一段鉴权说明，不需要改工具清单。
