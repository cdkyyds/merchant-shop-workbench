#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""电商店铺助手（拼多多/抖店）SkillHub Skill.

依赖：Python 3.8+，仅标准库。
凭证：环境变量 ZZB_TOKEN / FY_TOKEN，或 config.json，或 ~/.skillhub/pdd-shop-assistant.json。
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

ZZB_DEFAULT_URL = "https://jingflowapi.zzbtool.com/zzbrelay/agent-relay/mcp"
FY_DEFAULT_URL = "https://fyaimcp.feiyingai.com/mcp"
SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class SkillError(Exception):
    def __init__(self, message, code=""):
        super().__init__(message)
        self.code = code


def load_config(explicit_path=None):
    cfg = {}
    candidates = []
    if explicit_path:
        candidates.append(explicit_path)
    candidates.append(os.path.join(SKILL_ROOT, "config.json"))
    candidates.append(os.path.expanduser("~/.skillhub/pdd-shop-assistant.json"))
    for path in candidates:
        if path and os.path.isfile(path):
            with open(path, "r", encoding="utf-8-sig") as fh:
                cfg.update(json.load(fh))
            break
    cfg["zzbToken"] = os.environ.get("ZZB_TOKEN") or cfg.get("zzbToken") or ""
    cfg["fyToken"] = os.environ.get("FY_TOKEN") or cfg.get("fyToken") or ""
    cfg["zzbUrl"] = os.environ.get("ZZB_MCP_URL") or cfg.get("zzbUrl") or ZZB_DEFAULT_URL
    cfg["fyUrl"] = os.environ.get("FY_MCP_URL") or cfg.get("fyUrl") or FY_DEFAULT_URL
    return cfg


def http_post(url, payload, headers, timeout=120):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
            content_type = resp.headers.get("Content-Type", "")
            session_id = resp.headers.get("mcp-session-id")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:500]
        raise SkillError("HTTP %s: %s" % (exc.code, detail), "HTTP_ERROR")
    except urllib.error.URLError as exc:
        raise SkillError("连接失败：%s" % exc.reason, "NETWORK_ERROR")
    if "text/event-stream" in content_type:
        data_lines = [line[6:] for line in raw.splitlines() if line.startswith("data: ")]
        if not data_lines:
            raise SkillError("MCP 返回空事件流", "EMPTY_RESPONSE")
        raw = data_lines[0]
    try:
        return json.loads(raw), session_id
    except json.JSONDecodeError:
        raise SkillError("MCP 返回无法解析：%s" % raw[:300], "BAD_RESPONSE")


class McpClient:
    def __init__(self, url, token=None, session=False):
        self.url = url
        self.session_id = None
        self.next_id = 1
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if token:
            self.headers["Authorization"] = token
        if session:
            self._initialize()

    def _request(self, method, params, notify=False):
        payload = {"jsonrpc": "2.0", "method": method, "params": params}
        if not notify:
            payload["id"] = self.next_id
            self.next_id += 1
        headers = dict(self.headers)
        if self.session_id:
            headers["mcp-session-id"] = self.session_id
        data, session_id = http_post(self.url, payload, headers)
        if session_id:
            self.session_id = session_id
        if not notify and data.get("error"):
            raise SkillError(data["error"].get("message") or "MCP 调用失败", "MCP_ERROR")
        return data

    def _initialize(self):
        self._request("initialize", {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "skillhub-pdd-assistant", "version": "0.1.0"},
        })
        try:
            self._request("notifications/initialized", {}, notify=True)
        except SkillError:
            pass

    def tools(self):
        data = self._request("tools/list", {})
        return (data.get("result") or {}).get("tools") or []

    def tool(self, name, arguments):
        data = self._request("tools/call", {"name": name, "arguments": arguments})
        result = data.get("result") or {}
        content = result.get("content") or []
        text = "\n".join(item.get("text", "") for item in content if item.get("type") == "text")
        if result.get("isError"):
            raise SkillError(text or "工具执行失败", "TOOL_ERROR")
        try:
            parsed = json.loads(text) if text else {}
        except json.JSONDecodeError:
            parsed = {"raw": text}
        if isinstance(parsed, dict) and parsed.get("ok") is False:
            raise SkillError(parsed.get("message") or "工具执行失败", parsed.get("code") or "TOOL_ERROR")
        if isinstance(parsed, dict):
            if "data" in parsed:
                return parsed["data"]
            if isinstance(parsed.get("result"), dict):
                return parsed["result"]
            if isinstance(parsed.get("Result"), dict):
                return parsed["Result"]
        return parsed


