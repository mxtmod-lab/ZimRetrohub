# -*- coding: utf-8 -*-
"""App Store & Package Manager for TrimUI RetroHub.

Quan ly danh muc ung dung tien ich (Apps), kiem tra trang thai cai dat,
tai ve goi .tar.gz, giai nen vao SDCARD/Apps, phan quyen thuc thi va go cai dat.
"""

import os
import json
import ssl
import shutil
import stat
import subprocess
import tarfile
import urllib.request

from . import paths
from .storage import unlock

ONLINE_CDN_BASE = "https://cdn.xuanhoa493.com/"
GITHUB_RAW_BASE = "https://github.com/nguyenxuanhoa493/repohubtool/releases/download/assets/"
ASSET_BASE = ONLINE_CDN_BASE


def get_apps_catalog():
    """Doc catalog ung dung tu file apps_catalog.json."""
    catalog_path = paths.APPS_CATALOG_FILE
    if not os.path.isfile(catalog_path):
        # Fallback neu dang chay o thu muc goc dev
        alt_path = os.path.join(os.path.dirname(paths.APP_DIR), "catalog", "apps_catalog.json")
        if os.path.isfile(alt_path):
            catalog_path = alt_path

    if os.path.isfile(catalog_path):
        try:
            with open(catalog_path, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
                if isinstance(data, dict) and "apps" in data:
                    return data["apps"]
                if isinstance(data, list):
                    return data
        except Exception as e:
            print(f"[AppStore] Loi doc catalog: {e}")
    return []


def get_apps_status():
    """Lay danh sach ung dung kem trang thai cai dat thuc te tren the nho."""
    catalog = get_apps_catalog()
    installed_apps = set()

    if os.path.isdir(paths.APPS_DIR):
        try:
            for d in os.listdir(paths.APPS_DIR):
                full_p = os.path.join(paths.APPS_DIR, d)
                if os.path.isdir(full_p) and not d.startswith(".") and not d.startswith("_"):
                    # Co config.json hoac launch.sh duoc coi la hop le
                    if os.path.isfile(os.path.join(full_p, "config.json")) or os.path.isfile(os.path.join(full_p, "launch.sh")):
                        installed_apps.add(d)
        except OSError:
            pass

    results = []
    for item in catalog:
        app_id = item.get("id")
        app_path = os.path.join(paths.APPS_DIR, app_id)
        is_installed = app_id in installed_apps or os.path.isdir(app_path)
        if not is_installed and app_id == "RetroArch":
            boot_ra = os.path.join(paths.APPS_DIR, "BootRetroArch")
            if "BootRetroArch" in installed_apps or os.path.isdir(boot_ra):
                is_installed = True
                app_path = boot_ra

        cfg = {}
        if is_installed:
            cfg_file = os.path.join(app_path, "config.json")
            if os.path.isfile(cfg_file):
                try:
                    with open(cfg_file, "r", encoding="utf-8-sig") as f:
                        cfg = json.load(f)
                except Exception:
                    pass

        # Icon preview local trong repo/app assets
        icon_preview = ""
        cand_icons = [
            os.path.join(paths.APP_DIR, "assets", "apps_preview", f"{app_id}.png"),
            os.path.join(app_path, "commander.png"),
            os.path.join(app_path, "icon.png"),
        ]
        for c in cand_icons:
            if os.path.isfile(c):
                icon_preview = c
                break

        entry = dict(item)
        entry["installed"] = is_installed
        entry["installed_path"] = app_path if is_installed else ""
        entry["local_label"] = cfg.get("label", item.get("name", app_id))
        entry["icon_preview_local"] = icon_preview
        results.append(entry)

    return results


def _find_local_package(app_id):
    """Tim goi package .tar.gz co san tai may khong can mang."""
    tar_name = f"{app_id}.tar.gz"
    search_dirs = [
        paths.LOCAL_APPS_PACKAGES_DIR,
        os.path.join(paths.APP_DIR, "apps"),
        os.path.join(os.path.dirname(paths.APP_DIR), "apps"),
        os.path.join(paths.SDCARD_PATH, "apps"),
        os.path.join(paths.SDCARD_PATH, "Apps_repo"),
    ]
    for sdir in search_dirs:
        if sdir and os.path.isdir(sdir):
            candidate = os.path.join(sdir, tar_name)
            if os.path.isfile(candidate):
                return candidate
    return None


def download_package(app_id, target_file, on_progress=None, version=""):
    """Tai goi cai dat ung dung tu Cloudflare R2 hoac GitHub Releases."""
    tar_name = f"{app_id}.tar.gz"
    v_param = f"?v={version}" if version else "?v=2"
    urls = [
        f"{ONLINE_CDN_BASE}apps/{tar_name}{v_param}",
        f"{ONLINE_CDN_BASE}apps/{tar_name}",
        f"{GITHUB_RAW_BASE}{tar_name}",
    ]

    # SSL context permissive cho thiet bi TrimUI
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    last_error = None
    for url in urls:
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (TrimUI; RetroHub AppStore)"}
            )
            with urllib.request.urlopen(req, context=ctx, timeout=20) as resp:
                if resp.status != 200:
                    continue
                total_size = resp.headers.get("Content-Length")
                total_size = int(total_size) if total_size and total_size.isdigit() else 0

                downloaded = 0
                os.makedirs(os.path.dirname(target_file), exist_ok=True)
                with open(target_file, "wb") as out_f:
                    while True:
                        chunk = resp.read(65536)
                        if not chunk:
                            break
                        out_f.write(chunk)
                        downloaded += len(chunk)
                        if on_progress and total_size > 0:
                            on_progress(downloaded, total_size)
                return True, "OK"
        except Exception as e:
            last_error = str(e)
            if os.path.exists(target_file):
                try:
                    os.remove(target_file)
                except OSError:
                    pass

    return False, last_error or "Download failed"


