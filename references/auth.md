# 鉴权与凭证

本技能需要两个凭证，均由用户自己提供，技能包内不保存任何 Token。

## 1. 小尊宝设备 Token（zzb_...）

获取方式：

1. 打开小尊宝客户端并登录；
2. 进入「AI 接入」；
3. 复制设备凭证（`zzb_` 开头，一串十六进制）。

用途：调用小尊宝远程 MCP：

- URL：`https://jingflowapi.zzbtool.com/zzbrelay/agent-relay/mcp`
- Header：`Authorization: zzb_...`（不是 Bearer）

## 2. 飞影 ApiKey

获取方式：

1. 打开 `https://feiyingai.com/` 登录（手机号 + 验证码）；
2. 自动进入个人中心 `https://feiyingai.com/#/center`；
3. 复制 ApiKey。

用途：调用飞影 MCP：

- URL：`https://fyaimcp.feiyingai.com/mcp`
- 连接后调用 `set_fy_token`，参数 `token` = ApiKey；会话内生效。

## 配置方式

**方式一：环境变量（推荐）**

```bash
export ZZB_TOKEN="zzb_..."
export FY_TOKEN="..."
```

**方式二：config.json**

复制 `config.example.json` 为 `config.json`，填 `zzbToken` / `fyToken`。

**方式三：直接对话提供**

如果宿主不允许执行脚本，用户可在对话里把两个凭证发给 Agent，由 Agent 按 `references/tools.md` 的 HTTP 示例直接调用。

## 安全规则（必须遵守）

- 不要把完整 Token 展示给用户、写进回答、日志或文件；
- 不要把 Token 写进 SKILL.md / manifest.json / 脚本；
- 用户要求撤销时，指导其在小尊宝「AI 接入」重置、在飞影个人中心重新生成；
- 小尊宝设备 Token 等同于店铺操作权限，只能用于用户本人的店铺。