def zzb_client(cfg):
    if not cfg.get("zzbToken"):
        raise SkillError(
            "缺少 ZZBT_TOKEN。请设置环境变量 ZZB_TOKEN（小尊宝客户端 → AI 接入 → 复制设备凭证），"
            "或复制 config.example.json 为 config.json 填入 zzbToken。",
            "CONFIG_ERROR",
        )
    return McpClient(cfg["zzbUrl"], token=cfg["zzbToken"], session=True)


def fy_client(cfg):
    if not cfg.get("fyToken"):
        raise SkillError(
            "缺少飞影凭证。请设置环境变量 FY_TOKEN（飞影后台复制 ApiKey），"
            "或复制 config.example.json 为 config.json 填入 fyToken。",
            "CONFIG_ERROR",
        )
    client = McpClient(cfg["fyUrl"], session=True)
    client.tool("set_fy_token", {"token": cfg["fyToken"]})
    return client


def shorthand(text, limit=44):
    value = str(text or "").replace("\n", " ").strip()
    return value if len(value) <= limit else value[: limit - 1] + "…"


def print_table(headers, rows):
    widths = [len(h) for h in headers]
    cells = []
    for row in rows:
        line = [shorthand(cell) for cell in row]
        cells.append(line)
        widths = [max(widths[i], len(line[i])) for i in range(len(headers))]
    print("| " + " | ".join(headers[i].ljust(widths[i]) for i in range(len(headers))) + " |")
    print("|" + "|".join("-" * (widths[i] + 2) for i in range(len(headers))) + "|")
    for line in cells:
        print("| " + " | ".join(line[i].ljust(widths[i]) for i in range(len(headers))) + " |")


def status_text(value):
    return {True: "上架", False: "下架"}.get(value, str(value))


def resolve_shop(args, cfg):
    if getattr(args, "shop_id", None):
        return args.shop_id
    shops = zzb_client(cfg).tool("list_pdd_shops_detail", {})
    rows = shops.get("rows") or []
    if len(rows) == 1:
        print("店铺ID未指定，自动使用唯一店铺：%s" % rows[0].get("shopName", ""))
        return str(rows[0].get("shopId"))
    names = "、".join("%s(%s)" % (r.get("shopName", ""), r.get("shopId", "")) for r in rows) or "无"
    raise SkillError("请指定 --shop-id。当前店铺：%s" % names, "SHOP_REQUIRED")


def cmd_check(args, cfg):
    zzb = zzb_client(cfg).tool("get_app_status", {})
    fy = fy_client(cfg)
    balance = fy.tool("get_user_balance", {})
    if args.json:
        print(json.dumps({"zzb": zzb, "fy": balance}, ensure_ascii=False, indent=2))
        return 0
    print("小尊宝 MCP：已连接，客户端 %s，登录状态 %s" % (
        zzb.get("appVersion", "?"), "已登录" if zzb.get("loggedIn") else "未登录"))
    credit = balance.get("CreditStr") or str(balance.get("Credit", "?"))
    print("飞影 MCP：已连接，账号积分 %s" % credit)
    return 0


def cmd_shops(args, cfg):
    data = zzb_client(cfg).tool("list_pdd_shops_detail", {})
    rows = data.get("rows") or []
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0
    print("共 %s 家店铺，在线 %s 家。" % (data.get("total", len(rows)), data.get("onlineCount", 0)))
    print_table(["店铺ID", "店铺名称", "登录状态", "商品功能包"],
                [[r.get("shopId", ""), r.get("shopName", ""), r.get("loginStatus", ""),
                  (r.get("goodsPack") or {}).get("status", "")] for r in rows])
    return 0


