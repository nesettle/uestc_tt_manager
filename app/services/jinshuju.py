from __future__ import annotations

from html import unescape
import json
from datetime import datetime
from pathlib import Path
from tempfile import mkdtemp
import re
import shutil
import time
from typing import Any
from urllib.request import urlopen

from playwright.sync_api import BrowserContext, Error, Locator, Page, sync_playwright

from app.settings import AppConfig, FORM_EXPORTS_DIR
from app.tasks import TaskContext


FORM_TYPES = {"报名", "表单", "问卷", "收款"}
IGNORED_HOME_LINES = {
    "金数据",
    "表单",
    "收款",
    "对外查询",
    "营销应用",
    "联系人",
    "门户",
    "模板",
    "试用企业高级版",
    "套餐升级",
    "创建",
    "我的表单",
    "与我共享",
    "我的收藏",
    "填表记录",
    "回收站",
    "标签",
    "创建文件夹",
}


def click_first_visible(locator: Locator, timeout_ms: int = 10000) -> bool:
    try:
        locator.first.wait_for(state="visible", timeout=timeout_ms)
        locator.first.click()
        return True
    except Exception:
        return False


def save_debug_artifacts(page: Page, run_dir: Path, name: str) -> list[str]:
    artifacts: list[str] = []
    try:
        html_path = run_dir / f"{name}.html"
        html_path.write_text(page.content(), encoding="utf-8")
        artifacts.append(str(html_path))
    except Exception:
        pass
    try:
        png_path = run_dir / f"{name}.png"
        page.screenshot(path=str(png_path), full_page=True)
        artifacts.append(str(png_path))
    except Exception:
        pass
    return artifacts


