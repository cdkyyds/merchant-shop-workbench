# 商家工作台（SkillHub Skill）

一份面向拼多多/抖店商家的 AI 技能说明：查店铺、查商品、批量上下架、改价、改标题、删除、商品图生成，并把每次操作整理成带商品明细的工作日志。

**本技能不包含工具清单，也不自带“命令”。** 工具由小尊宝/飞影的 MCP 提供，以 `tools/list` 为准；本技能只写鉴权、流程、安全规则和日志格式。

## 目录

```
merchant-workbench/
├─ SKILL.md                 # 入口：凭证、调用方式、写操作规则、日志、费用
├─ manifest.json            # 名称/版本/简介/标签
├─ README.md
├─ config.example.json      # 凭证示例（不要提交真实 Token）
├─ references/
│  ├─ auth.md               # 两个凭证怎么拿、怎么配
│  ├─ tools.md              # 直接 HTTP/JSON-RPC 示例与错误码
│  ├─ workflow.md           # 查询/上下架/改价/改标题/删除/生图流程
│  ├─ worklog.md            # 工作日志格式
│  ├─ pricing.md            # 上游计费与本技能计费边界
│  └─ examples.md           # 对话示例
└─ scripts/
   └─ skill.py              # 可选兜底：给不能手写 JSON-RPC 的宿主用
```

## 凭证（用户自己提供）

1. **小尊宝设备 Token**：小尊宝客户端 → AI 接入 → 复制设备凭证（`zzb_` 开头）。
2. **飞影 ApiKey**：飞影后台复制。

```bash
export ZZB_TOKEN="zzb_..."
export FY_TOKEN="..."
```

或复制 `config.example.json` 为 `config.json` 填写。

## 怎么调用

- **宿主已接 MCP（推荐）**：直接把工具暴露给模型，按 `references/workflow.md` 的预览→确认→任务流程调用。工具名和参数以 `tools/list` 为准，不需要本技能列清单。
- **宿主只有 HTTP**：按 `references/tools.md` 的 JSON-RPC 示例直接调用。
- **宿主不能发 JSON-RPC、但有 Python**：用 `scripts/skill.py` 兜底（可选）。

脚本里的常用动作（可选）：

```bash
python scripts/skill.py check
python scripts/skill.py shops
python scripts/skill.py goods --shop-id 111911953 --status on_sale
python scripts/skill.py sale-preview --shop-id 111911953 --action off_sale --ids 111,222
python scripts/skill.py sale-confirm --confirm-token <token>
python scripts/skill.py price-preview --shop-id 111911953 --ids 111 --mode uniform --new-price 19.9
python scripts/skill.py title-preview --shop-id 111911953 --ids 111 --rules-json '[{"type":"affix","prefix":"新品"}]'
python scripts/skill.py delete-preview --shop-id 111911953 --ids 111 --source goods
python scripts/skill.py image-create --image-url https://example.com/a.jpg --num 1
python scripts/skill.py worklog --action 下架 --shop 小哈百货 --count 37 --result "成功35 失败2"
```

其余工具用 `call`（可选脚本）或直接按 MCP 工具名调。

## 发布到 SkillHub

### 网页发布（推荐先用）

1. 打开 https://skillhub.cn ，手机号登录，完成实名认证；
2. 右上角「发布 Skill」；
3. 选择本文件夹或上传压缩包，填写名称/分类/标签；
4. 提交后 `pending_review`，审核通过即可被用户安装。

### CLI 发布（经常迭代）

```bash
curl -fsSL https://skillhub.cn/install/install.sh | bash -s -- --cli-only
skillhub login --key "skh_..." --host https://api.skillhub.cn
skillhub publish ./merchant-workbench --dry-run
skillhub publish ./merchant-workbench --changelog "首次发布"
```

> Windows 上 CLI 需要 WSL；只发一两次用网页即可。

## 限制

- 小尊宝 MCP 依赖本机客户端在线；
- 店铺离线时只能查缓存，写操作返回登录失效；
- 不返回商品图片 URL（MCP 不提供）；
- 飞影生成按积分扣费；
- 删除不可恢复，默认只预览不执行。