def cmd_goods(args, cfg):
    shop_id = resolve_shop(args, cfg)
    payload = {"shopId": shop_id, "page": args.page, "pageSize": args.page_size}
    if args.status:
        payload["status"] = args.status
    if args.keyword:
        payload["keyword"] = args.keyword
    if args.ids:
        payload["goodsIds"] = parse_ids(args.ids)
    data = zzb_client(cfg).tool("list_pdd_goods", payload)
    rows = data.get("rows") or []
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0
    print("店铺 %s 查询到 %s 件商品（第 %s 页）。" % (shop_id, data.get("total", len(rows)), data.get("page", 1)))
    print_table(["商品ID", "商品名称", "在售", "库存", "状态"],
                [[r.get("goodsId", ""), r.get("goodsName", ""), status_text(r.get("onSale")),
                  r.get("quantity", ""), r.get("status", "")] for r in rows])
    if data.get("hasMore"):
        print("\n还有下一页，可用 --page %s 继续。" % (int(data.get("page", 1)) + 1))
    return 0


def cmd_sale_preview(args, cfg):
    shop_id = resolve_shop(args, cfg)
    ids = parse_ids(args.ids)
    if not ids:
        raise SkillError("请用 --ids 指定要上下架的商品ID，多个用逗号分隔。", "IDS_REQUIRED")
    if len(ids) > 50:
        raise SkillError("单次最多 50 件商品，请分批预览。", "TOO_MANY_IDS")
    action = "on_sale" if args.action == "on_sale" else "off_sale"
    data = zzb_client(cfg).tool("preview_pdd_goods_sale", {"shopId": shop_id, "goodsIds": ids, "action": action})
    rows = data.get("rows") or []
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0
    pending = [r for r in rows if r.get("result") == "pending"]
    skipped = [r for r in rows if r.get("result") == "skipped"]
    label = "上架" if action == "on_sale" else "下架"
    print("已生成%s预览：%s 件将%s，%s 件跳过，请把明细给用户确认。" % (label, len(pending), label, len(skipped)))
    print_table(["商品ID", "商品名称", "初始状态", "调整后", "结果"],
                [[r.get("goodsId", ""), r.get("goodsName", ""), status_text(r.get("onSale")), label,
                  "待执行" if r.get("result") == "pending" else (r.get("message") or "跳过")] for r in rows])
    token = data.get("confirmToken", "")
    print("\n确认凭据：%s（约 5 分钟有效）" % token)
    print("下一步：用户确认后执行 `sale-confirm --confirm-token %s`。" % token)
    return 0


def cmd_sale_confirm(args, cfg):
    data = zzb_client(cfg).tool("confirm_pdd_goods_sale", {"confirmToken": args.confirm_token, "confirmed": True})
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0
    print("已提交任务，taskId=%s，状态=%s。" % (data.get("taskId", ""), data.get("state", "")))
    print("下一步：用 `sale-task --task-id %s` 查询进度。" % data.get("taskId", ""))
    return 0


def cmd_sale_task(args, cfg):
    data = zzb_client(cfg).tool("get_pdd_goods_sale_task", {"taskId": args.task_id})
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0
    summary = data.get("summary") or {}
    print("任务 %s：%s" % (data.get("taskId", ""), data.get("state", "")))
    print("已提交 %s，失败 %s，未知 %s，跳过 %s。" % (
        summary.get("submitted", 0), summary.get("failed", 0), summary.get("unknown", 0), summary.get("skipped", 0)))
    rows = data.get("rows") or []
    if rows:
        print_table(["商品ID", "结果", "说明"],
                    [[r.get("goodsId", ""), r.get("result", ""), r.get("message", "")] for r in rows])
    return 0


def cmd_image_create(args, cfg):
    client = fy_client(cfg)
    payload = {
        "imgUrl": args.image_url,
        "num": args.num,
        "ratio": args.ratio,
    }
    if args.prompt:
        payload["prompt"] = args.prompt
    data = client.tool("create_scene_image", payload)
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0
    task_no = data.get("TaskNo") or data.get("taskNo") or ""
    print("已提交爆款首图任务，taskNo=%s。" % task_no)
    print("下一步：用 `image-task --task-no %s` 查询结果。" % task_no)
    return 0


