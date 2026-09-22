#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""RetroHub - Premium Retro Gaming Platform & Multi-Source ROM Store for TrimUI Handhelds."""

import os
import sys
import threading

# ------------------------------------------------------------------------------
# Library Paths (PortMaster exlibs, Vendor, and Custom DLLs)
# ------------------------------------------------------------------------------
EXLIBS_PATH = os.path.join(os.environ.get("SDCARD_PATH", "/mnt/SDCARD"), "Apps", "PortMaster", "PortMaster", "exlibs")
if os.path.exists(EXLIBS_PATH):
    sys.path.insert(0, EXLIBS_PATH)

VENDOR_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor")
if os.path.isdir(VENDOR_PATH):
    sys.path.insert(0, VENDOR_PATH)

_VENDOR_LIBS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "libs")
_DEFAULT_DLL_PATHS = f"{_VENDOR_LIBS}:/usr/trimui/lib:/usr/lib64:/usr/lib"
os.environ["PYSDL2_DLL_PATH"] = os.environ.get("PYSDL2_DLL_PATH") or _DEFAULT_DLL_PATHS

# ------------------------------------------------------------------------------
# Core Engine & Subsystem Imports
# ------------------------------------------------------------------------------
from rh.logger import init_logger
from rh.netplay import is_netplay_tunnel_running, stop_netplay_tunnel
from rh.downloader import purge_stale_downloads
from rh.env import auto_check_and_supplement_environment
from rh.engine import RetroHubEngine

# Screen Controllers (HomeScreen is loaded immediately; all other screens load lazily on demand)
from rh.screens.home import HomeScreen


def main():
    """Initialize subsystems, register screens, and start the engine loop."""
    init_logger()

    # Hang cho tai chi song trong RAM, nen file tam con lai tu lan chay truoc la rac
    # (co the ca GB the nho cho mot ban dia game). Don ngay khi khoi dong.
    try:
        purge_stale_downloads()
    except Exception:
        pass

    # Clean up any leftover Netplay tunnel from previous session
    try:
        if is_netplay_tunnel_running() or os.path.exists("/tmp/netplay_info.json"):
            stop_netplay_tunnel()
    except Exception:
        pass

    # Initialize Graphics & Event Engine
    engine = RetroHubEngine()
    engine.init_sdl()
    if not engine.init_fonts():
        sys.exit(1)

    # Register Screens (Immediate Home, Lazy Secondary Screens)
    engine.register_screen("home", HomeScreen(engine))
    engine.register_screen("library", "rh.screens.library", "LibraryScreen")
    engine.register_screen("store", "rh.screens.store", "StoreScreen")
    engine.register_screen("youtube", "rh.screens.youtube", "YoutubeScreen")
    engine.register_screen("watch", "rh.screens.watch", "WatchScreen")
    engine.register_screen("queue", "rh.screens.queue", "QueueScreen")
    engine.register_screen("downloads", "rh.screens.downloads", "DownloadsScreen")
    engine.register_screen("keyboard", "rh.screens.keyboard", "VirtualKeyboardScreen")
    engine.register_screen("network", "rh.screens.network", "NetworkScreen")
    engine.register_screen("settings", "rh.screens.settings", "SettingsScreen")
    engine.register_screen("utilities", "rh.screens.utilities", "UtilitiesScreen")
    engine.register_screen("led", "rh.screens.led", "LedScreen")
    engine.register_screen("splash", "rh.screens.splash", "SplashScreen")
    engine.register_screen("retro_store", "rh.screens.retro_store", "RetroStoreScreen")
    engine.register_screen("theme_store", "rh.screens.theme_store", "ThemeStoreScreen")
    engine.register_screen("icon_store", "rh.screens.icon_store", "IconStoreScreen")
    engine.register_screen("emu_store", "rh.screens.emu_store", "EmuStoreScreen")
    engine.register_screen("app_store", "rh.screens.app_store", "AppStoreScreen")

    # Background silent environment repair (starts after UI is already running, avoiding SD card bus contention)
    def _delayed_env_supplement():
        import time as _t
        _t.sleep(2.5)
        auto_check_and_supplement_environment()

    threading.Thread(target=_delayed_env_supplement, daemon=True).start()

    # Run Main Loop
    engine.run()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        import time
        import traceback
        err_msg = traceback.format_exc()
        sys.stderr.write(f"\n[RetroHub Crash]\n{err_msg}\n")
        try:
            _err_f = os.path.join(os.environ.get("SDCARD_PATH", "/mnt/SDCARD"), "RetroHub-loi.txt")
            with open(_err_f, "a", encoding="utf-8") as _ef:
                _ef.write(f"\n[RetroHub Crash at {time.strftime('%Y-%m-%d %H:%M:%S')}]\n{err_msg}\n")
        except Exception:
            pass
        raise
