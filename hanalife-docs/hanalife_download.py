# -*- coding: utf-8 -*-
"""
하나생명 공시실 전체상품 목록(판매상품/판매중지상품) 기초서류 일괄 다운로드

- 대상 페이지
    판매상품    : https://www.hanalife.co.kr/anm/product/allProduct.do?status=on
    판매중지상품 : https://www.hanalife.co.kr/anm/product/allProduct.do?status=off
- 서류: 상품요약서 / 사업방법서 / 보험약관 (판매중지상품은 상품요약서 열이 있을 때만)
- 저장 구조
    <저장폴더>/<판매중|판매중지>/<판매시작연도>/<판매시작일 YYYY.MM.DD>/<상품명>/[서류종류] 원본파일명
- 이미 받은 파일은 건너뜀(재실행 시 이어받기), 결과는 download_log.csv 에 기록

실행:
    pip install playwright
    playwright install chromium
    python hanalife_download.py                  # 판매+판매중지 전체
    python hanalife_download.py --status on      # 판매상품만
    python hanalife_download.py --limit 3        # 테스트(페이지당 3개 상품)
    python hanalife_download.py --headed         # 브라우저 창 보면서 실행
"""
import argparse
import csv
import re
import shutil
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

from playwright.sync_api import TimeoutError as PWTimeout
from playwright.sync_api import sync_playwright

BASE_URL = "https://www.hanalife.co.kr/anm/product/allProduct.do?status={status}"
DEFAULT_OUT = str(Path(__file__).resolve().parent.parent / "product-documents")
STATUS_NAME = {"on": "판매상품", "off": "판매중지상품"}
STATUS_FOLDER = {"on": "판매중", "off": "판매중지"}
DOC_COLUMNS = ["상품요약서", "사업방법서", "보험약관"]

# 테이블의 rowspan/colspan 을 풀어 행 단위 데이터로 만들고,
# 다운로드 버튼마다 data-ccdl 속성을 붙여 Playwright 로 클릭할 수 있게 한다.
PARSE_TABLE_JS = r"""
() => {
  const tables = [...document.querySelectorAll('table')].filter(t => {
    const h = t.innerText;
    return h.includes('상품명') && h.includes('판매기간');
  });
  if (!tables.length) return null;
  const table = tables[0];

  let headers = [...table.querySelectorAll('thead th')].map(th => th.innerText.trim());
  let bodyRows = [...table.querySelectorAll('tbody tr')];
  if (!headers.length) {
    const all = [...table.querySelectorAll('tr')];
    headers = [...all[0].children].map(c => c.innerText.trim());
    bodyRows = all.slice(1);
  }

  const grid = [];
  bodyRows.forEach((tr, r) => {
    grid[r] = grid[r] || [];
    let c = 0;
    [...tr.children].forEach(td => {
      while (grid[r][c]) c++;
      const rs = td.rowSpan || 1, cs = td.colSpan || 1;
      let dl = null;
      const link = td.querySelector('a, button, input[type=button]');
      if (link && /다운로드|down/i.test(link.innerText + ' ' + (link.value || '') + ' ' + (link.getAttribute('onclick') || '') + ' ' + (link.getAttribute('href') || ''))) {
        dl = 'cc-' + r + '-' + c;
        link.setAttribute('data-ccdl', dl);
      }
      for (let dr = 0; dr < rs; dr++) for (let dc = 0; dc < cs; dc++) {
        grid[r + dr] = grid[r + dr] || [];
        grid[r + dr][c + dc] = {text: td.innerText.trim(), dl: (dr === 0 && dc === 0) ? dl : null};
      }
      c += cs;
    });
  });

  return grid.map(row => {
    const o = {};
    headers.forEach((h, i) => { o[h] = row[i] || {text: '', dl: null}; });
    return o;
  });
}
"""

INVALID = re.compile(r'[\\/:*?"<>|\r\n\t]+')


def safe(name, maxlen=80):
    name = INVALID.sub("_", name).strip().rstrip(".")
    return (name[:maxlen].rstrip() or "_")


def parse_period(text):
    dates = re.findall(r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})", text)
    if not dates:
        return "날짜미상", "날짜미상", ""
    y, m, d = dates[0]
    start = f"{y}.{int(m):02d}.{int(d):02d}"
    end = ""
    if len(dates) > 1:
        y2, m2, d2 = dates[1]
        end = f"{y2}.{int(m2):02d}.{int(d2):02d}"
    return y, start, end


def find_col(row, keyword):
    for k in row:
        if keyword in k.replace(" ", ""):
            return k
    return None


def unique_path(path):
    if not path.exists():
        return path
    i = 2
    while True:
        p = path.with_name(f"{path.stem}({i}){path.suffix}")
        if not p.exists():
            return p
        i += 1