def cmd_image_task(args, cfg):
    data = fy_client(cfg).tool("get_task_result", {"taskNo": args.task_no, "needParams": True})
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0
    result = data.get("result") or data.get("Result") or {}
    status = result.get("Status")
    print("任务 %s：状态 %s（0 未开始/1 生成中/3 完成/5 失败）。" % (args.task_no, status))
    images = result.get("ImageUrls") or []
    if images:
        print("图片：")
        for url in images:
            print("- %s" % url)
    video = result.get("VideoUrl")
    if video:
        print("视频：%s" % video)
    if status == 5:
        print("失败原因：%s" % (result.get("FailReason") or "未知"))
    return 0


def cmd_balance(args, cfg):
    data = fy_client(cfg).tool("get_user_balance", {})
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0
    credit = data.get("CreditStr") or str(data.get("Credit", ""))
    print("飞影账号：%s，积分 %s。" % (data.get("NickName") or data.get("UserName") or "", credit))
    return 0


def cmd_price_preview(args, cfg):
    shop_id = resolve_shop(args, cfg)
    ids = parse_ids(args.ids)
    if not ids:
        raise SkillError("请用 --ids 指定要改价的商品ID。", "IDS_REQUIRED")
    if len(ids) > 50:
        raise SkillError("单次最多 50 件商品，请分批预览。", "TOO_MANY_IDS")
    price_types = [item.strip() for item in (args.price_types or "multi_price,price").split(",") if item.strip()]
    payload = {"shopId": shop_id, "goodsIds": ids, "priceTypes": price_types, "skuRange": args.sku_range}
    if args.sku_range == "all":
        if args.price_min is not None:
            payload["skuPriceMin"] = args.price_min
        if args.price_max is not None:
            payload["skuPriceMax"] = args.price_max
    if args.mode == "uniform":
        if args.new_price is None or args.new_price <= 0:
            raise SkillError("统一新价格需要 --new-price 且大于 0。", "INVALID_PRICE")
        payload["mode"] = "uniform"
        payload["newPrice"] = args.new_price
    elif args.mode == "formula":
        payload["mode"] = "formula"
        payload["formula"] = {
            "priceRatio": args.price_ratio if args.price_ratio is not None else 100,
            "plus": args.plus or 0,
            "minus": args.minus or 0,
            "resultRatio": args.result_ratio if args.result_ratio is not None else 100,
        }
    else:
        value = str(args.decimal or "")
        if not value.isdigit() or len(value) > 2:
            raise SkillError("仅修改小数位需要 --decimal，1~2 位数字。", "INVALID_DECIMAL")
        payload["mode"] = "decimal"
        payload["decimal"] = value
    data = zzb_client(cfg).tool("preview_pdd_goods_price", payload)
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0
    rows = data.get("rows") or []
    pending = [r for r in rows if r.get("result") == "pending"]
    print("已生成改价预览：%s 件将改价，%s 件跳过。" % (len(pending), len(rows) - len(pending)))
    print_table(["商品ID", "商品名称", "参考价", "SKU数", "结果"],
                [[r.get("goodsId", ""), r.get("goodsName", ""), r.get("marketPrice", ""),
                  len(r.get("skuChanges") or []), r.get("result", "") if r.get("result") != "skipped" else (r.get("message") or "跳过")] for r in rows])
    print("\n确认凭据：%s（约 5 分钟有效）" % data.get("confirmToken", ""))
    print("下一步：用户确认后执行 `price-confirm --confirm-token %s`。" % data.get("confirmToken", ""))
    return 0


def cmd_price_confirm(args, cfg):
    data = zzb_client(cfg).tool("confirm_pdd_goods_price", {"confirmToken": args.confirm_token, "confirmed": True})
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0
    print("已提交改价任务，taskId=%s，状态=%s。" % (data.get("taskId", ""), data.get("state", "")))
    print("下一步：`price-task --task-id %s` 查询进度。" % data.get("taskId", ""))
    return 0


def cmd_price_task(args, cfg):
    data = zzb_client(cfg).tool("get_pdd_goods_price_task", {"taskId": args.task_id})
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0
    summary = data.get("summary") or {}
    print("任务 %s：%s（成功 %s / 失败 %s / 未知 %s）" % (
        data.get("taskId", ""), data.get("state", ""), summary.get("submitted", 0),
        summary.get("failed", 0), summary.get("unknown", 0)))
    rows = data.get("rows") or []
    if rows:
        print_table(["商品ID", "结果", "说明"],
                    [[r.get("goodsId", ""), r.get("result", ""), r.get("message", "")] for r in rows])
    return 0