def normalize_form_title(value: str) -> str:
    cleaned = (value or "").strip()
    cleaned = re.sub(r"^\[(?:新|NEW)\]\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned


def sanitize_export_filename(value: str) -> str:
    cleaned = normalize_form_title(value) or "form"
    cleaned = re.sub(r'[\\/:*?"<>|]+', "_", cleaned)
    cleaned = re.sub(r"\s+", "_", cleaned).strip("._ ")
    return cleaned[:80] or "form"


def archive_export_copy(
    export_file: Path,
    *,
    export_tag: str,
    form_title: str | None,
    archive_root: Path = FORM_EXPORTS_DIR,
) -> Path:
    archive_dir = archive_root / export_tag
    archive_dir.mkdir(parents=True, exist_ok=True)
    base_name = sanitize_export_filename(form_title or export_tag)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = archive_dir / f"{timestamp}-{base_name}{export_file.suffix}"
    counter = 1
    while target.exists():
        target = archive_dir / f"{timestamp}-{base_name}-{counter}{export_file.suffix}"
        counter += 1
    shutil.copy2(export_file, target)
    return target


def wait_for_login(page: Page, home_url: str, timeout_ms: int = 300000) -> None:
    page.goto(home_url, wait_until="domcontentloaded", timeout=timeout_ms)
    deadline = time.monotonic() + (timeout_ms / 1000)
    while time.monotonic() < deadline:
        current_url = page.url
        if "jinshuju.net" not in current_url:
            page.wait_for_timeout(1000)
            continue
        if "/signin" in current_url or "/login" in current_url:
            page.wait_for_timeout(1000)
            continue
        try:
            body_text = page.locator("body").inner_text(timeout=5000)
        except Exception:
            body_text = ""
        try:
            page_html = page.content()
        except Exception:
            page_html = ""
        if "我的表单" in body_text or "/forms/" in page_html or "/home" in current_url:
            return
        page.wait_for_timeout(1000)
    raise RuntimeError("金数据登录未完成，请在打开的浏览器中完成登录后重试")


def parse_forms_from_home_text(page_text: str) -> list[dict[str, str]]:
    lines = [line.strip() for line in page_text.splitlines() if line.strip()]
    if not lines:
        return []
    start_index = 0
    my_form_positions = [index for index, line in enumerate(lines) if line == "我的表单"]
    if my_form_positions:
        start_index = my_form_positions[-1] + 1
    results: list[dict[str, str]] = []
    seen: set[str] = set()
    for index in range(start_index + 2, len(lines)):
        form_type = lines[index - 2]
        count_text = lines[index - 1]
        title = lines[index]
        if form_type not in FORM_TYPES:
            continue
        if not re.fullmatch(r"\d+", count_text):
            continue
        if title in IGNORED_HOME_LINES:
            continue
        if len(title) < 2:
            continue
        if title in seen:
            continue
        seen.add(title)
        results.append(
            {
                "title": title,
                "url": "",
                "entries_url": "",
                "updated_at": f"{form_type} | {count_text}",
            }
        )
    return results


def extract_forms_from_home_html(home_html: str, home_url: str = "https://jinshuju.net/home") -> list[dict[str, str]]:
    base_match = re.match(r"^https?://[^/]+", home_url or "")
    base_url = base_match.group(0) if base_match else "https://jinshuju.net"
    pieces = re.split(r'<div class="sortable-item-wrap"[^>]*role="Form"[^>]*>', home_html)
    results: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for piece in pieces[1:]:
        href_match = re.search(r'href="(?P<href>/forms/[^"]+/entries)"', piece)
        if not href_match:
            continue
        href = href_match.group("href").strip()
        span_matches = re.findall(r"<span[^>]*>([^<]+)</span>", piece)
        title = ""
        for raw in reversed(span_matches):
            candidate = unescape(raw).strip()
            if not candidate or candidate in {"编辑", "设置", "数据"}:
                continue
            title = candidate
            break
        if not title:
            continue
        full_url = href if href.startswith("http") else f"{base_url}{href}"
        key = (title, full_url)
        if key in seen:
            continue
        seen.add(key)
        results.append(
            {
                "title": title,
                "url": full_url,
                "entries_url": full_url,
                "updated_at": "",
            }
        )
    return results


def load_home_dashboard(page: Page, home_url: str, timeout_ms: int = 120000) -> tuple[str, str]:
    wait_for_login(page, home_url, timeout_ms=timeout_ms)
    deadline = time.monotonic() + (timeout_ms / 1000)
    last_body = ""
    last_html = ""
    while time.monotonic() < deadline:
        current_url = page.url
        if "/signin" in current_url or "/login" in current_url:
            raise RuntimeError("金数据当前处于登录页，请先重新登录")
        try:
            last_body = page.locator("body").inner_text(timeout=5000)
        except Exception:
            last_body = ""
        try:
            last_html = page.content()
        except Exception:
            last_html = ""
        if "/forms/" in last_html and (parse_forms_from_home_text(last_body) or "我的表单" in last_body):
            return last_body, last_html
        page.wait_for_timeout(1000)
    raise RuntimeError("金数据首页未在预期时间内加载出表单列表")


def discover_forms_from_page(page: Page, home_url: str) -> list[dict[str, str]]:
    body_text, home_html = load_home_dashboard(page, home_url)
    html_items = extract_forms_from_home_html(home_html, home_url=home_url)
    text_items = parse_forms_from_home_text(body_text)
    text_meta_exact = {item["title"]: item for item in text_items}
    text_meta_normalized: dict[str, dict[str, str]] = {}
    for item in text_items:
        text_meta_normalized.setdefault(normalize_form_title(item["title"]), item)
    if html_items:
        for item in html_items:
            meta = text_meta_exact.get(item["title"]) or text_meta_normalized.get(normalize_form_title(item["title"]))
            if meta:
                item["updated_at"] = meta.get("updated_at", "")
        return html_items
    return text_items


def resolve_entries_url(page: Page, home_url: str, form_title: str) -> str:
    wanted_exact = form_title.strip()
    wanted_normalized = normalize_form_title(form_title)
    candidates = discover_forms_from_page(page, home_url)
    for item in candidates:
        if item["title"].strip() == wanted_exact and item.get("entries_url"):
            return item["entries_url"]
    for item in candidates:
        if normalize_form_title(item["title"]) == wanted_normalized and item.get("entries_url"):
            return item["entries_url"]
    raise RuntimeError(f"未在金数据首页找到表单：{form_title}")


def click_entries_link_from_home(page: Page, home_url: str, entries_url: str) -> None:
    _, home_html = load_home_dashboard(page, home_url)
    relative_url = re.sub(r"^https?://[^/]+", "", entries_url).strip() or entries_url.strip()
    if not relative_url.startswith("/"):
        relative_url = f"/{relative_url.lstrip('/')}"
    if relative_url not in home_html:
        raise RuntimeError(f"首页中未找到表单入口：{entries_url}")
    page.locator(f"a[href='{relative_url}']").first.wait_for(state="attached", timeout=30000)
    with page.expect_navigation(wait_until="domcontentloaded", timeout=120000):
        try:
            page.locator(f"a[href='{relative_url}']").first.click()
        except Exception:
            page.evaluate(
                """
                (href) => {
                  const link = document.querySelector(`a[href="${href}"]`);
                  if (!link) throw new Error(`missing href: ${href}`);
                  link.click();
                }
                """,
                relative_url,
            )


def wait_for_entries_ready(page: Page, timeout_ms: int = 60000) -> None:
    page.wait_for_function(
        """
        () => {
          const body = document.body;
          const exportButton = document.querySelector('#open-search-entries-btn');
          const toolbar = document.querySelector("[class*='grid-toolbar__export-excel']");
          const title = document.title || '';
          return (
            (body && body.classList.contains('entries-index-page')) ||
            !!exportButton ||
            !!toolbar ||
            title.includes('数据')
          );
        }
        """,
        timeout=timeout_ms,
    )


def open_entries_page(page: Page, home_url: str, form_title: str | None, entries_url: str | None) -> None:
    target_url = (entries_url or "").strip()
    if not target_url:
        if not form_title:
            raise RuntimeError("必须提供表单标题或 entries_url")
        target_url = resolve_entries_url(page, home_url, form_title)
    try:
        page.goto(target_url, wait_until="domcontentloaded", timeout=120000)
    except Error:
        click_entries_link_from_home(page, home_url, target_url)
    wait_for_entries_ready(page)


def current_form_token(page: Page) -> str:
    match = re.search(r"/forms/([^/]+)/entries", page.url)
    if match:
        return match.group(1)
    token = page.locator("#root").get_attribute("data-form-token")
    if token:
        return token.strip()
    raise RuntimeError("未能识别当前金数据表单 token")


def submit_export_job(page: Page, form_token: str, download_format: str) -> None:
    sheet_format = "excel" if download_format == "xlsx" else "csv"
    result = page.evaluate(
        """
        async ({formToken, sheetFormat}) => {
          const csrf = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
          const body = new URLSearchParams();
          body.set('utf8', '✓');
          body.set('export_job[row_scope]', 'all');
          body.set('export_job[column_scope]', 'all');
          body.set('export_job[sheet_format]', sheetFormat);
          const response = await fetch(`/forms/${formToken}/export_job`, {
            method: 'POST',
            credentials: 'include',
            headers: {
              'X-CSRF-Token': csrf,
              'X-Requested-With': 'XMLHttpRequest',
              'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
              'Accept': '*/*'
            },
            body: body.toString(),
          });
          return {status: response.status, text: await response.text()};
        }
        """,
        {"formToken": form_token, "sheetFormat": sheet_format},
    )
    status_code = int(result.get("status", 0))
    response_text = str(result.get("text", ""))
    if status_code in {200, 201}:
        return
    if status_code == 422 and "已存在导出任务" in response_text:
        return
    raise RuntimeError(f"创建金数据导出任务失败: HTTP {status_code}")


def wait_for_export_download_url(page: Page, form_token: str, timeout_ms: int = 240000) -> str:
    deadline = time.monotonic() + (timeout_ms / 1000)
    last_payload: dict[str, Any] | None = None
    while time.monotonic() < deadline:
        payload = page.evaluate(
            """
            async (formToken) => {
              const response = await fetch(`/forms/${formToken}/export_job`, {
                credentials: 'include',
                headers: {'X-Requested-With': 'XMLHttpRequest', 'Accept': '*/*'}
              });
              const text = await response.text();
              try {
                return JSON.parse(text);
              } catch (error) {
                return {status: 'unknown', raw: text, http_status: response.status};
              }
            }
            """,
            form_token,
        )
        last_payload = payload
        status = str(payload.get("status", "")).lower()
        if status == "success" and payload.get("url"):
            return str(payload["url"])
        if status in {"failed", "error"}:
            raise RuntimeError(f"金数据导出失败: {payload.get('reason') or payload}")
        time.sleep(2)
    raise RuntimeError(f"等待金数据导出下载链接超时: {last_payload}")


def download_export_url(download_url: str, run_dir: Path, download_format: str) -> Path:
    extension = ".xlsx" if download_format == "xlsx" else ".csv"
    target = run_dir / f"jinshuju_export{extension}"
    target.parent.mkdir(parents=True, exist_ok=True)
    with urlopen(download_url) as response:
        target.write_bytes(response.read())
    return target


def click_more_and_export(page: Page) -> bool:
    toolbar = page.locator("body")
    direct_export = toolbar.get_by_role("button", name="导出", exact=True)
    if click_first_visible(direct_export, timeout_ms=5000):
        return True

    direct_export_text = toolbar.get_by_text("导出", exact=True)
    if click_first_visible(direct_export_text, timeout_ms=5000):
        return True

    more_button = page.locator(
        "xpath=.//*[@id='open-search-entries-btn']"
        "/ancestor::div[contains(@class,'QueryAndShareAction_share-entries__')]"
        "/following-sibling::*[1]//div[contains(@class,'ant-dropdown-trigger')]/button"
    ).first
    if not more_button.count():
        raise RuntimeError("未找到数据页工具栏中的三点菜单按钮")
    if not click_first_visible(more_button, timeout_ms=5000):
        raise RuntimeError("三点菜单按钮点击失败")
    page.wait_for_function(
        """
        () => [...document.querySelectorAll('li[role="menuitem"]')].some((el) => {
          const style = window.getComputedStyle(el);
          const rect = el.getBoundingClientRect();
          return style.visibility !== 'hidden' && style.display !== 'none' && rect.width > 0 && rect.height > 0;
        })
        """,
        timeout=5000,
    )
    export_menu_item = page.locator("li.ant-dropdown-menu-item[data-menu-id*='exportEntry']")
    if click_first_visible(export_menu_item, timeout_ms=5000):
        return True
    fallback_menu_item = page.locator("li.ant-dropdown-menu-item").nth(1)
    if click_first_visible(fallback_menu_item, timeout_ms=5000):
        return True
    raise RuntimeError("打开菜单后未找到导出数据项")


def pick_download_format(page: Page, download_format: str) -> None:
    page.wait_for_function(
        """
        () => {
          const formatLabel = document.querySelector("label[for='export_job_sheet_format_excel'], label[for='export_job_sheet_format_csv']");
          const privacyConfirm = document.querySelector("#export_privacy_confirm_modal a.confirm");
          const downloadLink = document.querySelector(".grid-toolbar__export-excel a[data-role='download']");
          const isVisible = (el) => {
            if (!el) return false;
            const style = window.getComputedStyle(el);
            const rect = el.getBoundingClientRect();
            return style.visibility !== 'hidden' && style.display !== 'none' && rect.width > 0 && rect.height > 0;
          };
          return isVisible(formatLabel) || isVisible(privacyConfirm) || isVisible(downloadLink);
        }
        """,
        timeout=30000,
    )

    format_label = (
        "label[for='export_job_sheet_format_excel']"
        if download_format == "xlsx"
        else "label[for='export_job_sheet_format_csv']"
    )
    format_locator = page.locator(format_label)
    try:
        if format_locator.first.is_visible(timeout=1000):
            if not click_first_visible(format_locator, timeout_ms=5000):
                raise RuntimeError(f"未找到导出格式选项: {download_format}")
            confirm_button = page.locator("a.submit.gd-btn.gd-btn-primary.second-step-el")
            if not click_first_visible(confirm_button, timeout_ms=5000):
                raise RuntimeError("未找到导出确认按钮")
    except Exception:
        pass

    privacy_confirm = page.locator("#export_privacy_confirm_modal a.confirm")
    try:
        if privacy_confirm.first.is_visible(timeout=3000) and not click_first_visible(privacy_confirm, timeout_ms=5000):
            raise RuntimeError("未找到继续导出按钮")
    except Exception:
        pass


def download_export_file(page: Page, run_dir: Path, download_format: str) -> Path:
    extension = ".xlsx" if download_format == "xlsx" else ".csv"
    page.wait_for_function(
        """
        () => {
          const isVisible = (el) => {
            const style = window.getComputedStyle(el);
            const rect = el.getBoundingClientRect();
            return style.visibility !== 'hidden' && style.display !== 'none' && rect.width > 0 && rect.height > 0;
          };
          return [...document.querySelectorAll(".grid-toolbar__export-excel a[data-role='download']")].some((el) => isVisible(el));
        }
        """,
        timeout=240000,
    )
    download_button = page.locator(".grid-toolbar__export-excel a[data-role='download']")
    with page.expect_download(timeout=120000) as download_info:
        if not click_first_visible(download_button, timeout_ms=5000):
            raise RuntimeError("下载链接已生成，但未找到可点击的下载按钮")
    download = download_info.value
    target = run_dir / f"jinshuju_export{extension}"
    target.parent.mkdir(parents=True, exist_ok=True)
    download.save_as(str(target))
    return target


def launch_context_with_fallback(playwright_obj: Any, profile_dir: Path, headless: bool) -> tuple[BrowserContext, Path]:
    launch_kwargs = {
        "headless": headless,
        "accept_downloads": True,
        "viewport": {"width": 1440, "height": 960},
    }
    try:
        context = playwright_obj.chromium.launch_persistent_context(str(profile_dir), **launch_kwargs)
        return context, profile_dir
    except Error:
        fallback_dir = Path(mkdtemp(prefix="jinshuju_profile_", dir=str(profile_dir.parent)))
        context = playwright_obj.chromium.launch_persistent_context(str(fallback_dir), **launch_kwargs)
        return context, fallback_dir


def check_session(ctx: TaskContext, config: AppConfig) -> dict[str, Any]:
    profile_dir = Path(config.jinshuju_profile_dir)
    profile_dir.mkdir(parents=True, exist_ok=True)
    ctx.set_message("打开金数据并检查登录状态")
    with sync_playwright() as playwright_obj:
        context, active_profile_dir = launch_context_with_fallback(playwright_obj, profile_dir, headless=False)
        try:
            page = context.pages[0] if context.pages else context.new_page()
            wait_for_login(page, config.jinshuju_home_url)
            return {
                "logged_in": True,
                "profile_dir": str(active_profile_dir),
                "current_url": page.url,
            }
        finally:
            context.close()


def discover_forms(ctx: TaskContext, config: AppConfig) -> list[dict[str, str]]:
    profile_dir = Path(config.jinshuju_profile_dir)
    profile_dir.mkdir(parents=True, exist_ok=True)
    ctx.set_message("登录并抓取金数据表单列表")
    with sync_playwright() as playwright_obj:
        context, _ = launch_context_with_fallback(playwright_obj, profile_dir, headless=False)
        try:
            page = context.pages[0] if context.pages else context.new_page()
            return discover_forms_from_page(page, config.jinshuju_home_url)
        finally:
            context.close()


def export_form(
    ctx: TaskContext | None,
    config: AppConfig,
    *,
    run_dir: Path,
    form_title: str | None,
    entries_url: str | None,
    download_format: str = "xlsx",
    headless: bool = False,
) -> tuple[Path, list[str]]:
    profile_dir = Path(config.jinshuju_profile_dir)
    profile_dir.mkdir(parents=True, exist_ok=True)
    run_dir.mkdir(parents=True, exist_ok=True)
    if ctx:
        ctx.set_message(f"导出金数据表单：{form_title or entries_url}")
    with sync_playwright() as playwright_obj:
        context, _ = launch_context_with_fallback(playwright_obj, profile_dir, headless=headless)
        page = context.pages[0] if context.pages else context.new_page()
        try:
            open_entries_page(
                page,
                home_url=config.jinshuju_home_url,
                form_title=form_title,
                entries_url=entries_url,
            )
            form_token = current_form_token(page)
            submit_export_job(page, form_token, download_format)
            download_url = wait_for_export_download_url(page, form_token)
            return download_export_url(download_url, run_dir, download_format), []
        except Exception:
            artifacts = save_debug_artifacts(page, run_dir, "jinshuju_debug")
            suffix = f"，调试文件：{', '.join(artifacts)}" if artifacts else ""
            raise RuntimeError(f"金数据导出失败{suffix}")
        finally:
            context.close()


def export_form_snapshot(
    ctx: TaskContext,
    config: AppConfig,
    *,
    form_title: str | None,
    entries_url: str | None,
    download_format: str = "xlsx",
    headless: bool = False,
    run_dir: Path | None = None,
    export_tag: str = "form",
) -> dict[str, Any]:
    if run_dir is None:
        raise RuntimeError("缺少 run_dir")
    target_run_dir = run_dir
    exports_dir = target_run_dir / "exports" / export_tag
    export_file, debug_artifacts = export_form(
        ctx,
        config,
        run_dir=exports_dir,
        form_title=form_title,
        entries_url=entries_url,
        download_format=download_format,
        headless=headless,
    )
    archived_export_file = archive_export_copy(
        export_file,
        export_tag=export_tag,
        form_title=form_title,
    )
    return {
        "run_dir": str(target_run_dir),
        "export_file": str(export_file),
        "archived_export_file": str(archived_export_file),
        "archived_export_dir": str(archived_export_file.parent),
        "form_title": form_title or "",
        "entries_url": entries_url or "",
        "download_format": download_format,
        "export_tag": export_tag,
        "debug_artifacts": debug_artifacts,
    }
