# -*- coding: utf-8 -*-
"""Chinh sach boxart: URL nao la bia that, URL nao chi la anh "chua co bia".

Nha cung cap khong tra 404 khi thieu bia - ho tra 200 kem mot anh placeholder.
Kho catalogue vi the co 23.931 dong tro vao no-image.png cua retrostic (may anh
gach cheo 245x165, 8 KB) va 20 dong placeholder cua gametuoitho. Tai chung ve la
tai ve mot anh 404, ghi len the, roi ve de len tile avatar tu ve cua RetroHub -
cai tile it ra con cho biet ten game va he may.
"""

import json
import os
import time

from .paths import SDCARD_PATH

# Khop theo ten file cuoi duong dan, khong khop chuoi con: retrostic co mot bia
# that ten "better-default-text-boxes.png" (ban hack sua khung thoai), va khop
# chuoi con "default" se giet nham no.
PLACEHOLDER_BASENAMES = frozenset((
    "no-image.png",      # retrostic, 23.931 dong
    "placeholder.png",   # gametuoitho
    "placeholder.svg",   # gametuoitho
    "default.jpg",       # dieu kien cu trong app.py, giu lai
))

# Cache "game nay da do roi, khong co bia": mot lan do het chuoi (catalog URL ->
# danh sach Libretro -> Bing) ton 10-40s, va man chi tiet mo lai tung lan thi lan
# nao cung tra lai gia do. Ghi tren the chu khong phai /tmp, vi /tmp la RAM: reboot
# mot cai la mat, va nguoi dung lai cho lai tu dau.
NO_ART_TTL_S = 7 * 86400
NO_ART_MAX = 400

_cache = None

def _cache_file():
    return os.path.join(SDCARD_PATH, ".retrohub", "cache", "boxart_miss.json")

def _key(sys_code, filename):
    """Khoa theo ten file cuoi cung: catalogue co dong ghi ca duong dan
    ("category/Game/x.jar") trong khi cho khac chi co ten file."""
    name = os.path.basename(str(filename or "").replace("\\", "/")).strip().lower()
    if not name:
        return None
    return "%s|%s" % (str(sys_code or "").upper(), name)

def _load():
    global _cache
    if _cache is None:
        data = {}
        try:
            with open(_cache_file(), "r", encoding="utf-8") as f:
                raw = json.load(f)
            if isinstance(raw, dict):
                data = {str(k): float(v) for k, v in raw.items()
                        if isinstance(v, (int, float))}
        except Exception:
            data = {}
        _cache = data
    return _cache

def _save(data):
    path = _cache_file()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(tmp, path)
    except Exception:
        pass

def clear_no_art_cache():
    """Quen ban trong RAM (test, hoac sau khi file bi thay tu ngoai)."""
    global _cache
    _cache = None

def no_art_count():
    return len(_load())

def no_art_known(sys_code, filename, now=None):
    """Da biet chac game nay khong co bia chua (con trong han TTL)."""
    key = _key(sys_code, filename)
    if not key:
        return False
    ts = _load().get(key)
    if not ts:
        return False
    return (now if now is not None else time.time()) - ts < NO_ART_TTL_S

def remember_no_art(sys_code, filename, now=None):
    """Ghi nho mot lan do khong ra bia. Tra ve True khi ghi duoc."""
    key = _key(sys_code, filename)
    if not key:
        return False
    ts = now if now is not None else time.time()
    fresh = {k: v for k, v in _load().items() if ts - v < NO_ART_TTL_S}
    fresh[key] = ts
    kept = dict(sorted(fresh.items(), key=lambda kv: kv[1], reverse=True)[:NO_ART_MAX])
    global _cache
    _cache = kept
    _save(kept)
    return True

def forget_no_art(sys_code, filename):
    """Xoa ghi nho cu khi bia da co that (do bang duong khac chang han)."""
    key = _key(sys_code, filename)
    cache = _load()
    if key in cache:
        cache.pop(key, None)
        _save(cache)

def is_real_boxart_url(url):
    """True khi url dang tro toi mot tam bia that, dang tai duoc."""
    if not url:
        return False
    url = str(url).strip()
    if not url or url == "null" or not url.lower().startswith("http"):
        return False
    # Bo query va fragment truoc khi lay ten file: "no-image.png?v=2" van la
    # placeholder.
    path = url.split("#", 1)[0].split("?", 1)[0]
    return path.rsplit("/", 1)[-1].lower() not in PLACEHOLDER_BASENAMES