def cmd_title_preview(args, cfg):
    shop_id = resolve_shop(args, cfg)
    ids = parse_ids(args.ids)
    if not ids:
        raise SkillError("请用 --ids 指定要改标题的商品ID。", "IDS_REQUIRED")
    try:
        rules = json.loads(args.rules_json)
    except json.JSONDecodeError:
        raise SkillError("--rules-json 不是合法 JSON。", "INVALID_RULES")
    if not isinstance(rules, list) or not rules:
        raise SkillError("--rules-json 必须是非空数组。", "INVALID_RULES")
    payload = {
        "shopId": shop_id,
        "goodsIds": ids,
        "targetType": args.target_type,
        "submitMode": args.submit_mode,
        "rules": rules,
    }
    keywords = parse_ids(args.sku_keywords) if args.sku_keywords else []
    if keywords:
        payload["skuKeywords"] = keywords
    data = zzb_client(cfg).tool("preview_pdd_goods_title", payload)
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0
    rows = data.get("rows") or []
    pending = [r for r in rows if r.get("result") == "pending"]
    print("已生成改标题预览：%s 件将修改，%s 件跳过。" % (len(pending), len(rows) - len(pending)))
    if args.target_type == "goods":
        print_table(["商品ID", "原标题", "新标题", "结果"],
                    [[r.get("goodsId", ""), r.get("beforeName", ""), r.get("afterName", ""),
                      r.get("result", "")] for r in rows])
    else:
        print_table(["商品ID", "商品名称", "SKU变更数", "结果"],
                    [[r.get("goodsId", ""), r.get("goodsName", ""), len(r.get("skuChanges") or []),
                      r.get("result", "")] for r in rows])
    print("\n确认凭据：%s（约 5 分钟有效）" % data.get("confirmToken", ""))
    print("下一步：用户确认后执行 `title-confirm --confirm-token %s`。" % data.get("confirmToken", ""))
    return 0


def cmd_title_confirm(args, cfg):
    data = zzb_client(cfg).tool("confirm_pdd_goods_title", {"confirmToken": args.confirm_token, "confirmed": True})
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0
    print("已提交改标题任务，taskId=%s。" % data.get("taskId", ""))
    print("下一步：`title-task --task-id %s` 查询进度。" % data.get("taskId", ""))
    return 0


def cmd_title_task(args, cfg):
    data = zzb_client(cfg).tool("get_pdd_goods_title_task", {"taskId": args.task_id})
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0
    summary = data.get("summary") or {}
    print("任务 %s：%s（成功 %s / 失败 %s / 未知 %s）" % (
        data.get("taskId", ""), data.get("state", ""), summary.get("submitted", 0),
        summary.get("failed", 0), summary.get("unknown", 0)))
    rows = data.get("rows") or []
    if rows:
        print_table(["商品ID", "结果", "说明"],
                    [[r.get("goodsId", ""), r.get("result", ""), r.get("message", "")] for r in rows])
    return 0


def cmd_delete_preview(args, cfg):
    shop_id = resolve_shop(args, cfg)
    ids = parse_ids(args.ids)
    if not ids:
        raise SkillError("请用 --ids 指定要删除的商品ID（草稿类传 commitId）。", "IDS_REQUIRED")
    if len(ids) > 50:
        raise SkillError("单次最多 50 件，请分批。", "TOO_MANY_IDS")
    payload = {"shopId": shop_id, "goodsIds": ids, "source": args.source, "onSalePolicy": args.on_sale_policy}
    if args.source == "draft":
        payload["draftStatus"] = args.draft_status
    data = zzb_client(cfg).tool("preview_pdd_goods_delete", payload)
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0
    rows = data.get("rows") or []
    pending = [r for r in rows if r.get("result") == "pending"]
    print("⚠️ 删除不可恢复。已生成预览：%s 件将删除，%s 件跳过。" % (len(pending), len(rows) - len(pending)))
    print_table(["商品ID/commitId", "商品名称", "初始状态", "结果"],
                [[r.get("goodsId") or r.get("commitId", ""), r.get("goodsName", ""),
                  r.get("status", ""), r.get("result", "") if r.get("result") != "skipped" else (r.get("message") or "跳过")] for r in rows])
    print("\n确认凭据：%s（约 5 分钟有效）" % data.get("confirmToken", ""))
    print("下一步：用户明确确认后执行 `delete-confirm --confirm-token %s`。" % data.get("confirmToken", ""))
    return 0