class Downloader:
    def __init__(self, page, ctx, log):
        self.page, self.ctx, self.log = page, ctx, log
        self.downloads, self.dialogs = [], []
        page.on("download", self._on_download)
        page.on("dialog", self._on_dialog)
        ctx.on("page", self._on_page)

    def _on_download(self, d):
        self.downloads.append(d)

    def _on_dialog(self, d):
        self.dialogs.append(d.message)
        d.accept()

    def _on_page(self, p):
        p.on("download", self._on_download)
        p.on("dialog", self._on_dialog)

    def fetch(self, locator, dest_dir, doc, timeout=30):
        """버튼 클릭 → (다운로드 이벤트 | 팝업 URL | 알림창) 중 하나를 처리. 저장 경로 또는 사유 반환."""
        n_dl, n_dialog = len(self.downloads), len(self.dialogs)
        pages_before = set(self.ctx.pages)
        locator.scroll_into_view_if_needed()
        locator.click()

        popup, deadline = None, time.time() + timeout
        while time.time() < deadline:
            if len(self.downloads) > n_dl:
                dl = self.downloads[-1]
                dest_dir.mkdir(parents=True, exist_ok=True)
                target = unique_path(dest_dir / safe(f"[{doc}] {dl.suggested_filename}", 150))
                dl.save_as(str(target))
                self._close_popups(pages_before)
                return target, ""
            if len(self.dialogs) > n_dialog:
                self._close_popups(pages_before)
                return None, "알림: " + self.dialogs[-1]
            new = [p for p in self.ctx.pages if p not in pages_before]
            if new:
                popup = new[0]
                url = popup.url
                if url and url != "about:blank" and time.time() > deadline - timeout + 3:
                    break  # 3초 기다려도 다운로드 이벤트가 없으면 팝업 URL 직접 수신
            self.page.wait_for_timeout(300)

        if popup is not None and popup.url not in ("", "about:blank"):
            resp = self.ctx.request.get(popup.url, timeout=60000)
            if resp.ok:
                cd = resp.headers.get("content-disposition", "")
                m = re.search(r"filename\*?=(?:UTF-8'')?\"?([^\";]+)", cd)
                fname = m.group(1) if m else popup.url.split("/")[-1].split("?")[0] or "file.pdf"
                if "." not in fname:
                    fname += ".pdf"
                dest_dir.mkdir(parents=True, exist_ok=True)
                target = unique_path(dest_dir / safe(f"[{doc}] {fname}", 150))
                target.write_bytes(resp.body())
                self._close_popups(pages_before)
                return target, ""
        self._close_popups(pages_before)
        return None, "다운로드 응답 없음(시간초과)"

    def _close_popups(self, pages_before):
        for p in self.ctx.pages:
            if p not in pages_before and p is not self.page:
                try:
                    p.close()
                except Exception:
                    pass


def go_next_page(page, current):
    """페이지네이션이 있을 경우 다음 페이지로 이동. 없으면 False."""
    nxt = str(current + 1)
    cand = page.locator(
        "[class*=pag] a, [class*=paging] a, [id*=pag] a"
    ).filter(has_text=re.compile(rf"^\s*{nxt}\s*$"))
    if cand.count() == 0:
        cand = page.locator("[class*=pag] a, [class*=paging] a").filter(
            has_text=re.compile(r"다음|next|>", re.I))
        if cand.count() == 0:
            return False
    before = page.locator("table").first.inner_text()
    cand.first.click()
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(800)
    return page.locator("table").first.inner_text() != before


def launch_browser(pw, args):
    """Playwright 전용 브라우저 → PC에 설치된 크롬 → 엣지 순서로 실행을 시도."""
    headless = not args.headed
    if args.chrome:
        return pw.chromium.launch(headless=headless, executable_path=args.chrome)
    errors = []
    for label, opts in [("Playwright 브라우저", {}), ("설치된 크롬", {"channel": "chrome"}),
                        ("설치된 엣지", {"channel": "msedge"})]:
        try:
            browser = pw.chromium.launch(headless=headless, **opts)
            print(f"브라우저: {label}")
            return browser
        except Exception as e:  # noqa: BLE001
            errors.append(f"{label}: {str(e).splitlines()[0]}")
    raise SystemExit("브라우저를 실행하지 못했습니다.\n  " + "\n  ".join(errors)
                     + "\n--chrome \"크롬 또는 엣지 exe 경로\" 옵션으로 직접 지정해 보세요.")


