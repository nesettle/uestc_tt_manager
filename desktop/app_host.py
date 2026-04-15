from __future__ import annotations

import argparse
import ctypes
import importlib.util
import json
import logging
import os
import socket
import sys
import threading
import time
import traceback
import urllib.error
import urllib.request
import webbrowser
from dataclasses import dataclass
from pathlib import Path

import uvicorn
import webview

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.runtime import APP_NAME, DESKTOP_ENV_FLAG, initialize_runtime_environment


HOST = "127.0.0.1"
PORT = 8050
APP_URL = f"http://{HOST}:{PORT}/"
HEALTH_URL = f"http://{HOST}:{PORT}/api/config"
MUTEX_NAME = "Global\\UESTC_TT_Manager_Desktop"
STARTUP_TIMEOUT_SECONDS = 30
WINDOW_WIDTH = 1440
WINDOW_HEIGHT = 960
WEBVIEW_GUI = "qt"


@dataclass
class DesktopStartResult:
    ok: bool
    message: str
    detail: str = ""
    suggestion: str = ""
    log_file: Path | None = None


class DesktopLaunchError(RuntimeError):
    def __init__(self, message: str, suggestion: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.suggestion = suggestion


class SingleInstanceGuard:
    def __init__(self, name: str) -> None:
        self.name = name
        self.handle = None
        self.acquired = False

    def acquire(self) -> bool:
        kernel32 = ctypes.windll.kernel32
        self.handle = kernel32.CreateMutexW(None, False, self.name)
        self.acquired = kernel32.GetLastError() != 183
        return self.acquired

    def release(self) -> None:
        if self.handle and self.acquired:
            ctypes.windll.kernel32.ReleaseMutex(self.handle)
        if self.handle:
            ctypes.windll.kernel32.CloseHandle(self.handle)
            self.handle = None
        self.acquired = False


def render_status_html(title: str, detail: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <title>{APP_NAME}</title>
  <style>
    body {{
      margin: 0;
      font-family: "Microsoft YaHei UI", "Segoe UI", sans-serif;
      background: linear-gradient(135deg, #eef6ff, #f7fafc);
      color: #17324d;
    }}
    .wrap {{
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 32px;
    }}
    .card {{
      width: min(680px, 100%);
      background: rgba(255,255,255,0.92);
      border-radius: 18px;
      padding: 28px 30px;
      box-shadow: 0 22px 60px rgba(23, 50, 77, 0.12);
    }}
    .eyebrow {{
      margin: 0 0 10px;
      font-size: 12px;
      letter-spacing: 0.16em;
      text-transform: uppercase;
      color: #4b79a5;
    }}
    h1 {{
      margin: 0 0 14px;
      font-size: 28px;
    }}
    p {{
      margin: 0;
      line-height: 1.7;
      white-space: pre-wrap;
    }}
    .spinner {{
      width: 18px;
      height: 18px;
      border: 3px solid #c9def2;
      border-top-color: #2c6aa6;
      border-radius: 999px;
      animation: spin 0.8s linear infinite;
      display: inline-block;
      vertical-align: middle;
      margin-right: 10px;
    }}
    @keyframes spin {{
      to {{ transform: rotate(360deg); }}
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <p class="eyebrow">UESTC TT Manager Desktop</p>
      <h1>{title}</h1>
      <p><span class="spinner"></span>{detail}</p>
    </div>
  </div>
</body>
</html>
"""


def render_error_html(message: str, detail: str, suggestion: str, log_file: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <title>{APP_NAME} - 启动失败</title>
  <style>
    body {{
      margin: 0;
      font-family: "Microsoft YaHei UI", "Segoe UI", sans-serif;
      background: linear-gradient(135deg, #fff0f0, #fff8f2);
      color: #4d1b1b;
    }}
    .wrap {{
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 32px;
    }}
    .card {{
      width: min(780px, 100%);
      background: rgba(255,255,255,0.95);
      border-radius: 18px;
      padding: 28px 30px;
      box-shadow: 0 22px 60px rgba(120, 36, 36, 0.12);
    }}
    h1 {{ margin: 0 0 14px; font-size: 28px; }}
    h2 {{ margin: 24px 0 8px; font-size: 16px; }}
    p, pre {{ margin: 0; line-height: 1.7; white-space: pre-wrap; }}
    pre {{
      background: #fff6f6;
      padding: 12px;
      border-radius: 12px;
      overflow: auto;
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <h1>启动失败</h1>
      <p>{message}</p>
      <h2>详情</h2>
      <pre>{detail}</pre>
      <h2>建议</h2>
      <pre>{suggestion or "请先查看日志定位问题。"}</pre>
      <h2>日志文件</h2>
      <pre>{log_file}</pre>
    </div>
  </div>
</body>
</html>
"""


def probe_service(timeout: float = 2.0) -> tuple[bool, str]:
    request = urllib.request.Request(HEALTH_URL, headers={"User-Agent": "uestc-tt-manager-desktop"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if isinstance(payload, dict):
            return True, "本地服务已可访问。"
        return False, "健康检查返回了非对象 JSON。"
    except urllib.error.HTTPError as exc:
        return False, f"健康检查返回 HTTP {exc.code}。"
    except urllib.error.URLError as exc:
        return False, f"无法连接到健康检查接口：{exc.reason}"
    except Exception as exc:  # pragma: no cover
        return False, f"健康检查异常：{exc}"


def port_in_use(host: str = HOST, port: int = PORT) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1.0)
        return sock.connect_ex((host, port)) == 0


def show_native_message(title: str, message: str) -> None:
    ctypes.windll.user32.MessageBoxW(0, message, title, 0x10)


def has_qt_runtime() -> bool:
    required_modules = [
        "qtpy",
        "PySide6",
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        "PySide6.QtNetwork",
        "PySide6.QtWebChannel",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
    ]
    return all(importlib.util.find_spec(module) is not None for module in required_modules)


class DesktopAppHost:
    def __init__(self) -> None:
        os.environ.setdefault(DESKTOP_ENV_FLAG, "1")
        os.environ.setdefault("PYWEBVIEW_GUI", WEBVIEW_GUI)
        self.paths = initialize_runtime_environment()
        self.window = None
        self.server = None
        self.server_thread: threading.Thread | None = None
        self.guard = SingleInstanceGuard(MUTEX_NAME)
        self.log_dir = self.paths.runs_dir / "desktop"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / f"desktop-{time.strftime('%Y%m%d-%H%M%S')}.log"
        self.logger = self._configure_logger()

    def _configure_logger(self) -> logging.Logger:
        logger = logging.getLogger("uestc_tt_manager.desktop")
        logger.setLevel(logging.INFO)
        logger.handlers.clear()
        file_handler = logging.FileHandler(self.log_file, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(file_handler)
        return logger

    def _update_status(self, title: str, detail: str) -> None:
        self.logger.info("%s - %s", title, detail)
        if self.window is not None:
            self.window.load_html(render_status_html(title, detail))

    def _show_error(self, result: DesktopStartResult) -> None:
        self.logger.error("%s | %s | %s", result.message, result.detail, result.suggestion)
        if self.window is not None:
            self.window.load_html(
                render_error_html(
                    result.message,
                    result.detail or result.message,
                    result.suggestion,
                    str(result.log_file or self.log_file),
                )
            )
        else:
            show_native_message(APP_NAME, f"{result.message}\n\n{result.suggestion}")

    def _start_server(self) -> None:
        from app.main import app

        config = uvicorn.Config(app, host=HOST, port=PORT, log_level="info", access_log=False)
        self.server = uvicorn.Server(config)
        self.server.run()

    def _start_server_thread(self) -> None:
        self.server_thread = threading.Thread(
            target=self._start_server,
            daemon=True,
            name="uestc-tt-desktop-server",
        )
        self.server_thread.start()

    def _wait_until_ready(self, timeout_seconds: int = STARTUP_TIMEOUT_SECONDS) -> None:
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            ready, detail = probe_service(timeout=1.0)
            if ready:
                self.logger.info("服务已就绪: %s", detail)
                return
            if self.server_thread and not self.server_thread.is_alive():
                raise DesktopLaunchError(
                    "本地服务启动后很快退出。",
                    f"请打开日志文件查看详情：{self.log_file}",
                )
            time.sleep(1)
        raise DesktopLaunchError(
            f"本地服务在 {timeout_seconds} 秒内未完成启动。",
            f"请查看日志文件：{self.log_file}",
        )

    def bootstrap(self) -> DesktopStartResult:
        try:
            if not self.guard.acquire():
                raise DesktopLaunchError("程序已经在运行。", "请切回已打开的窗口，或先关闭现有实例。")

            self._update_status("检查运行环境", "正在检查 Qt 运行库、Playwright 和用户数据目录。")
            if not has_qt_runtime():
                raise DesktopLaunchError(
                    "未检测到桌面窗口依赖。",
                    "当前桌面版需要内置 Qt 运行库（qtpy + PySide6 + QtWebEngine）。请重新使用新的桌面发行版安装包。",
                )

            self._update_status("检查本地服务", f"正在探测 {HEALTH_URL}")
            ready, detail = probe_service()
            if ready:
                self.logger.info("复用现有服务: %s", detail)
                return DesktopStartResult(ok=True, message="已复用现有本地服务。", log_file=self.log_file)

            if port_in_use():
                raise DesktopLaunchError(
                    "端口 8050 已被其他程序占用。",
                    "请先关闭占用 8050 端口的程序，再重新打开桌面版。",
                )

            self._update_status("启动本地服务", "正在后台启动 UESTC TT Manager 服务。")
            self._start_server_thread()
            self._update_status("等待页面可访问", "首次启动可能需要几秒钟，请稍候。")
            self._wait_until_ready()
            return DesktopStartResult(ok=True, message="服务已就绪。", log_file=self.log_file)
        except DesktopLaunchError as exc:
            return DesktopStartResult(
                ok=False,
                message=exc.message,
                detail=traceback.format_exc(),
                suggestion=exc.suggestion,
                log_file=self.log_file,
            )
        except Exception as exc:  # pragma: no cover
            return DesktopStartResult(
                ok=False,
                message=f"桌面版启动异常：{exc}",
                detail=traceback.format_exc(),
                suggestion="请打开日志文件查看详细错误。",
                log_file=self.log_file,
            )

    def run_window(self) -> None:
        self.window = webview.create_window(
            APP_NAME,
            html=render_status_html("准备启动", "正在初始化桌面版，请稍候。"),
            width=WINDOW_WIDTH,
            height=WINDOW_HEIGHT,
            min_size=(1180, 760),
        )

        def startup() -> None:
            result = self.bootstrap()
            if result.ok:
                self.window.load_url(APP_URL)
            else:
                self._show_error(result)

        webview.start(startup, gui=WEBVIEW_GUI, debug=not self.paths.frozen)
        self.guard.release()

    def smoke_test(self) -> int:
        result: DesktopStartResult = DesktopStartResult(
            ok=False,
            message="桌面窗口未完成初始化。",
            log_file=self.log_file,
        )

        self.window = webview.create_window(
            APP_NAME,
            html=render_status_html("桌面版自检", "正在验证 Qt 窗口初始化，请稍候。"),
            width=480,
            height=320,
            hidden=True,
        )

        def startup() -> None:
            nonlocal result
            result = self.bootstrap()
            try:
                self.window.destroy()
            except Exception:
                self.logger.exception("关闭 smoke test 窗口失败")

        try:
            webview.start(startup, gui=WEBVIEW_GUI, debug=not self.paths.frozen)
        except Exception as exc:
            result = DesktopStartResult(
                ok=False,
                message=f"桌面窗口初始化失败：{exc}",
                detail=traceback.format_exc(),
                suggestion="这通常表示 Qt 运行库或 QtWebEngine 没有被正确打包。",
                log_file=self.log_file,
            )

        print(f"ok={result.ok}")
        print(f"message={result.message}")
        if result.suggestion:
            print(f"suggestion={result.suggestion}")
        print(f"log_file={result.log_file}")
        self.guard.release()
        return 0 if result.ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="UESTC TT Manager 桌面版")
    parser.add_argument("--smoke-test", action="store_true", help="只做桌面启动链路测试，不打开窗口。")
    parser.add_argument("--open-browser", action="store_true", help="调试用途：启动成功后改为打开外部浏览器。")
    args = parser.parse_args(argv)

    host = DesktopAppHost()
    if args.smoke_test:
        return host.smoke_test()
    if args.open_browser:
        result = host.bootstrap()
        if result.ok:
            webbrowser.open(APP_URL)
            host.guard.release()
            return 0
        host._show_error(result)
        host.guard.release()
        return 1
    host.run_window()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