def cmd_delete_confirm(args, cfg):
    data = zzb_client(cfg).tool("confirm_pdd_goods_delete", {"confirmToken": args.confirm_token, "confirmed": True})
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0
    print("已提交删除任务，taskId=%s。" % data.get("taskId", ""))
    print("下一步：`delete-task --task-id %s` 查询进度。" % data.get("taskId", ""))
    return 0


def cmd_delete_task(args, cfg):
    data = zzb_client(cfg).tool("get_pdd_goods_delete_task", {"taskId": args.task_id})
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0
    summary = data.get("summary") or {}
    print("任务 %s：%s（成功 %s / 失败 %s / 未知 %s）" % (
        data.get("taskId", ""), data.get("state", ""), summary.get("submitted", 0),
        summary.get("failed", 0), summary.get("unknown", 0)))
    rows = data.get("rows") or []
    if rows:
        print_table(["商品ID/commitId", "结果", "说明"],
                    [[r.get("goodsId") or r.get("commitId", ""), r.get("result", ""), r.get("message", "")] for r in rows])
    return 0


def cmd_worklog(args, cfg):
    import datetime
    now = datetime.datetime.now()
    log_dir = args.dir or os.path.join(os.getcwd(), "worklogs")
    os.makedirs(log_dir, exist_ok=True)
    path = os.path.join(log_dir, now.strftime("%Y-%m-%d") + ".md")
    detail = []
    if args.detail_file:
        if not os.path.isfile(args.detail_file):
            raise SkillError("--detail-file 文件不存在：%s" % args.detail_file, "INVALID_DETAIL")
        with open(args.detail_file, "r", encoding="utf-8-sig") as fh:
            detail = json.load(fh)
    elif args.detail_json:
        try:
            detail = json.loads(args.detail_json)
        except json.JSONDecodeError:
            raise SkillError("--detail-json 不是合法 JSON。", "INVALID_DETAIL")
    if not isinstance(detail, list):
        raise SkillError("明细必须是数组。", "INVALID_DETAIL")
    lines = ["## %s %s" % (now.strftime("%H:%M"), args.title or args.action), ""]
    lines.append("- 动作：%s" % args.action)
    if args.shop:
        lines.append("- 店铺：%s" % args.shop)
    if args.count is not None:
        lines.append("- 数量：%s" % args.count)
    if args.result:
        lines.append("- 结果：%s" % args.result)
    if args.cost:
        lines.append("- 费用：%s（上游按各自规则扣费）" % args.cost)
    if detail:
        lines.append("")
        lines.append("| 商品ID | 商品名称 | 结果 | 说明 |")
        lines.append("|---|---|---|---|")
        for item in detail:
            lines.append("| %s | %s | %s | %s |" % (
                item.get("goodsId", ""), item.get("goodsName", ""),
                item.get("result", ""), item.get("message", "")))
    entry = "\n".join(lines)
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("# 工作日志 %s\n\n" % now.strftime("%Y-%m-%d"))
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(entry + "\n\n")
    print(entry)
    print("\n已写入：%s" % path)
    return 0


def platform_client(platform, cfg):
    if platform == "zzb":
        return zzb_client(cfg)
    if platform == "fy":
        client = McpClient(cfg["fyUrl"], session=True)
        if cfg.get("fyToken"):
            client.tool("set_fy_token", {"token": cfg["fyToken"]})
        return client
    raise SkillError("不支持的平台：%s" % platform, "INVALID_PLATFORM")


