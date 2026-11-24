# 标准流程

## 1. 查询类（只读）

```
用户提出查询 → check（可选）→ shops / goods → 摘要 + 表格
```

- `shops`：先让用户确认是哪家店、是否在线；
- `goods`：默认查在售；用户要“全部”时分别查在售/下架/售罄；
- 明细超过 20 行时先给总数和前 20 行，问用户要不要继续翻页。

## 2. 批量上下架（写操作，必须确认）

```
goods 找到商品 → sale-preview → 展示明细 → 用户确认 → sale-confirm → sale-task 轮询
```

硬性规则：

1. **先预览**：`sale-preview` 返回 `confirmToken` 和明细；
2. **展示明细**：商品ID、名称、初始状态、调整后状态、跳过原因、数量；
3. **问用户**：明确问“确认对这 N 件执行上下架吗？”；
4. **用户确认后**才 `sale-confirm`；
5. `sale-confirm` 返回 `taskId`，告诉用户“已提交，正在处理”；
6. 用 `sale-task` 轮询到 completed/failed，再汇报成功/失败件数和原因。

禁止：

- 跳过预览直接确认；
- 未经用户同意自动确认；
- 把 `submitted` 说成“已完成”；
- 对失败项自动重试（先让用户决定）。

## 3. 批量改价（写操作，必须确认）

```
goods → price-preview（mode/newPrice 或公式/小数位）→ 展示 SKU 前后价 → 用户确认 → price-confirm → price-task
```

- 修改类型：拼团价/单买价；范围：全部/最高/最低 SKU（全部可加价格区间）；
- 修改内容：统一新价、公式、仅改小数位；
- 预览里展示每个 SKU 的原价/新价，用户确认后再执行；
- 平台联动规则：单买价至少比拼团价多 1 元。

## 4. 批量改标题（写操作，必须确认）

```
goods → title-preview（rules-json）→ 展示原标题/新标题 → 用户确认 → title-confirm → title-task
```

- 支持商品标题和 SKU 规格名；
- 规则按顺序执行：替换、前后缀、删除关键词、过滤字符；
- 提交方式：立即发布 / 仅保存草稿；
- 预览中标注“无变化/失败”的行。

## 5. 批量删除（高风险，必须二次确认）

```
goods/draft → delete-preview → 展示明细 + “删除不可恢复” → 用户确认 → delete-confirm → delete-task
```

- 默认 `onSalePolicy=skip`（在售跳过）；
- 草稿类传 `--source draft --draft-status draft|publishing|rejected`，ID 用 commitId；
- 用户没有明确说“确认删除”时，只做预览，不执行。

## 6. 生成商品图（异步）

```
image-create → 返回 taskNo → image-task 轮询 → 把图片 URL 给用户
```

- 提交前确认张数、比例；没说就先问一次或按 1 张/1:1 保守默认并告知；
- 积分不足不要代下单，给充值链接；
- 完成后把图片 URL 列表交给用户，不让用户自己去 App 查。

## 4. 失败与恢复

| 场景 | 处理 |
|---|---|
| 店铺离线 | 让用户到小尊宝客户端重新登录店铺 |
| 客户端未启动 | 提示打开小尊宝客户端 |
| Token 失效 | 让用户重新复制设备 token / 飞影 ApiKey |
| 预览过期 | 重新 `sale-preview` |
| 任务 unknown | 不要重试写操作；让用户先查商品现状 |
