# -*- coding: utf-8 -*-
"""Modal theo doi tien do tu dong cai dat he may gia lap & PortMaster lan dau mo app."""

import math
import threading
import time

from .. import state
from ..i18n import tr
from .base import BaseModal


class InitialSetupModal(BaseModal):
    """Modal overlay giam sat tien trinh cai dat tu dong toan bo gia lap & PortMaster."""

    def __init__(self, engine=None):
        super().__init__(engine)
        self.items = []
        self.total_items = 0
        self.current_idx = 0
        self.current_item = None
        self.status_text = ""
        self.running = False
        self.done = False
        self.cancel_requested = False
        self.cancelled = False
        self.completed_history = []  # Danh sach cac muc da hoan thanh [(name, success)]
        self.success_count = 0
        self.error_count = 0
        self.worker_thread = None

    def open(self, data=None):
        super().open(data)
        data = data or {}
        self.items = data.get("items") or []
        self.total_items = len(self.items)
        self.current_idx = 0
        self.current_item = None
        self.status_text = tr("init_setup_subtitle")
        self.running = False
        self.done = False
        self.cancel_requested = False
        self.cancelled = False
        self.completed_history = []
        self.success_count = 0
        self.error_count = 0

        if self.items:
            self._start_worker()
        else:
            self.done = True
            state.initial_setup_done = True
            state.save_settings()

    def _start_worker(self):
        self.running = True
        self.worker_thread = threading.Thread(target=self._run_install_tasks, daemon=True)
        self.worker_thread.start()

    def _run_install_tasks(self):
        from ..emulator_store import install_emu
        from ..app_store import install_app

        for idx, item in enumerate(self.items):
            if self.cancel_requested:
                self.cancelled = True
                break

            self.current_idx = idx + 1
            self.current_item = item
            item_type = item.get("type", "emu")
            item_id = item.get("id", "")
            item_name = item.get("name", item_id)

            self.status_text = tr("init_setup_status_dl")

            success = False
            try:
                if item_type == "app":
                    def on_status(st):
                        if st == "downloading":
                            self.status_text = tr("init_setup_status_dl")
                        elif st == "installing":
                            self.status_text = tr("init_setup_status_ext")

                    ok, _ = install_app(item_id, on_status=on_status)
                    success = bool(ok)
                else:
                    self.status_text = tr("init_setup_status_ext")
                    res = install_emu(item_id)
                    success = bool(isinstance(res, dict) and res.get("success"))
            except Exception as e:
                print(f"[InitialSetup] Loi khi cai dat {item_id}: {e}")
                success = False

            if success:
                self.success_count += 1
                self.completed_history.append((item_name, True))
            else:
                self.error_count += 1
                self.completed_history.append((item_name, False))

            # Giu toi da 4 muc lich su gan nhat de render gon gang
            if len(self.completed_history) > 4:
                self.completed_history.pop(0)

            time.sleep(0.1)

        self.running = False
        if not self.cancelled:
            self.done = True
            self.status_text = tr("init_setup_done_msg")
            state.initial_setup_done = True
            state.save_settings()
            if self.engine:
                self.engine.toast(tr("init_setup_done_msg"), text_color=(0, 255, 160))
        else:
            self.status_text = tr("init_setup_cancelled")

    def handle_input(self, inputs):
        if not self.active:
            return False

        btn_a = inputs.get("btn_a")
        btn_b = inputs.get("btn_b")

        if self.running:
            if btn_b and not self.cancel_requested:
                self.cancel_requested = True
                self.status_text = tr("upd_cancelling")
                return True
            return True  # Nuot cac nut khac khi dang chay

        if self.done or self.cancelled:
            if btn_a or btn_b:
                self._dismiss()
                return True

        return True

    def _dismiss(self):
        if self.engine:
            self.engine.close_modal()
        else:
            self.close()

    def render(self, engine):
        if not self.active:
            return

        # Nop phu toi mo toan man hinh
        engine.fill_rect(0, 0, state.SCREEN_W, state.SCREEN_H, 0, 0, 0, 220)

        # Kich thuoc hop thoai modal
        mw = min(700, int(state.SCREEN_W * 0.88))
        mh = min(380, int(state.SCREEN_H * 0.82))
        mx = (state.SCREEN_W - mw) // 2
        my = (state.SCREEN_H - mh) // 2

        # Khung vien va nen
        engine.fill_rect(mx, my, mw, mh, 16, 22, 36, 255)
        border_color = (0, 230, 150) if self.done else (0, 230, 255)
        engine.draw_rect(mx, my, mw, mh, border_color[0], border_color[1], border_color[2], 255, thickness=2)

        # Thanh tieu de
        engine.fill_rect(mx + 2, my + 2, mw - 4, 46, 24, 34, 52, 255)
        header_title = tr("init_setup_done_title") if self.done else tr("init_setup_title")
        engine.draw_text(
            header_title,
            engine.font_item,
            mx + mw // 2,
            my + 24,
            border_color[0],
            border_color[1],
            border_color[2],
            center_x=True,
            center_y=True
        )

        # Thong tin muc dang cai dat
        if self.running and self.current_item:
            c_name = self.current_item.get("name", self.current_item.get("id", ""))
            c_type = self.current_item.get("type", "emu")
            badge = f"[{self.current_idx}/{self.total_items}]"
            item_display = f"{badge}  {c_name}"
            engine.draw_text(
                item_display,
                engine.font_item,
                mx + mw // 2,
                my + 78,
                255, 255, 255,
                center_x=True,
                center_y=True,
                max_w=mw - 60
            )
        elif self.done:
            summary = f"{tr('init_setup_status_ok')}: {self.success_count}/{self.total_items}"
            engine.draw_text(
                summary,
                engine.font_item,
                mx + mw // 2,
                my + 78,
                0, 255, 160,
                center_x=True,
                center_y=True
            )
        elif self.cancelled:
            engine.draw_text(
                tr("init_setup_cancelled"),
                engine.font_item,
                mx + mw // 2,
                my + 78,
                255, 180, 80,
                center_x=True,
                center_y=True
            )

        # Dong trang thai
        engine.draw_text(
            self.status_text,
            engine.font_badge,
            mx + mw // 2,
            my + 112,
            0, 220, 255,
            center_x=True,
            center_y=True,
            max_w=mw - 60
        )

        # Thanh tien do (Progress bar)
        bar_w = mw - 80
        bar_h = 22
        bx = mx + 40
        by = my + 140
        engine.fill_rect(bx, by, bar_w, bar_h, 10, 14, 24, 255)
        engine.draw_rect(bx, by, bar_w, bar_h, 45, 65, 95, 255, thickness=1)

        pct = 0
        if self.total_items > 0:
            pct = max(0, min(100, int((self.current_idx / self.total_items) * 100)))
        if self.done:
            pct = 100

        fill_w = int((bar_w - 4) * (pct / 100.0))
        if fill_w > 0:
            fill_r, fill_g, fill_b = (0, 230, 150) if self.done else (0, 210, 255)
            engine.fill_rect(bx + 2, by + 2, fill_w, bar_h - 4, fill_r, fill_g, fill_b, 255)

        pct_text = f"{pct}%"
        engine.draw_text(
            pct_text,
            engine.font_badge,
            bx + bar_w - 10,
            by + bar_h // 2,
            240, 245, 255,
            right_align=True,
            center_y=True
        )

        # Danh sach lich su cac muc vua hoan thanh
        hist_y = my + 180
        if self.completed_history:
            for h_name, h_ok in self.completed_history[-3:]:
                mark = "[OK]" if h_ok else "[ERR]"
                color = (0, 230, 150) if h_ok else (255, 100, 100)
                engine.draw_text(
                    f"{mark} {h_name}",
                    engine.font_badge,
                    bx + 6,
                    hist_y,
                    color[0], color[1], color[2]
                )
                hist_y += 24

        # Loi nhac canh bao nguon dien & mang
        if self.running:
            engine.draw_text(
                tr("init_setup_notice"),
                engine.font_badge,
                mx + mw // 2,
                my + mh - 58,
                140, 160, 195,
                center_x=True,
                center_y=True,
                max_w=mw - 60
            )

        # Thanh nut bam duoi cung
        btn_w = 170
        btn_h = 36
        btn_y = my + mh - 44
        btn_x = mx + (mw - btn_w) // 2

        if self.running:
            engine.fill_rect(btn_x, btn_y, btn_w, btn_h, 35, 45, 65, 255)
            engine.draw_rect(btn_x, btn_y, btn_w, btn_h, 75, 95, 130, 255, thickness=1)
            engine.draw_text(
                f"[B] {tr('init_setup_cancel_hint')}",
                engine.font_badge,
                btn_x + btn_w // 2,
                btn_y + btn_h // 2,
                210, 220, 235,
                center_x=True,
                center_y=True
            )
        else:
            engine.fill_rect(btn_x, btn_y, btn_w, btn_h, 0, 150, 100, 255)
            engine.draw_rect(btn_x, btn_y, btn_w, btn_h, 0, 230, 150, 255, thickness=1)
            btn_txt = f"[A] {tr('init_setup_done_btn')}"
            engine.draw_text(
                btn_txt,
                engine.font_badge,
                btn_x + btn_w // 2,
                btn_y + btn_h // 2,
                255, 255, 255,
                center_x=True,
                center_y=True
            )
