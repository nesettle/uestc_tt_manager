from __future__ import annotations

import asyncio
import csv
import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import aiohttp

from app.domain import Recipient
from app.services.common import ensure_run_dir, normalize_qq, write_json
from app.settings import AppConfig
from app.tasks import TaskContext


RESULT_FIELDS = [
    "qq",
    "name",
    "college",
    "mode",
    "status",
    "message_id",
    "error",
    "sent_at",
    "message_preview",
]

CANNOT_TEMP_SESSION_PATTERNS = [
    "temp",
    "临时",
    "not_friend",
    "not friend",
    "好友",
    "权限",
]


@dataclass
class ResultRow:
    qq: str
    name: str
    college: str
    mode: str
    status: str
    message_id: str
    error: str
    sent_at: str
    message_preview: str


def load_ws_server_config(config_path: Path) -> dict[str, Any]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    servers = config.get("network", {}).get("websocketServers", [])
    enabled = [item for item in servers if item.get("enable")]
    if not enabled:
        raise RuntimeError(f"未在 {config_path} 中找到已启用的 websocketServers 配置")
    server = enabled[0]
    for key in ("host", "port", "token"):
        if not server.get(key):
            raise RuntimeError(f"WebSocket 服务端配置缺少字段 {key}")
    return server


def truncate_preview(message: str, width: int = 120) -> str:
    return message if len(message) <= width else message[: width - 3] + "..."


def build_message(template: str, recipient: Recipient) -> str:
    return (recipient.message or template).format(name=recipient.name)


def response_error_text(response: dict[str, Any]) -> str:
    message = response.get("message")
    retcode = response.get("retcode")
    status = response.get("status")
    if message or retcode or status:
        return f"status={status}, retcode={retcode}, message={message}"
    return json.dumps(response, ensure_ascii=False)


def classify_temp_session_error(error_text: str) -> str:
    lowered = error_text.lower()
    if any(pattern in lowered for pattern in CANNOT_TEMP_SESSION_PATTERNS):
        return "cannot_temp_session"
    return "api_failed"


class NapCatWsClient:
    def __init__(self, host: str, port: int, token: str) -> None:
        self.url = f"ws://{host}:{port}"
        self.headers = {"Authorization": f"Bearer {token}"}
        self.session: aiohttp.ClientSession | None = None
        self.ws: aiohttp.ClientWebSocketResponse | None = None

    async def __aenter__(self) -> "NapCatWsClient":
        timeout = aiohttp.ClientTimeout(total=20)
        self.session = aiohttp.ClientSession(timeout=timeout)
        self.ws = await self.session.ws_connect(self.url, headers=self.headers)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self.ws is not None:
            await self.ws.close()
        if self.session is not None:
            await self.session.close()

    async def request(self, action: str, params: dict[str, Any] | None = None, timeout: float = 15.0) -> dict[str, Any]:
        if self.ws is None:
            raise RuntimeError("WebSocket 尚未连接")
        echo = uuid.uuid4().hex
        payload = {"action": action, "params": params or {}, "echo": echo}
        await self.ws.send_json(payload)
        deadline = asyncio.get_running_loop().time() + timeout
        while True:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                raise TimeoutError(f"{action} 响应超时")
            msg = await self.ws.receive(timeout=remaining)
            if msg.type == aiohttp.WSMsgType.TEXT:
                data = json.loads(msg.data)
                if data.get("echo") == echo:
                    return data
            elif msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED):
                raise RuntimeError("WebSocket 已关闭")
            elif msg.type == aiohttp.WSMsgType.ERROR:
                raise RuntimeError("WebSocket 错误")


async def verify_group_member(client: NapCatWsClient, group_id: int, user_id: int) -> tuple[bool, str]:
    response = await client.request(
        "get_group_member_info",
        {"group_id": group_id, "user_id": user_id, "no_cache": True},
    )
    if response.get("status") == "ok" and response.get("retcode") == 0:
        return True, ""
    return False, response_error_text(response)


def write_results(run_dir: Path, rows: list[ResultRow]) -> None:
    csv_path = run_dir / "results.csv"
    jsonl_path = run_dir / "results.jsonl"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))
    with jsonl_path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(asdict(row), ensure_ascii=False) + "\n")


def recipients_from_payload(items: list[dict[str, Any]], template: str) -> list[Recipient]:
    results: list[Recipient] = []
    for item in items:
        results.append(
            Recipient(
                qq=normalize_qq(item.get("qq", "")),
                name=str(item.get("name", "")).strip(),
                college=str(item.get("college", "")).strip(),
                message=str(item.get("message", "")).strip() or template,
            )
        )
    return results


