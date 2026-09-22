# -*- coding: utf-8 -*-
"""Full-screen App Store Screen for TrimUI RetroHub."""

import os
import math
import time
import threading

from .. import state
from ..paths import APP_DIR, SDCARD_PATH
from ..i18n import tr
from ..app_store import (
    get_apps_status,
    install_app,
    uninstall_app,
)
from .base import BaseScreen


class AppStoreScreen(BaseScreen):
    """Split View App Store Screen for managing utility apps."""

    ITEMS_PER_PAGE = 6

    def __init__(self, engine=None):
        super().__init__(engine)
        self.raw_apps = []
        self.filtered_items = []
        self.selected_idx = 0
        self.scroll_top = 0
        self.filter_mode = "all"  # "all", "installed", "missing"
        self.installing_app = False
        self.install_msg = ""
        self.install_progress = 0
        self.confirm_uninstall_target = None
        self.install_target_item = None
        self.install_action_type = "install"

    def on_enter(self, params=None):
        self.refresh_catalog()

    def refresh_catalog(self, force_reload=False):
        """Reloads app catalog and real-time status on SD card."""
        try:
            self.raw_apps = get_apps_status() or []
        except Exception as e:
            print(f"[AppStoreScreen] Error loading apps: {e}")
            self.raw_apps = []
        self.apply_filter()

    def apply_filter(self):
        """Applies filter mode to the app list."""
        self.filtered_items = []

        for item in self.raw_apps:
            is_inst = item.get("installed", False)
            if self.filter_mode == "installed" and not is_inst:
                continue
            if self.filter_mode == "missing" and is_inst:
                continue

            entry = dict(item)
            self.filtered_items.append(entry)

        if self.selected_idx >= len(self.filtered_items):
            self.selected_idx = max(0, len(self.filtered_items) - 1)

    def get_header_title(self):
        total_items = len(self.filtered_items)
        cur_page = (self.selected_idx // self.ITEMS_PER_PAGE) + 1 if total_items > 0 else 1
        total_pages = max(1, math.ceil(total_items / self.ITEMS_PER_PAGE)) if total_items > 0 else 1

        mode_map = {
            "all": tr("app_filter_all"),
            "installed": tr("app_filter_installed"),
            "missing": tr("app_filter_missing"),
        }
        mode_str = mode_map.get(self.filter_mode, tr("app_filter_all"))
        cur_info = f" ({total_items})" if total_items > 0 else ""
        return f"{tr('app_store_title')}{cur_info} • [{mode_str}] • {cur_page}/{total_pages}"

    def get_footer_actions(self):
        if self.confirm_uninstall_target is not None:
            return [
                ("A", tr("app_confirm_yes"), (255, 75, 75), (255, 255, 255), True),
                ("B", tr("app_confirm_no"), (120, 140, 170), (220, 225, 235), False),
            ]

        if self.installing_app:
            return []

        actions = []
        if self.filtered_items and 0 <= self.selected_idx < len(self.filtered_items):
            cur = self.filtered_items[self.selected_idx]
            if cur.get("installed"):
                actions.append(("A", tr("app_btn_launch"), (0, 230, 150), (220, 225, 235), True))
                actions.append(("X", tr("app_btn_uninstall"), (255, 100, 100), (220, 225, 235), False))
            else:
                actions.append(("A", tr("app_btn_install"), (0, 230, 150), (220, 225, 235), True))

        actions.append(("Y", tr("app_btn_filter"), (255, 200, 0), (220, 225, 235), True))
        actions.append(("B", tr("footer_back"), (255, 75, 75), (220, 225, 235), False))
        return actions

    def handle_input(self, inputs):
        if self.installing_app:
            return False

        btn_up = inputs.get("btn_up")
        btn_down = inputs.get("btn_down")
        btn_a = inputs.get("btn_a")
        btn_b = inputs.get("btn_b")
        btn_x = inputs.get("btn_x")
        btn_y = inputs.get("btn_y")
        btn_l1 = inputs.get("btn_l1")
        btn_r1 = inputs.get("btn_r1")

        # Handle Confirm Uninstall Modal
        if self.confirm_uninstall_target is not None:
            if btn_b:
                self.confirm_uninstall_target = None
                return True
            if btn_a:
                target = self.confirm_uninstall_target
                self.confirm_uninstall_target = None
                self._start_uninstall_app(target)
                return True
            return False

        total_items = len(self.filtered_items)
        if total_items == 0:
            if btn_b:
                self.engine.pop_screen()
                return True
            if btn_y:
                self._cycle_filter()
                return True
            return False

        item = self.filtered_items[self.selected_idx] if 0 <= self.selected_idx < total_items else {}

        if btn_b:
            self.engine.pop_screen()
            return True

        if btn_up:
            if self.selected_idx > 0:
                self.selected_idx -= 1
            else:
                self.selected_idx = total_items - 1
            return True

        elif btn_down:
            if self.selected_idx < total_items - 1:
                self.selected_idx += 1
            else:
                self.selected_idx = 0
            return True

        elif btn_l1:
            self.selected_idx = max(0, self.selected_idx - self.ITEMS_PER_PAGE)
            return True

        elif btn_r1:
            self.selected_idx = min(total_items - 1, self.selected_idx + self.ITEMS_PER_PAGE)
            return True

        elif btn_y:
            self._cycle_filter()
            return True

        elif btn_a and 0 <= self.selected_idx < total_items:
            if item.get("installed"):
                self._launch_app(item)
            else:
                self._start_install_app(item)
            return True

        elif btn_x and 0 <= self.selected_idx < total_items:
            if item.get("installed"):
                self.confirm_uninstall_target = item
                return True

        return False

    def _cycle_filter(self):
        filters = ["all", "installed", "missing"]
        try:
            curr_i = filters.index(self.filter_mode)
            self.filter_mode = filters[(curr_i + 1) % len(filters)]
        except ValueError:
            self.filter_mode = "all"
        self.selected_idx = 0
        self.scroll_top = 0
        self.apply_filter()

    def _launch_app(self, item):
        app_id = item.get("id")
        app_path = item.get("installed_path")
        if not app_path or not os.path.isdir(app_path):
            app_path = os.path.join(paths.APPS_DIR, app_id)
            if not os.path.isdir(app_path) and app_id == "RetroArch":
                boot_ra = os.path.join(paths.APPS_DIR, "BootRetroArch")
                if os.path.isdir(boot_ra):
                    app_path = boot_ra

        if not os.path.isdir(app_path):
            if hasattr(self.engine, "toast"):
                self.engine.toast("Không tìm thấy thư mục ứng dụng!")
            return

        # Tim file thuc thi launch.sh hoac duoc chi dinh trong config
        launch_file = "launch.sh"
        if item.get("launch") and os.path.isfile(os.path.join(app_path, item.get("launch"))):
            launch_file = item.get("launch")

        full_launch = os.path.join(app_path, launch_file)
        if not os.path.isfile(full_launch):
            if hasattr(self.engine, "toast"):
                self.engine.toast(f"Không tìm thấy {launch_file}!")
            return

        try:
            os.chmod(full_launch, 0o755)
        except Exception:
            pass

        app_name = item.get("name", app_id)
        if hasattr(self.engine, "toast"):
            self.engine.toast(f"Đang mở {app_name}...")

        handoff_script = f"""#!/bin/sh
cd "{app_path}"
"./{launch_file}"
"""
        try:
            with open("/tmp/launch_game.sh", "w", encoding="utf-8") as f:
                f.write(handoff_script)
            os.chmod("/tmp/launch_game.sh", 0o755)
            with open("/tmp/rh_last_screen.txt", "w", encoding="utf-8") as f:
                f.write("app_store")
            self.engine.running = False
        except Exception as e:
            if hasattr(self.engine, "toast"):
                self.engine.toast(f"Lỗi khởi động: {e}")

    def _start_install_app(self, item):
        app_id = item.get("id")
        if not app_id or self.installing_app:
            return

        self.installing_app = True
        self.install_target_item = item
        self.install_action_type = "install"
        self.install_stage = "downloading"
        self.install_msg = tr("app_downloading")
        self.install_progress = 0

        def _worker():
            def _prog(cur, total):
                if total > 0:
                    self.install_progress = int((cur / total) * 100)

            def _status_cb(stage):
                self.install_stage = stage
                if stage == "downloading":
                    self.install_msg = tr("app_downloading")
                elif stage == "installing":
                    self.install_msg = tr("app_extracting")
                    self.install_progress = 100

            ok, msg = install_app(app_id, on_progress=_prog, on_status=_status_cb)
            time.sleep(0.4)
            self.installing_app = False
            self.install_msg = tr("app_install_success") if ok else f"{tr('app_install_failed')} ({msg})"
            self.refresh_catalog()

        threading.Thread(target=_worker, daemon=True).start()

    def _start_uninstall_app(self, item):
        app_id = item.get("id")
        if not app_id or self.installing_app:
            return

        self.installing_app = True
        self.install_target_item = item
        self.install_action_type = "uninstall"
        self.install_stage = "uninstalling"
        self.install_msg = tr("app_uninstalling")
        self.install_progress = 100

        def _worker():
            ok, msg = uninstall_app(app_id)
            time.sleep(0.4)
            self.installing_app = False
            self.install_msg = tr("app_uninstall_success") if ok else f"Gỡ bỏ thất bại ({msg})"
            self.refresh_catalog()

        threading.Thread(target=_worker, daemon=True).start()

    def render(self, engine):
        total_items = len(self.filtered_items)
        if total_items == 0:
            engine.draw_text(tr("app_empty_filter"), engine.font_item,
                             state.SCREEN_W // 2, state.SCREEN_H // 2, 160, 175, 195, center_x=True, center_y=True)
            return

        # Split Layout: Left list (54% width), Right details (46% width)
        left_w = int(state.SCREEN_W * 0.54)
        right_w = state.SCREEN_W - left_w - 40
        start_y = 64 + 14
        card_h = 76
        gap = 10
        max_visible = 6

        # Scroll bounds
        max_scroll = max(0, total_items - max_visible)
        if self.selected_idx < self.scroll_top:
            self.scroll_top = self.selected_idx
        elif self.selected_idx >= self.scroll_top + max_visible:
            self.scroll_top = self.selected_idx - max_visible + 1
        self.scroll_top = max(0, min(max_scroll, self.scroll_top))

        visible_items = self.filtered_items[self.scroll_top : self.scroll_top + max_visible]

        # 1. Draw Left List
        panel_x = 24
        for i, item in enumerate(visible_items):
            actual_idx = self.scroll_top + i
            cy = start_y + i * (card_h + gap)
            is_sel = (actual_idx == self.selected_idx)
            is_inst = item.get("installed", False)
            app_id = item.get("id", "")

            if is_sel:
                engine.fill_rect(panel_x, cy, left_w, card_h, 28, 44, 75, 255)
                engine.draw_rect(panel_x, cy, left_w, card_h, 0, 246, 246, 255, thickness=3)
                engine.fill_rect(panel_x + 3, cy + 6, 8, card_h - 12, 0, 246, 246, 255)
                text_r, text_g, text_b = 255, 255, 255
            else:
                engine.fill_rect(panel_x, cy, left_w, card_h, 19, 26, 42, 255)
                engine.draw_rect(panel_x, cy, left_w, card_h, 40, 54, 85, 255, thickness=1)
                text_r, text_g, text_b = 200, 210, 225

            # App Icon (46x46)
            icon_file = item.get("icon_preview_local") or os.path.join(APP_DIR, "assets", "apps_preview", f"{app_id}.png")
            icon_x = panel_x + 16
            icon_y = cy + (card_h - 46) // 2
            if icon_file and os.path.isfile(icon_file):
                engine.draw_proportional_boxart(icon_file, icon_x, icon_y, 46, 46)
            else:
                engine.fill_rect(icon_x, icon_y, 46, 46, 12, 16, 28, 255)
                engine.draw_text(app_id[:3].upper(), engine.font_badge, icon_x + 23, icon_y + 23, 100, 130, 170, center_x=True, center_y=True)

            # App Name (Centered vertically in the card)
            text_x = icon_x + 46 + 14
            title_text = f"{actual_idx + 1}. {item.get('name', app_id)}"
            engine.draw_text(title_text, engine.font_item, text_x, cy + (card_h // 2), text_r, text_g, text_b, center_y=True)

            # Badge: INSTALLED / NOT INSTALLED
            badge_w = 92
            badge_h = 36
            badge_x = panel_x + left_w - badge_w - 14
            badge_y = cy + (card_h - badge_h) // 2

            if is_inst:
                engine.fill_rect(badge_x, badge_y, badge_w, badge_h, 20, 60, 40, 255)
                engine.draw_rect(badge_x, badge_y, badge_w, badge_h, 34, 197, 94, 255, thickness=1)
                engine.draw_text(tr("app_installed_badge"), engine.font_badge, badge_x + badge_w // 2, badge_y + badge_h // 2, 74, 222, 128, center_x=True, center_y=True)
            else:
                engine.fill_rect(badge_x, badge_y, badge_w, badge_h, 35, 40, 55, 255)
                engine.draw_rect(badge_x, badge_y, badge_w, badge_h, 80, 95, 125, 255, thickness=1)
                engine.draw_text(tr("app_not_installed_badge"), engine.font_badge, badge_x + badge_w // 2, badge_y + badge_h // 2, 160, 175, 200, center_x=True, center_y=True)

        # 2. Draw Right Details Panel
        if 0 <= self.selected_idx < total_items:
            sel_item = self.filtered_items[self.selected_idx]
            right_x = panel_x + left_w + 16
            right_y = start_y
            right_h = 6 * (card_h + gap) - gap

            # Background Box
            engine.fill_rect(right_x, right_y, right_w, right_h, 16, 23, 38, 255)
            engine.draw_rect(right_x, right_y, right_w, right_h, 45, 60, 95, 255, thickness=1)

            # Icon Box
            app_id = sel_item.get("id", "")
            preview_file = sel_item.get("icon_preview_local") or os.path.join(APP_DIR, "assets", "apps_preview", f"{app_id}.png")

            pad_x = 20
            img_box_h = 96
            img_box_w = right_w - pad_x * 2
            img_box_x = right_x + pad_x
            img_box_y = right_y + 16
            engine.fill_rect(img_box_x, img_box_y, img_box_w, img_box_h, 10, 14, 24, 255)

            if preview_file and os.path.isfile(preview_file):
                engine.draw_proportional_boxart(preview_file, img_box_x, img_box_y, img_box_w, img_box_h)
            else:
                engine.draw_text(app_id, engine.font_item, img_box_x + img_box_w // 2, img_box_y + img_box_h // 2, 100, 130, 170, center_x=True, center_y=True)

            # Details with generous padding
            cur_y = img_box_y + img_box_h + 18
            engine.draw_text(sel_item.get("name", app_id), engine.font_item, right_x + pad_x, cur_y, 255, 255, 255)

            cur_y += 34
            is_inst = sel_item.get("installed", False)
            status_str = tr("app_installed_badge") if is_inst else tr("app_not_installed_badge")
            status_color = (74, 222, 128) if is_inst else (180, 195, 215)
            engine.draw_text(f"Status: {status_str}", engine.font_badge, right_x + pad_x, cur_y, *status_color)

            cur_y += 28
            size_str = sel_item.get("package_size", "Unknown")
            engine.draw_text(f"Size: {size_str} • Author: {sel_item.get('author', 'Unknown')}", engine.font_badge, right_x + pad_x, cur_y, 140, 160, 190)

            # Subtle separator
            cur_y += 34
            engine.fill_rect(right_x + pad_x, cur_y - 12, right_w - pad_x * 2, 1, 40, 55, 80, 160)

            # Description (Bilingual based on state.current_lang, generous line spacing)
            desc_key = "desc_vi" if state.current_lang == "VI" else "desc_en"
            desc = sel_item.get(desc_key) or sel_item.get("desc_vi") or sel_item.get("desc_en") or ""
            if desc:
                max_desc_w = right_w - pad_x * 2 - 12
                lines = engine.wrap_text_to_width(desc, engine.font_badge, max_desc_w, max_lines=6)
                for line in lines:
                    engine.draw_text(line, engine.font_badge, right_x + pad_x, cur_y, 200, 215, 235)
                    cur_y += 28

            # Notification toast box at bottom of right panel (when idle)
            if not self.installing_app and self.install_msg and self.confirm_uninstall_target is None:
                ov_w = right_w - pad_x * 2
                ov_h = 42
                ov_x = right_x + pad_x
                ov_y = right_y + right_h - ov_h - 16
                engine.fill_rect(ov_x, ov_y, ov_w, ov_h, 16, 32, 24, 240)
                engine.draw_rect(ov_x, ov_y, ov_w, ov_h, 34, 197, 94, 255, thickness=1)
                engine.draw_text(self.install_msg, engine.font_badge, ov_x + ov_w // 2, ov_y + ov_h // 2, 74, 222, 128, center_x=True, center_y=True)

        # 3. Draw Confirm Uninstall Modal (Centered Pop-up with generous vertical spacing)
        if self.confirm_uninstall_target is not None:
            target = self.confirm_uninstall_target
            # Dark backdrop
            engine.fill_rect(0, 0, state.SCREEN_W, state.SCREEN_H, 0, 0, 0, 215)

            mw = min(640, int(state.SCREEN_W * 0.75))
            mh = 300
            mx = (state.SCREEN_W - mw) // 2
            my = (state.SCREEN_H - mh) // 2

            # Main dialog box
            engine.fill_rect(mx, my, mw, mh, 20, 26, 40, 255)
            engine.draw_rect(mx, my, mw, mh, 255, 85, 85, 255, thickness=2)

            # Title bar
            engine.fill_rect(mx + 2, my + 2, mw - 4, 50, 48, 22, 28, 255)
            engine.draw_text(tr("app_confirm_uninstall_title"), engine.font_item, mx + mw // 2, my + 27, 255, 95, 95, center_x=True, center_y=True)

            # Target App Name
            target_name = target.get("name", target.get("id", ""))
            engine.draw_text(target_name, engine.font_item, mx + mw // 2, my + 95, 255, 255, 255, center_x=True, center_y=True)

            # Warning description
            engine.draw_text(tr("app_confirm_uninstall_msg"), engine.font_badge, mx + mw // 2, my + 138, 210, 220, 235, center_x=True, center_y=True)
            sub_dir = f"SDCARD/Apps/{target.get('id', '')}"
            sub_txt = f"Toàn bộ thư mục {sub_dir} sẽ bị xóa." if state.current_lang == "VI" else f"Directory {sub_dir} will be deleted."
            engine.draw_text(sub_txt, engine.font_badge, mx + mw // 2, my + 170, 150, 165, 185, center_x=True, center_y=True)

            # Buttons: [A] Gỡ bỏ  [B] Hủy
            btn_w = 160
            btn_h = 42
            btn_y = my + mh - btn_h - 24

            # [A] Confirm Button (Red)
            btn_a_x = mx + mw // 2 - btn_w - 18
            engine.fill_rect(btn_a_x, btn_y, btn_w, btn_h, 180, 45, 45, 255)
            engine.draw_rect(btn_a_x, btn_y, btn_w, btn_h, 255, 90, 90, 255, thickness=1)
            engine.draw_text(f"[A] {tr('app_confirm_yes')}", engine.font_badge, btn_a_x + btn_w // 2, btn_y + btn_h // 2, 255, 255, 255, center_x=True, center_y=True)

            # [B] Cancel Button (Dark blue/gray)
            btn_b_x = mx + mw // 2 + 18
            engine.fill_rect(btn_b_x, btn_y, btn_w, btn_h, 35, 46, 68, 255)
            engine.draw_rect(btn_b_x, btn_y, btn_w, btn_h, 75, 95, 130, 255, thickness=1)
            engine.draw_text(f"[B] {tr('app_confirm_no')}", engine.font_badge, btn_b_x + btn_w // 2, btn_y + btn_h // 2, 210, 220, 235, center_x=True, center_y=True)

        # 4. Draw Install/Uninstall Progress Modal (Centered Pop-up with distinct Download/Install stages)
        elif self.installing_app:
            # Dark backdrop
            engine.fill_rect(0, 0, state.SCREEN_W, state.SCREEN_H, 0, 0, 0, 215)

            mw = min(660, int(state.SCREEN_W * 0.8))
            mh = 310
            mx = (state.SCREEN_W - mw) // 2
            my = (state.SCREEN_H - mh) // 2

            # Modal Frame
            engine.fill_rect(mx, my, mw, mh, 18, 26, 44, 255)
            engine.draw_rect(mx, my, mw, mh, 0, 230, 255, 255, thickness=2)

            # Title bar with stage differentiation
            engine.fill_rect(mx + 2, my + 2, mw - 4, 50, 25, 38, 62, 255)
            if self.install_action_type == "install":
                if getattr(self, "install_stage", "downloading") == "downloading":
                    modal_title = tr("app_downloading_modal_title")
                else:
                    modal_title = tr("app_installing_modal_title")
            else:
                modal_title = tr("app_uninstalling_modal_title")
            engine.draw_text(modal_title, engine.font_item, mx + mw // 2, my + 27, 0, 246, 246, center_x=True, center_y=True)

            # Target item details
            item = self.install_target_item or (self.filtered_items[self.selected_idx] if 0 <= self.selected_idx < total_items else {})
            app_id = item.get("id", "")
            app_name = item.get("name", app_id)

            # App Icon (52x52)
            icon_file = item.get("icon_preview_local") or os.path.join(APP_DIR, "assets", "apps_preview", f"{app_id}.png")
            icon_x = mx + 45
            icon_y = my + 76
            if icon_file and os.path.isfile(icon_file):
                engine.draw_proportional_boxart(icon_file, icon_x, icon_y, 52, 52)
            else:
                engine.fill_rect(icon_x, icon_y, 52, 52, 12, 16, 28, 255)
                engine.draw_text(app_id[:3].upper(), engine.font_badge, icon_x + 26, icon_y + 26, 100, 130, 170, center_x=True, center_y=True)

            # App Name
            engine.draw_text(app_name, engine.font_item, icon_x + 68, my + 88, 255, 255, 255)

            # Status Message & Percentage
            status_y = my + 144
            engine.draw_text(self.install_msg, engine.font_badge, icon_x, status_y, 0, 220, 255)

            # Percentage text cleanly aligned within modal boundary
            if self.install_action_type == "install":
                prog_txt = f"{self.install_progress}%"
                # Placed comfortably inside the right margin (aligned with progress bar end)
                engine.draw_text(prog_txt, engine.font_item, mx + mw - 75, status_y, 0, 230, 150, center_x=True, center_y=True)

            # Progress Bar
            pb_x = mx + 45
            pb_y = my + 176
            pb_w = mw - 90
            pb_h = 22
            engine.fill_rect(pb_x, pb_y, pb_w, pb_h, 12, 18, 30, 255)
            engine.draw_rect(pb_x, pb_y, pb_w, pb_h, 50, 75, 110, 255, thickness=1)

            fill_pct = max(0, min(100, self.install_progress)) if self.install_action_type == "install" else 100
            fill_w = int((pb_w - 4) * (fill_pct / 100.0))
            if fill_w > 0:
                engine.fill_rect(pb_x + 2, pb_y + 2, fill_w, pb_h - 4, 0, 230, 150, 255)

            # Bottom advisory notice
            notice = "Vui lòng giữ kết nối và không tắt nguồn..." if state.current_lang == "VI" else "Please wait and do not turn off device..."
            engine.draw_text(notice, engine.font_badge, mx + mw // 2, my + 250, 140, 160, 195, center_x=True, center_y=True)
