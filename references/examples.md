# 对话示例

## 1. 查店铺 / 商品

用户：看看我拼多多店铺在售的商品。

助手：`shops` → `goods --shop-id <ID> --status on_sale` → 摘要 + 表格。

## 2. 批量下架

用户：把这两件下架：1028384205374、1028351551164。

助手：

1. `sale-preview --shop-id 111911953 --action off_sale --ids 1028384205374,1028351551164`
2. 展示明细，问“确认下架这 2 件吗？”
3. 用户确认 → `sale-confirm --confirm-token <token>`
4. `sale-task --task-id <taskId>` 查结果
5. `worklog` 写日志

## 3. 批量改价

用户：把这两件商品统一改成 19.9 元。

助手：

1. `price-preview --shop-id 111911953 --ids 111,222 --mode uniform --new-price 19.9`
2. 展示每个 SKU 的原价/新价
3. 确认 → `price-confirm` → `price-task`
4. `worklog` 写日志

## 4. 批量改标题

用户：给这两件商品标题前面加“新品”。

助手：

1. `title-preview --shop-id 111911953 --ids 111,222 --rules-json '[{"type":"affix","prefix":"新品"}]'`
2. 展示原标题/新标题
3. 确认 → `title-confirm` → `title-task`
4. `worklog` 写日志

## 5. 批量删除

用户：把这两件草稿删掉。

助手：

1. `delete-preview --shop-id 111911953 --ids 111,222 --source draft --draft-status draft`
2. 展示明细并明确说“删除不可恢复，确认吗？”
3. 用户确认 → `delete-confirm` → `delete-task`
4. `worklog` 写日志（标注删除不可恢复）

## 6. 生成商品图

用户：用这张图生成 3 张首图。

助手：`image-create --image-url <URL> --num 3` → `image-task --task-no <taskNo>` → 把图片 URL 给用户 → `worklog`。

## 7. 错误

- 店铺登录失效：让用户到小尊宝客户端重新登录；
- 积分不足：给飞影充值链接，不代下单；
- 预览过期：重新预览。