def install_app(app_id, on_progress=None, on_status=None):
    """Cai dat ung dung vao SDCARD/Apps/<app_id>."""
    try:
        os.makedirs(paths.APPS_DIR, exist_ok=True)
    except OSError as e:
        return False, f"Khong the tao thu muc Apps: {e}"

    local_tar = _find_local_package(app_id)
    temp_tar = None

    if local_tar:
        tar_path = local_tar
        if on_status:
            on_status("installing")
    else:
        if on_status:
            on_status("downloading")
        temp_tar = os.path.join(paths.APPS_DIR, f".tmp_{app_id}.tar.gz")
        catalog = get_apps_catalog()
        app_meta = next((item for item in catalog if item.get("id") == app_id), {})
        ver = app_meta.get("version", "")
        ok, msg = download_package(app_id, temp_tar, on_progress, version=ver)
        if not ok:
            return False, f"Tai ve that bai: {msg}"
        tar_path = temp_tar
        if on_status:
            on_status("installing")

    # Giai nen an toan vao SDCARD/Apps
    try:
        target_dir = os.path.join(paths.APPS_DIR, app_id)
        if os.path.exists(target_dir):
            unlock(target_dir)

        with tarfile.open(tar_path, "r:gz") as tar:
            # Kiem tra path traversal truoc khi extract
            dest_abs = os.path.abspath(paths.APPS_DIR)
            for member in tar.getmembers():
                member_path = os.path.abspath(os.path.join(paths.APPS_DIR, member.name))
                if not member_path.startswith(dest_abs):
                    return False, f"Phat hien duong dan nguy hiem trong goi: {member.name}"

            if hasattr(tarfile, "data_filter"):
                tar.extractall(path=paths.APPS_DIR, filter="data")
            else:
                tar.extractall(path=paths.APPS_DIR)

        # Phan quyen thuc thi cho launch.sh va binary trong thu muc app
        if os.path.isdir(target_dir):
            for root, _, files in os.walk(target_dir):
                for f in files:
                    fp = os.path.join(root, f)
                    if f.endswith(".sh") or "." not in f:
                        try:
                            st = os.stat(fp)
                            os.chmod(fp, st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
                        except OSError:
                            pass

        # Dong bo icon vao SDCARD/Icons/Default/Apps/ de giao dien TrimUI Stock nhan
        stock_icons_dir = os.path.join(paths.SDCARD_PATH, "Icons", "Default", "Apps")
        try:
            os.makedirs(stock_icons_dir, exist_ok=True)
            icon_candidates = [
                os.path.join(paths.APP_DIR, "assets", "apps_preview", f"{app_id}.png"),
                os.path.join(target_dir, "commander.png"),
                os.path.join(target_dir, "icon.png"),
            ]
            for ic in icon_candidates:
                if os.path.isfile(ic):
                    dst_ic = os.path.join(stock_icons_dir, f"{app_id}.png")
                    if not os.path.exists(dst_ic):
                        shutil.copy2(ic, dst_ic)
                    break
        except Exception:
            pass

        # Voi rieng RetroArch: dong bo ngay cores, autoconfig va binary sang SDCARD/RetroArch/
        # de cac launcher he may trong Emus/*/launch.sh co the dung ngay ma khong can mo app truoc
        if app_id == "RetroArch" and os.path.isdir(target_dir):
            ra_system_dir = os.path.join(paths.SDCARD_PATH, "RetroArch")
            try:
                os.makedirs(os.path.join(ra_system_dir, ".retroarch"), exist_ok=True)
                for item in ["ra64.trimui", "retroarch.cfg"]:
                    src_f = os.path.join(target_dir, item)
                    dst_f = os.path.join(ra_system_dir, item)
                    if os.path.isfile(src_f) and not os.path.exists(dst_f):
                        shutil.copy2(src_f, dst_f)

                app_dot_ra = os.path.join(target_dir, ".retroarch")
                sys_dot_ra = os.path.join(ra_system_dir, ".retroarch")
                if os.path.isdir(app_dot_ra):
                    for sub in ["autoconfig", "cores", "system", "filters", "config", "overlay"]:
                        sub_src = os.path.join(app_dot_ra, sub)
                        sub_dst = os.path.join(sys_dot_ra, sub)
                        if os.path.isdir(sub_src):
                            os.makedirs(sub_dst, exist_ok=True)
                            for root, _, files in os.walk(sub_src):
                                rel = os.path.relpath(root, sub_src)
                                cur_dst = os.path.join(sub_dst, rel) if rel != "." else sub_dst
                                os.makedirs(cur_dst, exist_ok=True)
                                for f in files:
                                    sf = os.path.join(root, f)
                                    df = os.path.join(cur_dst, f)
                                    if not os.path.exists(df):
                                        shutil.copy2(sf, df)

                ra_bin = os.path.join(ra_system_dir, "ra64.trimui")
                if os.path.isfile(ra_bin):
                    try:
                        st = os.stat(ra_bin)
                        os.chmod(ra_bin, st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
                    except OSError:
                        pass
            except Exception as e:
                print(f"[AppStore] Sync RetroArch system error: {e}")

        # Voi rieng PortMaster: dam bao tuong thich ca TrimUI Stock OS lan CrossMix OS
        if app_id == "PortMaster" and os.path.isdir(target_dir):
            _patch_portmaster_environment(target_dir)

        try:
            os.sync()
        except (AttributeError, OSError):
            pass

        return True, "Cai dat thanh cong"

    except Exception as e:
        return False, f"Loi giai nen: {e}"
    finally:
        if temp_tar and os.path.exists(temp_tar):
            try:
                os.remove(temp_tar)
            except OSError:
                pass


def _patch_portmaster_environment(target_dir):
    """Va loi tuong thich cho PortMaster tren ca TrimUI Stock OS va CrossMix OS."""
    try:
        # 1. Dam bao thu muc du lieu ports va home tren the nho
        data_home = os.path.join(paths.SDCARD_PATH, "Data", "home")
        data_ports = os.path.join(paths.SDCARD_PATH, "Data", "ports")
        os.makedirs(data_home, exist_ok=True)
        os.makedirs(data_ports, exist_ok=True)

        # 2. Chinh sua launch.sh
        launch_file = os.path.join(target_dir, "launch.sh")
        if os.path.isfile(launch_file):
            with open(launch_file, "r", encoding="utf-8") as f:
                content = f.read()

            modified = False

            # Fix loi crash fatal vi thieu ex_config tren Stock OS
            if "source /mnt/SDCARD/System/etc/ex_config" in content and "[ -f /mnt/SDCARD/System/etc/ex_config ]" not in content:
                content = content.replace(
                    "source /mnt/SDCARD/System/etc/ex_config",
                    "[ -f /mnt/SDCARD/System/etc/ex_config ] && source /mnt/SDCARD/System/etc/ex_config"
                )
                modified = True

            # Fix loi pugwash khong tim thay python3 tren Stock OS
            if "py_cand" not in content and "command -v python3" not in content:
                py_patch = (
                    "\n# Ensure python3 is in PATH for Stock OS\n"
                    "if ! command -v python3 >/dev/null 2>&1; then\n"
                    "  for py_cand in \\\n"
                    "    \"/mnt/SDCARD/.retrohub/python/bin\" \\\n"
                    "    \"/mnt/SDCARD/System/bin\" \\\n"
                    "    \"/mnt/SDCARD/Apps/RetroHub/python/bin\"; do\n"
                    "    if [ -x \"$py_cand/python3\" ]; then\n"
                    "      export PATH=\"$py_cand:$PATH\"\n"
                    "      break\n"
                    "    fi\n"
                    "  done\n"
                    "fi\n"
                    "\n"
                    "export PYSDL2_DLL_PATH=\"/usr/trimui/lib:/usr/lib64:/usr/lib\"\n"
                    "export LD_LIBRARY_PATH=\"/usr/trimui/lib:/usr/lib64:/usr/lib:$controlfolder/libs:$LD_LIBRARY_PATH\"\n"
                    "mkdir -p /mnt/SDCARD/Data/home\n"
                    "mkdir -p /mnt/SDCARD/Data/ports\n"
                )
                if "controlfolder=" in content:
                    idx = content.find("controlfolder=")
                    next_nl = content.find("\n", idx)
                    if next_nl != -1:
                        content = content[:next_nl + 1] + py_patch + content[next_nl + 1:]
                        modified = True

            if modified:
                with open(launch_file, "w", encoding="utf-8") as f:
                    f.write(content)

            try:
                st = os.stat(launch_file)
                os.chmod(launch_file, st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            except OSError:
                pass

        # 3. Phan quyen thuc thi cho cac file script va binary quan trong
        pm_sub = os.path.join(target_dir, "PortMaster")
        if os.path.isdir(pm_sub):
            for root, _, files in os.walk(pm_sub):
                for fn in files:
                    if fn.endswith((".sh", ".txt", ".aarch64", ".armhf")) or "." not in fn:
                        fp = os.path.join(root, fn)
                        try:
                            st = os.stat(fp)
                            os.chmod(fp, st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
                        except OSError:
                            pass
    except Exception as e:
        print(f"[AppStore] Patch PortMaster error: {e}")


def uninstall_app(app_id):
    """Go cai dat ung dung khoi SDCARD/Apps/<app_id>."""
    target_dir = os.path.join(paths.APPS_DIR, app_id)
    if not os.path.exists(target_dir):
        return True, "Ung dung chua duoc cai dat"

    try:
        unlock(target_dir)
        shutil.rmtree(target_dir)

        # Xoa icon stock tuong ung neu co
        stock_icon = os.path.join(paths.SDCARD_PATH, "Icons", "Default", "Apps", f"{app_id}.png")
        if os.path.isfile(stock_icon):
            try:
                os.remove(stock_icon)
            except OSError:
                pass

        try:
            os.sync()
        except (AttributeError, OSError):
            pass

        return True, "Go cai dat thanh cong"
    except Exception as e:
        return False, f"Loi khi go bo ung dung: {e}"
