# -*- coding: utf-8 -*-
"""Full-screen Emulator Store & Package Manager for TrimUI RetroHub."""

import os
import math
import time
import threading
from .. import state
from ..paths import EMUS_DIR, SDCARD_PATH, APP_DIR
from ..i18n import tr
from ..emulator_store import (
    get_emus_status,
    install_emu,
)
from ..modals.j2me import J2meModal
from .base import BaseScreen


class EmuStoreScreen(BaseScreen):
    """Full-screen Split View Emulator Store Screen."""

    ITEMS_PER_PAGE = 5

    def __init__(self, engine=None):
        super().__init__(engine)
        self.raw_emus = []
        self.filtered_items = []
        self.selected_idx = 0
        self.scroll_top = 0
        self.filter_mode = "all"  # "all", "installed", "missing", "8_16bit", "handheld", "3d", "arcade", "engines"
        self.focus_right = False
        self.installing_emu = False
        self.install_emu_info = {}
        self.install_msg = ""
        self.cached_preview_path = None
        self.confirm_install_all = False
        self.missing_emus_to_install = []
        self.install_all_running = False
        self.install_all_total = 0
        self.install_all_cur = 0
        self.view_mode = "auto"

    def on_enter(self, params=None):
        self.focus_right = False
        self.refresh_catalog()

    def refresh_catalog(self, force_reload=False):
        """Reloads emulator catalog and status."""
        try:
            self.raw_emus = get_emus_status() or []
        except Exception as e:
            print(f"[EmuStoreScreen] Error loading emus: {e}")
            self.raw_emus = []

        missing = [it for it in self.raw_emus if not it.get("installed")]
        if not missing:
            self.view_mode = "list"
        elif getattr(self, "view_mode", "auto") != "list":
            self.view_mode = "single_option"

        self.apply_filter()

    def apply_filter(self):
        """Applies filter mode to the emulator list."""
        self.filtered_items = []

        for item in self.raw_emus:
            is_inst = item.get("installed", False)
            cat = item.get("category", "")

            if self.filter_mode == "installed" and not is_inst:
                continue
            if self.filter_mode == "missing" and is_inst:
                continue
            if self.filter_mode == "8_16bit" and cat not in ("8-Bit", "16-Bit"):
                continue
            if self.filter_mode == "handheld" and cat != "Handheld":
                continue
            if self.filter_mode == "3d" and cat != "3D Consoles":
                continue
            if self.filter_mode == "arcade" and cat != "Arcade":
                continue
            if self.filter_mode == "engines" and cat not in ("Engines", "Media"):
                continue

            lbl = tr("emu_installed_badge") if is_inst else tr("emu_not_installed_badge")
            entry = dict(item)
            entry["label"] = lbl
            self.filtered_items.append(entry)

        for idx, it in enumerate(self.filtered_items):
            it["display_title"] = f"{idx + 1}. {it.get('name', it.get('id', ''))}"

        if self.selected_idx >= len(self.filtered_items):
            self.selected_idx = max(0, len(self.filtered_items) - 1)

    def get_header_title(self):
        if getattr(self, "view_mode", "auto") == "single_option":
            return f"{tr('emu_store_title')} • [{tr('emu_single_opt_badge')}]"

        total_items = len(self.filtered_items)
        cur_page = (self.selected_idx // self.ITEMS_PER_PAGE) + 1 if total_items > 0 else 1
        total_pages = max(1, math.ceil(total_items / self.ITEMS_PER_PAGE)) if total_items > 0 else 1

        mode_map = {
            "all": tr("emu_filter_all"),
            "installed": tr("emu_filter_installed"),
            "missing": tr("emu_filter_missing"),
            "8_16bit": "8/16-Bit",
            "handheld": "Handheld",
            "3d": "3D Consoles",
            "arcade": "Arcade",
            "engines": "Engines",
        }
        mode_str = mode_map.get(self.filter_mode, tr("emu_filter_all"))

        cur_info = ""
        if 0 <= self.selected_idx < total_items:
            it = self.filtered_items[self.selected_idx]
            name_str = it.get("name", it.get("id", ""))
            size_str = f" • {it.get('package_size')}" if it.get("package_size") else ""
            cur_info = f" • #{self.selected_idx + 1} {name_str}{size_str}"

        return f"{tr('emu_store_title')}{cur_info} • [{mode_str}] • {cur_page}/{total_pages}"

    def get_footer_actions(self):
        if self.confirm_install_all:
            return [
                ("A", tr("app_confirm_yes"), (0, 230, 150), (255, 255, 255), True),
                ("B", tr("app_confirm_no"), (120, 140, 170), (220, 225, 235), False),
            ]

        if getattr(self, "view_mode", "auto") == "single_option":
            return [
                ("A", tr("emu_btn_install_all"), (0, 230, 150), (255, 255, 255), True),
                ("B", tr("footer_back"), (255, 75, 75), (220, 225, 235), False),
            ]

        if not self.filtered_items or self.selected_idx < 0 or self.selected_idx >= len(self.filtered_items):
            return [("B", tr("footer_back"), (255, 75, 75), (220, 225, 235), False)]

        item = self.filtered_items[self.selected_idx]
        is_java = (item.get("id") == "JAVA" and item.get("installed"))

        if self.focus_right:
            return [
                ("A", "Mở cài đặt" if state.current_lang == "VI" else "Open Settings", (0, 246, 246), (220, 225, 235), True),
                ("B", "Trở lại" if state.current_lang == "VI" else "Back to List", (255, 75, 75), (220, 225, 235), False),
            ]

        actions = []
        if is_java:
            actions.append(("A", "Cài đặt Java" if state.current_lang == "VI" else "Java Settings", (0, 246, 246), (220, 225, 235), True))

        actions.append(("SELECT", tr("emu_btn_install_all"), (255, 140, 0), (220, 225, 235), True))
        actions.append(("Y", tr("emu_btn_filter"), (0, 230, 255), (220, 225, 235), True))
        actions.append(("L1/R1", "Trang" if state.current_lang == "VI" else "Page", (70, 95, 140), (220, 225, 235), False))
        actions.append(("B", tr("footer_back"), (255, 75, 75), (220, 225, 235), False))
        return actions

    def handle_input(self, inputs):
        if self.installing_emu:
            return True

        btn_up = inputs.get("btn_up")
        btn_down = inputs.get("btn_down")
        btn_left = inputs.get("btn_left")
        btn_right = inputs.get("btn_right")
        btn_start = inputs.get("btn_start")
        btn_select = inputs.get("btn_select")
        btn_a = inputs.get("btn_a")
        btn_b = inputs.get("btn_b")
        btn_y = inputs.get("btn_y")
        btn_l1 = inputs.get("btn_l1")
        btn_r1 = inputs.get("btn_r1")

        # Modal xac nhan cai toan bo gia lap
        if self.confirm_install_all:
            if btn_b:
                self.confirm_install_all = False
                return True
            if btn_a:
                items_to_install = list(self.missing_emus_to_install)
                self.confirm_install_all = False
                self._start_install_all_emus(items_to_install)
                return True
            return False

        # Xu ly giao dien 1 option (Single Option Mode: chi co duy nhat luong cai toan bo)
        if getattr(self, "view_mode", "auto") == "single_option":
            if btn_b:
                self.engine.pop_screen()
                return True
            if btn_a:
                self.missing_emus_to_install = list(self.raw_emus)
                self.confirm_install_all = True
                return True
            return False

        # Phim SELECT trong list view de cai dat lai toan bo
        if btn_select:
            self.missing_emus_to_install = list(self.raw_emus)
            self.confirm_install_all = True
            return True

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
        is_java_installed = (item.get("id") == "JAVA" and item.get("installed"))

        # Direct START hotkey to open Java Settings whenever Java is selected
        if is_java_installed and btn_start:
            self.engine.open_modal(J2meModal(self.engine))
            return True

        # When right details panel button is focused
        if self.focus_right:
            if btn_b or btn_left:
                self.focus_right = False
                return True
            if btn_a:
                self.engine.open_modal(J2meModal(self.engine))
                return True
            if btn_up or btn_down:
                self.focus_right = False
            else:
                return True

        if btn_b:
            self.engine.pop_screen()
            return True

        if btn_right and is_java_installed:
            self.focus_right = True
            return True

        if btn_up:
            self.focus_right = False
            if self.selected_idx > 0:
                self.selected_idx -= 1
            else:
                self.selected_idx = total_items - 1
            return True

        elif btn_down:
            self.focus_right = False
            if self.selected_idx < total_items - 1:
                self.selected_idx += 1
            else:
                self.selected_idx = 0
            return True

        elif btn_l1:
            self.focus_right = False
            self.selected_idx = max(0, self.selected_idx - self.ITEMS_PER_PAGE)
            return True

        elif btn_r1:
            self.focus_right = False
            self.selected_idx = min(total_items - 1, self.selected_idx + self.ITEMS_PER_PAGE)
            return True

        elif btn_y:
            self.focus_right = False
            self._cycle_filter()
            return True

        elif btn_a and 0 <= self.selected_idx < total_items:
            # Nut A chi mo cai dat Java neu dang o he may Java (khong cai le tung he)
            if is_java_installed:
                self.engine.open_modal(J2meModal(self.engine))
                return True

        return False

    def _start_install_all_emus(self, items_to_install):
        if not items_to_install or self.installing_emu:
            return

        self.installing_emu = True
        self.install_all_running = True
        self.install_all_total = len(items_to_install)
        self.install_all_cur = 0

        def run_task():
            total = len(items_to_install)
            for idx, emu in enumerate(items_to_install):
                sys_id = emu.get("id")
                self.install_all_cur = idx + 1
                self.install_emu_info = emu
                self.install_msg = tr("emu_install_all_progress").format(
                    sys=emu.get("name", sys_id), cur=idx + 1, total=total
                )
                try:
                    install_emu(sys_id)
                except Exception as e:
                    print(f"[EmuStore] Error installing {sys_id}: {e}")
                time.sleep(0.3)

            self.installing_emu = False
            self.install_all_running = False
            self.view_mode = "list"
            if self.engine:
                self.engine.toast(tr("emu_install_all_done"), text_color=(0, 255, 160))
            self.refresh_catalog()

        threading.Thread(target=run_task, daemon=True).start()

    def _cycle_filter(self):
        self.focus_right = False
        filters = ["all", "installed", "missing", "8_16bit", "handheld", "3d", "arcade", "engines"]
        try:
            curr_i = filters.index(self.filter_mode)
            self.filter_mode = filters[(curr_i + 1) % len(filters)]
        except ValueError:
            self.filter_mode = "all"
        self.selected_idx = 0
        self.scroll_top = 0
        self.apply_filter()

    def render(self, engine):
        try:
            if getattr(self, "view_mode", "auto") == "single_option":
                self._render_single_option(engine)
            else:
                self._render_content(engine)
        except Exception as e:
            print(f"[EmuStoreScreen] Render error: {e}")
            engine.draw_text(f'{tr("store_err_render")}: {str(e)}', engine.font_item,
                             state.SCREEN_W // 2, state.SCREEN_H // 2, 255, 100, 100, center_x=True, center_y=True)

    def _render_content(self, engine):
        total_items = len(self.filtered_items)
        if total_items == 0:
            engine.draw_text(tr("emu_empty_filter"), engine.font_item,
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
            sys_id = item.get("id", "").lower()

            if is_sel:
                engine.fill_rect(panel_x, cy, left_w, card_h, 28, 44, 75, 255)
                engine.draw_rect(panel_x, cy, left_w, card_h, 0, 246, 246, 255, thickness=3)
                engine.fill_rect(panel_x + 3, cy + 6, 8, card_h - 12, 0, 246, 246, 255)
                text_r, text_g, text_b = 255, 255, 255
            else:
                engine.fill_rect(panel_x, cy, left_w, card_h, 19, 26, 42, 255)
                engine.draw_rect(panel_x, cy, left_w, card_h, 40, 54, 85, 255, thickness=1)
                text_r, text_g, text_b = 200, 210, 225

            # System Icon (46x46)
            icon_file = os.path.join(APP_DIR, "assets", "emus_preview", f"ic-{sys_id}.png")
            icon_x = panel_x + 16
            icon_y = cy + (card_h - 46) // 2
            if os.path.isfile(icon_file):
                engine.draw_proportional_boxart(icon_file, icon_x, icon_y, 46, 46)
            else:
                engine.fill_rect(icon_x, icon_y, 46, 46, 12, 16, 28, 255)
                engine.draw_text(sys_id[:3].upper(), engine.font_badge, icon_x + 23, icon_y + 23, 100, 130, 170, center_x=True, center_y=True)

            # System Name & Category
            text_x = icon_x + 46 + 12
            title_text = f"{actual_idx + 1}. {item.get('name', item.get('id', ''))}"
            engine.draw_text(title_text, engine.font_item, text_x, cy + 22, text_r, text_g, text_b)
            
            sub_info = f"{item.get('category', '')} • Core: {item.get('active_core') or item.get('core', '')}"
            engine.draw_text(sub_info, engine.font_badge, text_x, cy + 48, 130, 150, 180)

            # Badge: INSTALLED / MISSING
            badge_w = 92
            badge_h = 36
            badge_x = panel_x + left_w - badge_w - 14
            badge_y = cy + (card_h - badge_h) // 2
            
            if is_inst:
                engine.fill_rect(badge_x, badge_y, badge_w, badge_h, 20, 60, 40, 255)
                engine.draw_rect(badge_x, badge_y, badge_w, badge_h, 34, 197, 94, 255, thickness=1)
                engine.draw_text(tr("emu_installed"), engine.font_badge, badge_x + badge_w // 2, badge_y + badge_h // 2, 74, 222, 128, center_x=True, center_y=True)
            else:
                engine.fill_rect(badge_x, badge_y, badge_w, badge_h, 35, 40, 55, 255)
                engine.draw_rect(badge_x, badge_y, badge_w, badge_h, 80, 95, 125, 255, thickness=1)
                engine.draw_text(tr("emu_not_installed"), engine.font_badge, badge_x + badge_w // 2, badge_y + badge_h // 2, 160, 175, 200, center_x=True, center_y=True)

        # 2. Draw Right Details Panel
        if 0 <= self.selected_idx < total_items:
            sel_item = self.filtered_items[self.selected_idx]
            right_x = panel_x + left_w + 16
            right_y = start_y
            right_h = 6 * (card_h + gap) - gap

            # Background Box
            engine.fill_rect(right_x, right_y, right_w, right_h, 16, 23, 38, 255)
            engine.draw_rect(right_x, right_y, right_w, right_h, 45, 60, 95, 255, thickness=1)

            # Preview Image / Poster
            sys_id = sel_item.get("id", "").lower()
            preview_file = os.path.join(APP_DIR, "assets", "emus_preview", f"poster-{sys_id}.png")
            if not os.path.isfile(preview_file):
                preview_file = os.path.join(APP_DIR, "assets", "emus_preview", f"ic-{sys_id}.png")

            pad_x = 18
            img_box_h = 108
            img_box_w = right_w - pad_x * 2
            img_box_x = right_x + pad_x
            img_box_y = right_y + 16
            engine.fill_rect(img_box_x, img_box_y, img_box_w, img_box_h, 10, 14, 24, 255)

            if os.path.isfile(preview_file):
                engine.draw_proportional_boxart(preview_file, img_box_x, img_box_y, img_box_w, img_box_h)

            # Details text below preview with generous padding and separate lines
            text_x = img_box_x + 4
            text_start_y = img_box_y + img_box_h + 16

            # System Title
            title_name = f"{sel_item.get('name', '')} ({sel_item.get('id', '')})"
            engine.draw_text(title_name, engine.font_title, text_x, text_start_y, 0, 240, 255)

            # Each item on its own line with generous line-height
            info_y = text_start_y + 34
            row_gap = 26

            # 1. Company
            comp = sel_item.get('company') or tr('emu_unknown')
            engine.draw_text(f'{tr("emu_company")}  {comp}', engine.font_badge, text_x, info_y + 0 * row_gap, 190, 210, 235)

            # 2. Year
            year_val = sel_item.get('year') or 'N/A'
            engine.draw_text(f'{tr("emu_year")}  {year_val}', engine.font_badge, text_x, info_y + 1 * row_gap, 190, 210, 235)

            # 3. Core / Emulator
            core_name = sel_item.get('active_core') or sel_item.get('core', 'RetroArch')
            engine.draw_text(f'{tr("emu_core")}   {core_name}', engine.font_badge, text_x, info_y + 2 * row_gap, 255, 210, 95)

            # 4. ROMs count
            roms_val = tr("emu_roms_count").format(n=sel_item.get("rom_count", 0))
            engine.draw_text(f'{tr("emu_roms")} {roms_val}', engine.font_badge, text_x, info_y + 3 * row_gap, 110, 235, 165)

            # 5. Package Size
            pkg_size = sel_item.get('package_size') or tr('emu_updating')
            engine.draw_text(f'{tr("emu_pkg_size")} {pkg_size}', engine.font_badge, text_x, info_y + 4 * row_gap, 160, 205, 250)

            # Divider line with comfortable top/bottom margin
            div_y = info_y + 5 * row_gap + 8
            engine.fill_rect(text_x, div_y, img_box_w - 8, 1, 45, 60, 95, 255)

            # Description (word-wrapped with 22px spacing)
            desc_text = sel_item.get("desc", "")
            if desc_text:
                desc_y = div_y + 14
                lines = engine.wrap_text_to_width(desc_text, engine.font_badge, img_box_w - 12, max_lines=3)
                for li, l_str in enumerate(lines):
                    engine.draw_text(l_str, engine.font_badge, text_x, desc_y + li * 22, 165, 180, 200)

            # If JAVA is installed, show Settings button on the right details panel
            if sel_item.get("id") == "JAVA" and sel_item.get("installed"):
                btn_w = img_box_w
                btn_h = 44
                btn_x = img_box_x
                btn_y = right_y + right_h - btn_h - 14

                vi = (state.current_lang == "VI")
                cfg_btn_txt = "CÀI ĐẶT JAVA (START)" if vi else "JAVA SETTINGS (START)"

                if self.focus_right:
                    engine.fill_rect(btn_x, btn_y, btn_w, btn_h, 30, 60, 105, 255)
                    engine.draw_rect(btn_x, btn_y, btn_w, btn_h, 0, 246, 246, 255, thickness=2)
                    engine.draw_text(cfg_btn_txt, engine.font_sub, btn_x + btn_w // 2, btn_y + btn_h // 2,
                                     255, 255, 255, center_x=True, center_y=True)
                else:
                    engine.fill_rect(btn_x, btn_y, btn_w, btn_h, 22, 32, 54, 255)
                    engine.draw_rect(btn_x, btn_y, btn_w, btn_h, 0, 210, 240, 180, thickness=1)
                    engine.draw_text(cfg_btn_txt, engine.font_sub, btn_x + btn_w // 2, btn_y + btn_h // 2,
                                     0, 230, 255, center_x=True, center_y=True)

        # 3. Confirm Install All Modal (Pop-up Dialog with generous spacing)
        if self.confirm_install_all:
            self._render_confirm_install_all(engine)

        # 4. Draw Installation Progress Modal if active
        elif self.installing_emu:
            self._render_install_progress(engine)

    def _render_single_option(self, engine):
        """Render single option view when emulators are not yet fully installed."""
        cw = min(740, int(state.SCREEN_W * 0.78))
        ch = min(460, int(state.SCREEN_H * 0.72))
        cx = (state.SCREEN_W - cw) // 2
        cy = 64 + (state.SCREEN_H - 64 - 48 - ch) // 2

        # 1. Main Background Box
        engine.fill_rect(cx, cy, cw, ch, 18, 26, 44, 255)
        engine.draw_rect(cx, cy, cw, ch, 0, 240, 255, 255, thickness=2)

        # 2. Header Banner
        bh = 54
        engine.fill_rect(cx + 2, cy + 2, cw - 4, bh, 25, 38, 62, 255)
        engine.fill_rect(cx + 2, cy + bh, cw - 4, 1, 45, 60, 95, 255)

        # Banner Icon
        icon_path = os.path.join(APP_DIR, "assets", "emus_preview", "ic-arcade.png")
        if not os.path.isfile(icon_path):
            icon_path = os.path.join(APP_DIR, "assets", "ic-apps.png")
        if os.path.isfile(icon_path):
            engine.draw_proportional_boxart(icon_path, cx + 16, cy + 9, 36, 36)

        # Banner Title
        engine.draw_text(tr("emu_single_opt_title"), engine.font_title, cx + 64, cy + 14, 0, 246, 246)

        # Banner Status Badge
        missing = [it for it in self.raw_emus if not it.get("installed")]
        total = len(self.raw_emus)
        installed = total - len(missing)

        badge_w = 180
        badge_h = 32
        badge_x = cx + cw - badge_w - 16
        badge_y = cy + (bh - badge_h) // 2

        if installed == 0:
            badge_txt = tr("emu_single_opt_missing").format(count=0, total=total)
            engine.fill_rect(badge_x, badge_y, badge_w, badge_h, 60, 25, 25, 255)
            engine.draw_rect(badge_x, badge_y, badge_w, badge_h, 255, 80, 80, 255, thickness=1)
            engine.draw_text(badge_txt, engine.font_badge, badge_x + badge_w // 2, badge_y + badge_h // 2, 255, 120, 120, center_x=True, center_y=True)
        else:
            badge_txt = tr("emu_single_opt_partial").format(count=len(missing), total=total)
            engine.fill_rect(badge_x, badge_y, badge_w, badge_h, 60, 50, 20, 255)
            engine.draw_rect(badge_x, badge_y, badge_w, badge_h, 255, 200, 60, 255, thickness=1)
            engine.draw_text(badge_txt, engine.font_badge, badge_x + badge_w // 2, badge_y + badge_h // 2, 255, 220, 100, center_x=True, center_y=True)

        # 3. Content Description
        sub_y = cy + bh + 20
        engine.draw_text(tr("emu_single_opt_sub"), engine.font_item, cx + 24, sub_y, 255, 255, 255)

        div_y = sub_y + 36
        engine.fill_rect(cx + 24, div_y, cw - 48, 1, 40, 55, 85, 255)

        # 4. Feature Bullets
        bullets = [
            ("✓", tr("emu_single_opt_desc1")),
            ("✓", tr("emu_single_opt_desc2")),
            ("✓", tr("emu_single_opt_desc3")),
            ("✓", tr("emu_single_opt_desc4")),
        ]
        list_y = div_y + 16
        for i, (b_icon, b_text) in enumerate(bullets):
            row_y = list_y + i * 34
            engine.draw_text(b_icon, engine.font_item, cx + 28, row_y, 0, 230, 150)
            engine.draw_text(b_text, engine.font_badge, cx + 56, row_y + 2, 200, 215, 235)

        # 5. Prominent Action Button
        btn_w = cw - 48
        btn_h = 56
        btn_x = cx + 24
        btn_y = cy + ch - btn_h - 20

        pulse = int(math.sin(time.time() * 4) * 15)
        bg_g = max(0, min(255, 160 + pulse))
        engine.fill_rect(btn_x, btn_y, btn_w, btn_h, 0, bg_g, 100, 255)
        engine.draw_rect(btn_x, btn_y, btn_w, btn_h, 0, 246, 246, 255, thickness=2)
        engine.draw_text(tr("emu_single_opt_btn"), engine.font_item, btn_x + btn_w // 2, btn_y + btn_h // 2, 255, 255, 255, center_x=True, center_y=True)

        # 6. Modals if triggered
        if self.confirm_install_all:
            self._render_confirm_install_all(engine)
        elif self.installing_emu:
            self._render_install_progress(engine)

    def _render_confirm_install_all(self, engine):
        engine.fill_rect(0, 0, state.SCREEN_W, state.SCREEN_H, 0, 0, 0, 215)
        mw = min(660, int(state.SCREEN_W * 0.78))
        mh = 290
        mx = (state.SCREEN_W - mw) // 2
        my = (state.SCREEN_H - mh) // 2

        # Box
        engine.fill_rect(mx, my, mw, mh, 20, 28, 44, 255)
        engine.draw_rect(mx, my, mw, mh, 0, 230, 255, 255, thickness=2)

        # Header
        engine.fill_rect(mx + 2, my + 2, mw - 4, 50, 24, 38, 62, 255)
        engine.draw_text(tr("emu_confirm_install_all_title"), engine.font_item, mx + mw // 2, my + 27, 0, 246, 246, center_x=True, center_y=True)

        # Question text
        missing_count = len(getattr(self, "missing_emus_to_install", []))
        msg = tr("emu_confirm_install_all_msg").format(count=missing_count)
        engine.draw_text(msg, engine.font_item, mx + mw // 2, my + 95, 255, 255, 255, center_x=True, center_y=True)

        sub_txt = "Các gói giả lập sẽ được tự động tải về và thiết lập." if state.current_lang == "VI" else "All packages will be downloaded and configured automatically."
        engine.draw_text(sub_txt, engine.font_badge, mx + mw // 2, my + 135, 170, 190, 215, center_x=True, center_y=True)

        sub_note = "Quá trình này có thể mất vài phút tùy vào kết nối mạng." if state.current_lang == "VI" else "This process may take a few minutes depending on Wi-Fi."
        engine.draw_text(sub_note, engine.font_badge, mx + mw // 2, my + 165, 140, 155, 180, center_x=True, center_y=True)

        # Buttons: [A] Đồng ý  [B] Hủy
        btn_w = 160
        btn_h = 42
        btn_y = my + mh - btn_h - 22

        # [A] Confirm (Green)
        btn_a_x = mx + mw // 2 - btn_w - 18
        engine.fill_rect(btn_a_x, btn_y, btn_w, btn_h, 0, 160, 100, 255)
        engine.draw_rect(btn_a_x, btn_y, btn_w, btn_h, 0, 230, 150, 255, thickness=1)
        engine.draw_text(f"[A] {tr('app_confirm_yes')}", engine.font_badge, btn_a_x + btn_w // 2, btn_y + btn_h // 2, 255, 255, 255, center_x=True, center_y=True)

        # [B] Cancel (Blue/gray)
        btn_b_x = mx + mw // 2 + 18
        engine.fill_rect(btn_b_x, btn_y, btn_w, btn_h, 35, 46, 68, 255)
        engine.draw_rect(btn_b_x, btn_y, btn_w, btn_h, 75, 95, 130, 255, thickness=1)
        engine.draw_text(f"[B] {tr('app_confirm_no')}", engine.font_badge, btn_b_x + btn_w // 2, btn_y + btn_h // 2, 210, 220, 235, center_x=True, center_y=True)

    def _render_install_progress(self, engine):
        engine.fill_rect(0, 0, state.SCREEN_W, state.SCREEN_H, 0, 0, 0, 215)
        overlay_w = min(660, int(state.SCREEN_W * 0.8))
        overlay_h = 280
        ox = (state.SCREEN_W - overlay_w) // 2
        oy = (state.SCREEN_H - overlay_h) // 2

        engine.fill_rect(ox, oy, overlay_w, overlay_h, 18, 26, 44, 255)
        engine.draw_rect(ox, oy, overlay_w, overlay_h, 0, 230, 255, 255, thickness=2)

        # Title bar
        engine.fill_rect(ox + 2, oy + 2, overlay_w - 4, 50, 25, 38, 62, 255)
        p_title = tr("emu_confirm_install_all_title") if getattr(self, "install_all_running", False) else tr("emu_installing")
        engine.draw_text(p_title, engine.font_item, ox + overlay_w // 2, oy + 27, 0, 246, 246, center_x=True, center_y=True)

        # System Name / Info
        cur_item = self.install_emu_info or {}
        sys_title = cur_item.get("name", cur_item.get("id", ""))
        engine.draw_text(sys_title, engine.font_item, ox + overlay_w // 2, oy + 88, 255, 255, 255, center_x=True, center_y=True)

        # Status Message
        engine.draw_text(self.install_msg, engine.font_badge, ox + overlay_w // 2, oy + 124, 0, 220, 255, center_x=True, center_y=True)

        # Progress Bar
        bar_w = overlay_w - 90
        bar_h = 20
        bx = ox + 45
        by = oy + 158
        engine.fill_rect(bx, by, bar_w, bar_h, 12, 18, 30, 255)
        engine.draw_rect(bx, by, bar_w, bar_h, 50, 75, 110, 255, thickness=1)

        if getattr(self, "install_all_running", False) and self.install_all_total > 0:
            fill_pct = max(0, min(100, int((self.install_all_cur / self.install_all_total) * 100)))
            fill_w = int((bar_w - 4) * (fill_pct / 100.0))
            if fill_w > 0:
                engine.fill_rect(bx + 2, by + 2, fill_w, bar_h - 4, 0, 230, 150, 255)
            # Text % inside modal
            prog_pct_txt = f"{fill_pct}%"
            engine.draw_text(prog_pct_txt, engine.font_item, ox + overlay_w - 75, oy + 124, 0, 230, 150, center_x=True, center_y=True)
        else:
            pulse_w = int((math.sin(time.time() * 4) * 0.5 + 0.5) * (bar_w - 40)) + 40
            engine.fill_rect(bx + 2, by + 2, pulse_w, bar_h - 4, 0, 230, 255, 255)

        # Bottom notice
        notice = "Vui lòng giữ kết nối Wi-Fi và không tắt nguồn..." if state.current_lang == "VI" else "Please wait and do not turn off device..."
        engine.draw_text(notice, engine.font_badge, ox + overlay_w // 2, oy + 225, 140, 160, 195, center_x=True, center_y=True)
