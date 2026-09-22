# -*- coding: utf-8 -*-
"""Man quan ly tien trinh tai game (mo tu nut Y trong cac man store).

Chi doc anh chup tu rh.downloader: worker dang tai o thread khac la nguon duy
nhat cua su that, man nay khong giu trang thai rieng. Hang cho chi song trong
RAM nen tat app la sach.
"""

from .. import state
from ..downloader import (cancel_download, clear_download_queue, clear_failed, enqueue_download,
                          forget_failed, is_paused, list_download_items,
                          pause_active_download, resume_active_download)
from ..i18n import tr
from .base import BaseScreen

# Nhan trang thai lay tu i18n, khong dung ky hieu hay emoji: font tren may khong
# co glyph do nen se hien thanh o vuong.
_STATUS_KEY = {
    "error": "dlq_status_failed",
    "downloading": "dlq_status_active",
    "extracting": "dlq_status_extracting",
    "cancelling": "dlq_status_cancelling",
    "queued": "dlq_status_queued",
    "cancelled": "dl_cancelled_toast",
}

def _status_text(item):
    if item.get("paused"):
        return tr("dlq_status_paused")
    return tr(_STATUS_KEY.get(item.get("status"), "dlq_status_queued"))

# Luoi le dung theo phan con lai cua app: header ket thuc o y=64, footer bat dau
# tu SCREEN_H-56, cac man khac (store, home, settings) deu le 40px. The phien
# dang tai cao theo co chu that (24pt tieu de + 22pt dong trang thai + thanh tien
# do + 22pt dong dung luong) chu khong theo con so uoc luong.
# Mau vien focus dung chung voi cac man khac (queue, library, store).
FOCUS_RGB = (230, 33, 23)
PAD = 40
TOP_Y = 76
FOOTER_H = 56
BOTTOM_GAP = 16
CARD_H = 152
LIST_GAP = 16
ROW_H = 60
ROW_INNER_H = 52
LIST_TOP = TOP_Y + CARD_H + LIST_GAP