def cmd_list_tools(args, cfg):
    client = platform_client(args.platform, cfg)
    tools = client.tools()
    if args.json:
        print(json.dumps(tools, ensure_ascii=False, indent=2))
        return 0
    print("%s 共 %s 个工具：" % (args.platform, len(tools)))
    print_table(["工具", "说明", "必填参数"],
                [[t.get("name", ""), str(t.get("description", "")).replace("\n", " "),
                  ", ".join((t.get("inputSchema") or {}).get("required") or []) or "-"] for t in tools])
    return 0


def cmd_call(args, cfg):
    arguments = {}
    if args.args_file:
        if not os.path.isfile(args.args_file):
            raise SkillError("--args-file 文件不存在。", "INVALID_ARGS")
        with open(args.args_file, "r", encoding="utf-8-sig") as fh:
            arguments = json.load(fh)
    elif args.args_json:
        try:
            arguments = json.loads(args.args_json)
        except json.JSONDecodeError:
            raise SkillError("--args-json 不是合法 JSON。", "INVALID_ARGS")
    if not isinstance(arguments, dict):
        raise SkillError("参数必须是 JSON 对象。", "INVALID_ARGS")
    client = platform_client(args.platform, cfg)
    data = client.tool(args.tool, arguments)
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


def parse_ids(value):
    ids = []
    for part in str(value or "").replace("，", ",").replace("\n", ",").split(","):
        part = part.strip()
        if not part:
            continue
        if not part.isdigit():
            raise SkillError("商品ID只能是数字：%s" % part, "INVALID_ID")
        ids.append(part)
    return ids


def build_parser():
    parser = argparse.ArgumentParser(description="电商店铺助手（拼多多/抖店）")
    parser.add_argument("--config", help="config.json 路径")
    parser.add_argument("--json", action="store_true", help="输出原始 JSON")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("check", help="检查两个 MCP 凭证")
    sub.add_parser("shops", help="查询店铺列表")
    sub.add_parser("balance", help="查询飞影积分")

    goods = sub.add_parser("goods", help="查询商品")
    goods.add_argument("--shop-id")
    goods.add_argument("--status", choices=["on_sale", "off_sale", "sold_out"])
    goods.add_argument("--keyword")
    goods.add_argument("--ids")
    goods.add_argument("--page", type=int, default=1)
    goods.add_argument("--page-size", type=int, default=50)

    preview = sub.add_parser("sale-preview", help="生成上下架预览")
    preview.add_argument("--shop-id")
    preview.add_argument("--action", choices=["on_sale", "off_sale"], required=True)
    preview.add_argument("--ids", required=True)

    confirm = sub.add_parser("sale-confirm", help="确认执行上下架")
    confirm.add_argument("--confirm-token", required=True)

    task = sub.add_parser("sale-task", help="查询上下架任务")
    task.add_argument("--task-id", required=True)

    image = sub.add_parser("image-create", help="生成爆款首图")
    image.add_argument("--image-url", required=True)
    image.add_argument("--prompt")
    image.add_argument("--ratio", default="1:1", choices=["1:1", "3:4"])
    image.add_argument("--num", type=int, default=1, choices=[1, 2, 3, 4, 5])

    image_task = sub.add_parser("image-task", help="查询生图任务")
    image_task.add_argument("--task-no", required=True)

    price = sub.add_parser("price-preview", help="生成批量改价预览")
    price.add_argument("--shop-id")
    price.add_argument("--ids", required=True)
    price.add_argument("--mode", required=True, choices=["uniform", "formula", "decimal"])
    price.add_argument("--new-price", type=float)
    price.add_argument("--price-types", default="multi_price,price")
    price.add_argument("--sku-range", default="all", choices=["all", "highest", "lowest"])
    price.add_argument("--price-min", type=float)
    price.add_argument("--price-max", type=float)
    price.add_argument("--price-ratio", type=float)
    price.add_argument("--plus", type=float)
    price.add_argument("--minus", type=float)
    price.add_argument("--result-ratio", type=float)
    price.add_argument("--decimal")

    price_confirm = sub.add_parser("price-confirm", help="确认执行改价")
    price_confirm.add_argument("--confirm-token", required=True)
    price_task = sub.add_parser("price-task", help="查询改价任务")
    price_task.add_argument("--task-id", required=True)

    title = sub.add_parser("title-preview", help="生成批量改标题预览")
    title.add_argument("--shop-id")
    title.add_argument("--ids", required=True)
    title.add_argument("--rules-json", required=True, help='规则数组，例如 [{"type":"affix","prefix":"新品"}]')
    title.add_argument("--target-type", default="goods", choices=["goods", "sku"])
    title.add_argument("--submit-mode", default="publish", choices=["publish", "draft"])
    title.add_argument("--sku-keywords")

    title_confirm = sub.add_parser("title-confirm", help="确认执行改标题")
    title_confirm.add_argument("--confirm-token", required=True)
    title_task = sub.add_parser("title-task", help="查询改标题任务")
    title_task.add_argument("--task-id", required=True)

    delete = sub.add_parser("delete-preview", help="生成批量删除预览（不可恢复）")
    delete.add_argument("--shop-id")
    delete.add_argument("--ids", required=True)
    delete.add_argument("--source", default="goods", choices=["goods", "draft"])
    delete.add_argument("--draft-status", default="draft", choices=["draft", "publishing", "rejected"])
    delete.add_argument("--on-sale-policy", default="skip", choices=["skip", "off_sale_and_delete"])

    delete_confirm = sub.add_parser("delete-confirm", help="确认执行删除")
    delete_confirm.add_argument("--confirm-token", required=True)
    delete_task = sub.add_parser("delete-task", help="查询删除任务")
    delete_task.add_argument("--task-id", required=True)

    worklog = sub.add_parser("worklog", help="写入一条用户可读的工作日志")
    worklog.add_argument("--dir")
    worklog.add_argument("--title")
    worklog.add_argument("--action", required=True)
    worklog.add_argument("--shop")
    worklog.add_argument("--count", type=int)
    worklog.add_argument("--result")
    worklog.add_argument("--cost")
    worklog.add_argument("--detail-json")
    worklog.add_argument("--detail-file")

    list_tools = sub.add_parser("list-tools", help="列出某个平台的全部 MCP 工具")
    list_tools.add_argument("--platform", required=True, choices=["zzb", "fy"])

    call = sub.add_parser("call", help="通用调用任意 MCP 工具（参数用 JSON）")
    call.add_argument("--platform", required=True, choices=["zzb", "fy"])
    call.add_argument("--tool", required=True)
    call.add_argument("--args-json")
    call.add_argument("--args-file")

    # 允许 --json 写在子命令后面
    try:
        for child in parser._subparsers._group_actions[0].choices.values():
            child.add_argument("--json", action="store_true", help="输出原始 JSON")
    except Exception:  # noqa: BLE001 - 解析器结构变化时忽略
        pass
    return parser