async def _precheck_async(ctx: TaskContext, config: AppConfig, recipients: list[Recipient]) -> dict:
    if not config.event_group_id.strip():
        raise RuntimeError("请先在系统配置中填写成电杯赛事群群号")
    ws_config = load_ws_server_config(Path(config.napcat_config_path))
    run_dir = ensure_run_dir("notify-precheck")
    rows: list[ResultRow] = []
    async with NapCatWsClient(
        host=ws_config["host"],
        port=int(ws_config["port"]),
        token=str(ws_config["token"]),
    ) as client:
        login_response = await client.request("get_login_info")
        if login_response.get("status") != "ok" or login_response.get("retcode") != 0:
            raise RuntimeError("get_login_info 失败: " + response_error_text(login_response))
        login_info = login_response.get("data") or {}
        total = len(recipients)
        for index, recipient in enumerate(recipients, start=1):
            ctx.set_progress(index, total, f"预检通知对象：{recipient.name}")
            message = build_message(config.notify_template, recipient)
            if not recipient.qq:
                rows.append(
                    ResultRow("", recipient.name, recipient.college, "precheck", "missing_qq", "", "缺少有效 QQ", "", truncate_preview(message))
                )
                continue
            try:
                is_member, member_error = await verify_group_member(client, int(config.event_group_id), int(recipient.qq))
            except Exception as exc:
                rows.append(
                    ResultRow(
                        recipient.qq,
                        recipient.name,
                        recipient.college,
                        "precheck",
                        "transport_failed",
                        "",
                        str(exc),
                        "",
                        truncate_preview(message),
                    )
                )
                continue
            rows.append(
                ResultRow(
                    recipient.qq,
                    recipient.name,
                    recipient.college,
                    "precheck",
                    "precheck_ok" if is_member else "group_member_not_found",
                    "",
                    "" if is_member else member_error,
                    "",
                    truncate_preview(message),
                )
            )
    write_results(run_dir, rows)
    summary = {"run_dir": str(run_dir), "login_info": login_info, "rows": [asdict(row) for row in rows]}
    write_json(run_dir / "summary.json", summary)
    return summary


async def _send_async(ctx: TaskContext, config: AppConfig, recipients: list[Recipient]) -> dict:
    if not config.event_group_id.strip():
        raise RuntimeError("请先在系统配置中填写成电杯赛事群群号")
    ws_config = load_ws_server_config(Path(config.napcat_config_path))
    run_dir = ensure_run_dir("notify-send")
    rows: list[ResultRow] = []
    async with NapCatWsClient(
        host=ws_config["host"],
        port=int(ws_config["port"]),
        token=str(ws_config["token"]),
    ) as client:
        login_response = await client.request("get_login_info")
        if login_response.get("status") != "ok" or login_response.get("retcode") != 0:
            raise RuntimeError("get_login_info 失败: " + response_error_text(login_response))
        login_info = login_response.get("data") or {}
        total = len(recipients)
        for index, recipient in enumerate(recipients, start=1):
            ctx.set_progress(index, total, f"发送通知：{recipient.name}")
            message = build_message(config.notify_template, recipient)
            sent_at = datetime.now().isoformat(timespec="seconds")
            try:
                if not recipient.qq:
                    rows.append(
                        ResultRow("", recipient.name, recipient.college, "send", "missing_qq", "", "缺少有效 QQ", sent_at, truncate_preview(message))
                    )
                    continue
                is_member, member_error = await verify_group_member(client, int(config.event_group_id), int(recipient.qq))
                if not is_member:
                    rows.append(
                        ResultRow(recipient.qq, recipient.name, recipient.college, "send", "group_member_not_found", "", member_error, sent_at, truncate_preview(message))
                    )
                    continue
                response = await client.request(
                    "send_private_msg",
                    {
                        "user_id": int(recipient.qq),
                        "group_id": int(config.event_group_id),
                        "message": message,
                    },
                )
                if response.get("status") == "ok" and response.get("retcode") == 0:
                    data = response.get("data") or {}
                    rows.append(
                        ResultRow(recipient.qq, recipient.name, recipient.college, "send", "sent", str(data.get("message_id", "")), "", sent_at, truncate_preview(message))
                    )
                else:
                    error_text = response_error_text(response)
                    rows.append(
                        ResultRow(
                            recipient.qq,
                            recipient.name,
                            recipient.college,
                            "send",
                            classify_temp_session_error(error_text),
                            "",
                            error_text,
                            sent_at,
                            truncate_preview(message),
                        )
                    )
            except Exception as exc:
                rows.append(
                    ResultRow(
                        recipient.qq,
                        recipient.name,
                        recipient.college,
                        "send",
                        "transport_failed",
                        "",
                        str(exc),
                        sent_at,
                        truncate_preview(message),
                    )
                )
    write_results(run_dir, rows)
    summary = {"run_dir": str(run_dir), "login_info": login_info, "rows": [asdict(row) for row in rows]}
    write_json(run_dir / "summary.json", summary)
    return summary


def precheck(ctx: TaskContext, config: AppConfig, payload_rows: list[dict[str, Any]]) -> dict:
    recipients = recipients_from_payload(payload_rows, config.notify_template)
    return asyncio.run(_precheck_async(ctx, config, recipients))


def send(ctx: TaskContext, config: AppConfig, payload_rows: list[dict[str, Any]]) -> dict:
    recipients = recipients_from_payload(payload_rows, config.notify_template)
    return asyncio.run(_send_async(ctx, config, recipients))
