"""vue-notes keep-alive: keep all 8 uWSGI workers' notes_oracle connections warm.

Every run mints a fresh JWT (in-process, never logged) and GETs
/api/note-types/ 16 times through the public API. uWSGI distributes the
sequential requests across workers, so each worker's notes_oracle
connection (CONN_MAX_AGE 1800s) and its LocMemCache note-types entry get
touched at least once per run. Cron runs this every 10 minutes, so no
worker connection ever idles past ~10 minutes and the user's first click
after a long idle stays fast.

Usage (cron):
*/10 * * * * /home/opc/vueStockapi/.venv/bin/python /home/opc/vueStockapi/keepalive_notes.py >> /home/opc/vueStockapi/keepalive_notes.log 2>&1
"""

import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.request

for _ca in ("/etc/pki/tls/certs/ca-bundle.crt", "/etc/ssl/certs/ca-certificates.crt"):
    if os.path.exists(_ca):
        CTX = ssl.create_default_context(cafile=_ca)
        break
else:
    CTX = ssl.create_default_context()

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "vueStockapi.settings")
sys.path.insert(0, "/home/opc/vueStockapi")

import django  # noqa: E402

django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from rest_framework_simplejwt.tokens import RefreshToken  # noqa: E402

BASE = "https://api.huabenwuxin.com"
# 24 路并发：必须超过 worker 总并发槽（4 worker × 2 线程 = 8），才能逼内核
# 把请求分给每一个 worker；顺序请求或刚好 16 路会被内核反复交给同一个热 worker。
N = 24
UA = "vue-notes-keepalive/1.0"


def _one(i, token):
    req = urllib.request.Request(BASE + "/api/note-types/", method="GET")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("User-Agent", UA)
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=30, context=CTX) as resp:
            body = json.loads(resp.read() or b"[]")
            dt = time.perf_counter() - t0
            return resp.status == 200 and isinstance(body, list) and len(body) >= 1, dt
    except Exception as e:  # noqa: BLE001 - keep-alive must not crash the cron
        print(f"keepalive request failed: {type(e).__name__}", file=sys.stderr)
        return False, time.perf_counter() - t0


def main():
    user = get_user_model().objects.filter(username="huabenwuxin").first()
    if user is None:
        user = get_user_model().objects.filter(is_superuser=True).first()
    assert user, "no user to mint token for"
    token = str(RefreshToken.for_user(user).access_token)

    # 16 路并发同时发：uWSGI 的共享 socket 由内核分发，顺序请求会被内核
    # 反复交给同一个刚用过的 worker，只有并发才能一次唤醒全部 8 个 worker。
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=N) as ex:
        results = list(ex.map(lambda i: _one(i, token), range(N)))
    ok = sum(1 for good, _ in results if good)
    times = sorted(dt for _, dt in results)
    med = times[len(times) // 2] if times else -1
    print(
        f"{time.strftime('%Y-%m-%d %H:%M:%S')} keepalive ok={ok}/{N} "
        f"min={times[0]:.2f}s med={med:.2f}s max={times[-1]:.2f}s",
        flush=True,
    )
    return 0 if ok == N else 1


if __name__ == "__main__":
    raise SystemExit(main())