HANDLERS = {
    "check": cmd_check,
    "shops": cmd_shops,
    "goods": cmd_goods,
    "sale-preview": cmd_sale_preview,
    "sale-confirm": cmd_sale_confirm,
    "sale-task": cmd_sale_task,
    "price-preview": cmd_price_preview,
    "price-confirm": cmd_price_confirm,
    "price-task": cmd_price_task,
    "title-preview": cmd_title_preview,
    "title-confirm": cmd_title_confirm,
    "title-task": cmd_title_task,
    "delete-preview": cmd_delete_preview,
    "delete-confirm": cmd_delete_confirm,
    "delete-task": cmd_delete_task,
    "image-create": cmd_image_create,
    "image-task": cmd_image_task,
    "balance": cmd_balance,
    "worklog": cmd_worklog,
    "list-tools": cmd_list_tools,
    "call": cmd_call,
}


def main():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:  # noqa: BLE001 - 旧环境忽略
            pass
    parser = build_parser()
    args = parser.parse_args()
    cfg = load_config(args.config)
    handler = HANDLERS[args.command]
    try:
        return handler(args, cfg)
    except SkillError as exc:
        if args.json:
            print(json.dumps({"ok": False, "code": exc.code, "message": str(exc)}, ensure_ascii=False))
        else:
            sys.stderr.write("[%s] %s\n" % (exc.code or "ERROR", exc))
        return 1
    except Exception as exc:  # noqa: BLE001 - 给用户可读错误
        sys.stderr.write("[UNEXPECTED] %s: %s\n" % (type(exc).__name__, exc))
        return 1


_json_mode = False

if __name__ == "__main__":
    sys.exit(main())