def done_keys(log_path):
    """이미 받은 서류: (상품명, 판매시작일, 서류) → 저장 경로.
    판매상태·판매기간 글자는 키에 넣지 않음 — 판매중이던 상품이 판매중지로 바뀌면 판매기간에 종료일이 붙고
    목록도 바뀌지만, 같은 서류이므로 다시 받지 않고 폴더만 옮기기 위함."""
    keys = {}
    if log_path.exists():
        with open(log_path, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                if r["결과"] in ("성공", "이동") and r["저장경로"] and Path(r["저장경로"]).exists():
                    keys[(r["상품명"], parse_period(r["판매기간"])[1], r["서류"])] = Path(r["저장경로"])
    return keys


def rel(path, base):
    try:
        return path.relative_to(base)
    except ValueError:
        return path


def move_doc(src, dest_dir, stop_at):
    """받아 둔 서류를 새 폴더로 옮기고, 비게 된 예전 폴더(상품명·판매일자·연도)는 지움."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    target = unique_path(dest_dir / src.name)
    shutil.move(str(src), str(target))
    d = src.parent
    while d != stop_at and stop_at in d.parents:
        try:
            d.rmdir()  # 비어 있을 때만 지워짐
        except OSError:
            break
        d = d.parent
    return target


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=DEFAULT_OUT, help="저장 폴더 (기본: 통합 폴더의 product-documents). 기존 다운로드를 이어받으려면 이전 폴더를 지정하세요.")
    ap.add_argument("--status", choices=["on", "off", "all"], default="all")
    ap.add_argument("--limit", type=int, default=0, help="페이지당 처리할 상품 행 수(테스트용)")
    ap.add_argument("--headed", action="store_true", help="브라우저 창 표시")
    ap.add_argument("--chrome", default=None, help="크롬 실행파일 경로(선택). 예: C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe")
    ap.add_argument("--base-url", default=BASE_URL, help=argparse.SUPPRESS)  # 테스트용
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    log_path = out / "download_log.csv"
    skip = done_keys(log_path)
    new_log = not log_path.exists()
    logf = open(log_path, "a", newline="", encoding="utf-8-sig")
    log = csv.writer(logf)
    if new_log:
        log.writerow(["시각", "판매상태", "대상", "분류", "상품명", "판매기간", "서류", "결과", "저장경로", "비고"])

    statuses = ["on", "off"] if args.status == "all" else [args.status]
    stats = {"성공": 0, "건너뜀": 0, "이동": 0, "실패": 0, "서류없음": 0}

    with sync_playwright() as pw:
        browser = launch_browser(pw, args)
        ctx = browser.new_context(accept_downloads=True, locale="ko-KR")
        page = ctx.new_page()
        dlr = Downloader(page, ctx, log)

        for status in statuses:
            sname = STATUS_NAME[status]
            print(f"\n===== {sname} =====")
            page.goto(args.base_url.format(status=status), wait_until="networkidle")
            page_no = 1
            while True:
                rows = page.evaluate(PARSE_TABLE_JS)
                if not rows:
                    print("  상품 표를 찾지 못했습니다. 사이트 구조가 바뀌었는지 확인하세요.")
                    break
                print(f"  [{page_no}페이지] {len(rows)}행")
                if args.limit:
                    rows = rows[: args.limit]

                for row in rows:
                    get = lambda kw: row[find_col(row, kw)]["text"] if find_col(row, kw) else ""
                    target, category = get("대상"), get("분류")
                    name, period = get("상품명"), get("판매기간")
                    if not name:
                        continue
                    year, start, _ = parse_period(period)
                    dest = out / STATUS_FOLDER[status] / year / start / safe(name)

                    for doc in DOC_COLUMNS:
                        key = (name, start, doc)
                        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        if key in skip:
                            old = skip[key]
                            if old.parent == dest:  # 이미 받음
                                stats["건너뜀"] += 1
                                continue
                            # 판매중 → 판매중지로 바뀌었거나 예전 폴더 구조로 받은 서류: 다시 받지 않고 옮기기만 함
                            # (판매중지 목록에 상품요약서 열이 없어도 받아 둔 상품요약서는 같이 옮김)
                            path = move_doc(old, dest, out)
                            skip[key] = path
                            stats["이동"] += 1
                            print(f"    MV  {start} {name} [{doc}] {rel(old.parent, out)} -> {rel(dest, out)}")
                            log.writerow([now, sname, target, category, name, period, doc, "이동", str(path), f"이전 위치: {old}"])
                            logf.flush()
                            continue
                        col = find_col(row, "약관" if doc == "보험약관" else doc)
                        if col is None:
                            continue  # 판매중지상품은 상품요약서 열이 없음
                        dl_id = row[col]["dl"]
                        if not dl_id:
                            stats["서류없음"] += 1
                            log.writerow([now, sname, target, category, name, period, doc, "서류없음", "", ""])
                            continue
                        try:
                            path, note = dlr.fetch(page.locator(f"[data-ccdl='{dl_id}']"), dest, doc)
                        except Exception as e:  # noqa: BLE001
                            path, note = None, f"오류: {e}"
                        if path:
                            skip[key] = path
                            stats["성공"] += 1
                            print(f"    OK  {start} {name} [{doc}] -> {path.name}")
                            log.writerow([now, sname, target, category, name, period, doc, "성공", str(path), note])
                        else:
                            stats["실패"] += 1
                            print(f"    NG  {start} {name} [{doc}] ({note})")
                            log.writerow([now, sname, target, category, name, period, doc, "실패", "", note])
                        logf.flush()
                        page.wait_for_timeout(300)  # 서버 부하 방지

                if args.limit or not go_next_page(page, page_no):
                    break
                page_no += 1

        browser.close()
    logf.close()
    print(f"\n완료: 성공 {stats['성공']} / 건너뜀 {stats['건너뜀']} / 이동 {stats['이동']} / 실패 {stats['실패']} / 서류없음 {stats['서류없음']}")
    print(f"저장 위치: {out}\n로그: {log_path}")


if __name__ == "__main__":
    main()