class DownloadsScreen(BaseScreen):
    """Danh sach dang tai + hang cho, co tam dung / huy / xoa hang cho."""

    def __init__(self, engine=None):
        super().__init__(engine)
        self.items = []
        self.sel = 0
        self.scroll = 0
        self.confirm_clear = False

    # ------------------------------------------------------------------
    def on_enter(self, params=None):
        self.confirm_clear = False
        self.sel = 0
        self.scroll = 0
        self.refresh()

    def refresh(self):
        """Nap lai anh chup tu downloader va giu con tro trong khoang hop le."""
        self.items = list_download_items()
        if self.sel >= len(self.items):
            self.sel = max(0, len(self.items) - 1)

    def get_header_title(self):
        return "%s (%d)" % (tr("dlq_title"), len(self.items))

    def get_footer_actions(self):
        if self.confirm_clear:
            return [
                ("A", tr("app_confirm_yes"), (255, 75, 75), (255, 255, 255), True),
                ("B", tr("app_confirm_no"), (120, 140, 170), (220, 225, 235), False),
            ]
        actions = []
        if self.items:
            sel = self.items[min(self.sel, len(self.items) - 1)]
            if sel["kind"] == "failed":
                # Muc loi: A tai lai, X bo khoi danh sach.
                actions.append(("A", tr("dlq_footer_retry"), (0, 230, 150), (220, 225, 235), True))
                actions.append(("X", tr("dlq_footer_remove"), (255, 150, 60), (220, 225, 235), True))
            else:
                active = next((it for it in self.items if it["kind"] == "active"), None)
                pause_lbl = tr("dlq_footer_resume") if active and active.get("paused") else tr("dlq_footer_pause")
                actions.append(("A", pause_lbl, (0, 230, 150), (220, 225, 235), True))
                actions.append(("X", tr("dlq_footer_cancel"), (255, 150, 60), (220, 225, 235), True))
        if any(it["kind"] in ("queued", "failed") for it in self.items):
            actions.append(("Y", tr("dlq_footer_clear"), (255, 75, 75), (220, 225, 235), False))
        actions.append(("B", tr("footer_back"), (255, 75, 75), (220, 225, 235), False))
        return actions

    # ------------------------------------------------------------------
    def _toggle_pause(self):
        item = self.items[self.sel] if self.items else None
        if not item or item["kind"] != "active" or item["status"] != "downloading":
            if self.engine:
                self.engine.toast(tr("dlq_only_active"))
            return
        if is_paused():
            resume_active_download()
            msg = tr("dlq_resumed_toast")
        else:
            pause_active_download()
            msg = tr("dlq_paused_toast")
        if self.engine:
            self.engine.toast(msg)
        self.refresh()

    def _retry_selected(self):
        """Tai lai muc vua loi: xep lai vao hang cho va bo khoi danh sach loi."""
        if not self.items:
            return
        item = self.items[self.sel]
        if item["kind"] != "failed":
            return
        forget_failed(item.get("game_info"))
        msg = enqueue_download(item.get("sys_code", ""), item.get("game_info") or {})
        if self.engine:
            self.engine.toast(msg or tr("dlq_retry_toast"))
        self.refresh()

    def _remove_failed(self):
        if not self.items:
            return
        item = self.items[self.sel]
        if item["kind"] != "failed":
            return
        if forget_failed(item.get("game_info")) and self.engine:
            self.engine.toast(tr("dlq_failed_removed_toast"))
        self.refresh()

    def _cancel_selected(self):
        if not self.items:
            return
        item = self.items[self.sel]
        was_active = item["kind"] == "active"
        if cancel_download(item.get("game_info")):
            if self.engine:
                self.engine.toast(tr("dl_cancelled_toast") if was_active
                                  else tr("dlq_removed_toast"))
        self.refresh()

    def _clear_queue(self):
        removed = clear_download_queue() + clear_failed()
        if removed and self.engine:
            self.engine.toast(tr("dlq_cleared_toast").format(n=removed))
        self.confirm_clear = False
        self.refresh()

    def _row_index(self, idx):
        """Chi so dong trong danh sach cho (the phien dang tai khong phai mot dong)."""
        return idx - 1 if self.items and self.items[0]["kind"] == "active" else idx

    def _visible_rows(self):
        """So dong cho hien duoc: tru le tren, the phien dang tai, le duoi, footer."""
        return max(1, (state.SCREEN_H - TOP_Y - CARD_H - LIST_GAP - BOTTOM_GAP - FOOTER_H) // ROW_H)

    # ------------------------------------------------------------------
    def handle_input(self, inputs):
        if self.confirm_clear:
            if inputs.get("btn_a"):
                self._clear_queue()
                return True
            if inputs.get("btn_b"):
                self.confirm_clear = False
                return True
            return True

        if inputs.get("btn_b"):
            self.engine.pop_screen()
            return True

        if inputs.get("btn_y"):
            if any(it["kind"] == "queued" for it in self.items):
                self.confirm_clear = True
            elif self.engine:
                self.engine.toast(tr("dlq_empty"))
            return True

        if inputs.get("btn_a"):
            if self.items and self.items[self.sel]["kind"] == "failed":
                self._retry_selected()
            else:
                self._toggle_pause()
            return True

        if inputs.get("btn_x"):
            if self.items and self.items[self.sel]["kind"] == "failed":
                self._remove_failed()
            else:
                self._cancel_selected()
            return True

        total = len(self.items)
        if total:
            if inputs.get("btn_up"):
                self.sel = (self.sel - 1) % total
            elif inputs.get("btn_down"):
                self.sel = (self.sel + 1) % total
            else:
                return False
            visible = self._visible_rows()
            row = self._row_index(self.sel)
            if row < 0:
                return True
            if row < self.scroll:
                self.scroll = row
            elif row >= self.scroll + visible:
                self.scroll = row - visible + 1
            return True
        return False

    # ------------------------------------------------------------------
    def render(self, engine):
        # Man nay doi theo tien do tai, nen doc lai anh chup moi khung hinh: chi
        # la mot list nho, khong cham dia hay mang.
        self.refresh()

        width = state.SCREEN_W
        if not self.items:
            engine.draw_text(tr("dlq_empty"), engine.font_item, width // 2,
                             state.SCREEN_H // 2, 140, 160, 190, center_x=True, center_y=True)
            if self.confirm_clear:
                self._render_confirm(engine)
            return

        for idx in range(len(self.items)):
            item = self.items[idx]
            if idx == 0 and item["kind"] == "active":
                self._render_active(engine, item, PAD, TOP_Y, width - PAD * 2, idx == self.sel)
                continue
            row_i = self._row_index(idx)
            if row_i < self.scroll or row_i >= self.scroll + self._visible_rows():
                continue
            row_y = LIST_TOP + (row_i - self.scroll) * ROW_H
            if item["kind"] == "failed":
                self._render_failed(engine, item, PAD, row_y, width - PAD * 2, idx == self.sel)
            else:
                self._render_queued(engine, item, PAD, row_y, width - PAD * 2, idx == self.sel)

        if self.confirm_clear:
            self._render_confirm(engine)

    def _render_active(self, engine, item, x, y, w, selected):
        engine.fill_rect(x, y, w, CARD_H, 19, 26, 42, 255)
        if selected:
            # Phien dang tai cung la mot muc trong danh sach: khong co vien nay thi
            # nguoi dung khong biet A dang tac dong len muc nao.
            engine.draw_rect(x, y, w, CARD_H, FOCUS_RGB[0], FOCUS_RGB[1], FOCUS_RGB[2], 255,
                             thickness=3)
            engine.fill_rect(x + 4, y + 4, w - 8, 4, FOCUS_RGB[0], FOCUS_RGB[1], FOCUS_RGB[2], 255)
        else:
            engine.draw_rect(x, y, w, CARD_H, 40, 54, 85, 255, thickness=1)
        # The "dang huy" o goc phai: trang thai nay phai nhin ra ngay, khong lan vao
        # dong tien do nhu mot phan cua so lieu.
        chip_w = 0
        if item.get("status") == "cancelling":
            label = tr("dlq_status_cancelling")
            chip_w = engine.measure_text(label, engine.font_footer) + 24
            chip_x = x + w - 18 - chip_w
            engine.fill_rect(chip_x, y + 12, chip_w, 30, 130, 32, 32, 255)
            engine.draw_text(label, engine.font_footer, chip_x + chip_w // 2, y + 27,
                             255, 235, 235, center_x=True, center_y=True, max_w=chip_w - 12)

        title_w = w - 36 - (chip_w + 12 if chip_w else 0)
        engine.draw_text(item.get("title", ""), engine.font_grid_title, x + 18, y + 14,
                         225, 235, 250, max_w=title_w)

        pct = max(0, min(100, int(item.get("progress_pct") or 0)))
        status_txt = "%s  %d%%  %s" % (_status_text(item), pct, item.get("speed_str", ""))
        if item.get("status") == "cancelling":
            status_txt = "%d%%  %s" % (pct, item.get("speed_str", ""))
        if item.get("status") == "cancelling":
            col = (255, 95, 95)
        elif item.get("paused"):
            col = (255, 200, 0)
        else:
            col = (0, 246, 246)
        engine.draw_text(status_txt, engine.font_footer, x + 18, y + 50, col[0], col[1], col[2],
                         max_w=w - 36)

        bar_x = x + 18
        bar_y = y + 86
        bar_w = w - 36
        engine.fill_rect(bar_x, bar_y, bar_w, 18, 28, 44, 75, 255)
        if pct > 0:
            engine.fill_rect(bar_x, bar_y, max(4, bar_w * pct // 100), 18, 0, 230, 150, 255)
        engine.draw_rect(bar_x, bar_y, bar_w, 18, 60, 80, 120, 255, thickness=1)

        # Worker da ghi san "102.0 / 256.0 MB" trong downloaded_str; noi them kich
        # thuoc lan nua thi dong nay thanh "102.0 / 256.0 MB / 256.0 MB".
        done = item.get("downloaded_str") or ""
        size = item.get("size_str") or ""
        if "/" in done:
            meta = done
        elif done and size:
            meta = "%s / %s" % (done, size)
        else:
            meta = done or size
        engine.draw_text(meta, engine.font_footer, bar_x, bar_y + 28, 180, 195, 220,
                         max_w=bar_w)

    def _render_queued(self, engine, item, x, y, w, selected):
        if selected:
            engine.fill_rect(x, y, w, ROW_INNER_H, 28, 44, 75, 255)
            engine.draw_rect(x, y, w, ROW_INNER_H, 230, 33, 23, 255, thickness=3)
        else:
            engine.fill_rect(x, y, w, ROW_INNER_H, 19, 26, 42, 255)
            engine.draw_rect(x, y, w, ROW_INNER_H, 40, 54, 85, 255, thickness=1)
        engine.draw_text("#%d" % item.get("pos", 0), engine.font_badge, x + 18, y + 14,
                         0, 220, 245)
        engine.draw_text(item.get("title", ""), engine.font_grid_title, x + 72, y + 16,
                         225, 235, 250, max_w=w - 72 - 260)
        # Mot dong ben phai: hai dong (dung luong + trang thai) cao hon chieu cao
        # dong nen chu truot ra ngoai o.
        right_txt = tr("dlq_status_queued")
        if item.get("size_str"):
            right_txt = "%s  %s" % (right_txt, item.get("size_str"))
        engine.draw_text(right_txt, engine.font_footer, x + w - 18, y + 16,
                         130, 150, 180, right_align=True, max_w=250)

    def _render_failed(self, engine, item, x, y, w, selected):
        """Dong loi: do, giu lai trong danh sach va noi ro ly do."""
        if selected:
            engine.fill_rect(x, y, w, ROW_INNER_H, 52, 20, 24, 255)
            engine.draw_rect(x, y, w, ROW_INNER_H, FOCUS_RGB[0], FOCUS_RGB[1], FOCUS_RGB[2], 255,
                             thickness=3)
        else:
            engine.fill_rect(x, y, w, ROW_INNER_H, 38, 18, 22, 255)
            engine.draw_rect(x, y, w, ROW_INNER_H, 120, 45, 50, 255, thickness=1)
        engine.draw_text(tr("dlq_status_failed"), engine.font_footer, x + 18, y + 16,
                         255, 120, 120, max_w=140)
        engine.draw_text(item.get("title", ""), engine.font_grid_title, x + 140, y + 16,
                         255, 205, 205, max_w=w - 140 - 260)
        reason = (item.get("msg") or "").replace("\n", " ").strip()
        engine.draw_text(reason, engine.font_footer, x + w - 18, y + 16, 220, 150, 150,
                         right_align=True, max_w=250)

    def _render_confirm(self, engine):
        width = state.SCREEN_W
        height = state.SCREEN_H
        queued = sum(1 for it in self.items if it["kind"] == "queued")
        mw = min(width - 160, 640)
        mh = 290
        mx = (width - mw) // 2
        my = (height - mh) // 2

        engine.fill_rect(0, 0, width, height, 8, 11, 20, 200)
        engine.fill_rect(mx, my, mw, mh, 22, 30, 50, 255)
        engine.draw_rect(mx, my, mw, mh, 255, 90, 90, 255, thickness=2)
        engine.draw_text(tr("dlq_confirm_clear_title"), engine.font_item, mx + mw // 2, my + 36,
                         255, 95, 95, center_x=True, center_y=True, max_w=mw - 60)
        lines = engine.wrap_text_to_width(tr("dlq_confirm_clear_msg").format(n=queued),
                                          engine.font_badge, mw - 80, max_lines=2)
        for i, line in enumerate(lines):
            engine.draw_text(line, engine.font_badge, mx + mw // 2, my + 100 + i * 34,
                             210, 220, 235, center_x=True, center_y=True, max_w=mw - 60)

        btn_w = (mw - 60) // 2
        btn_h = 54
        btn_y = my + mh - btn_h - 24
        engine.fill_rect(mx + 20, btn_y, btn_w, btn_h, 180, 45, 45, 255)
        engine.draw_rect(mx + 20, btn_y, btn_w, btn_h, 255, 90, 90, 255, thickness=1)
        engine.draw_text("[A] %s" % tr("app_confirm_yes"), engine.font_badge,
                         mx + 20 + btn_w // 2, btn_y + btn_h // 2, 255, 255, 255,
                         center_x=True, center_y=True, max_w=btn_w - 12)
        engine.fill_rect(mx + 40 + btn_w, btn_y, btn_w, btn_h, 35, 46, 68, 255)
        engine.draw_rect(mx + 40 + btn_w, btn_y, btn_w, btn_h, 75, 95, 130, 255, thickness=1)
        engine.draw_text("[B] %s" % tr("app_confirm_no"), engine.font_badge,
                         mx + 40 + btn_w + btn_w // 2, btn_y + btn_h // 2, 210, 220, 235,
                         center_x=True, center_y=True, max_w=btn_w - 12)
