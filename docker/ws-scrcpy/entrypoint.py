#!/usr/bin/env python3
import os
import subprocess
import threading
import time
import signal
import sys
import json
import logging
import urllib.request
import urllib.parse
import ssl
from http.server import HTTPServer, BaseHTTPRequestHandler
from concurrent.futures import ThreadPoolExecutor, as_completed


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(
            {
                "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
                "level": record.levelname,
                "msg": record.getMessage(),
            },
            ensure_ascii=False,
        )


_handler = logging.StreamHandler()
_handler.setFormatter(JsonFormatter())
logging.basicConfig(handlers=[_handler], level=logging.INFO)
log = logging.getLogger("entrypoint")

WAIT_LIMIT = int(os.environ.get("WAIT_LIMIT", "120"))
ADB_PORT = int(os.environ.get("ADB_PORT", "5555"))
RETRY_COUNT = int(os.environ.get("RETRY_COUNT", "3"))
MONITOR_INTERVAL = int(os.environ.get("MONITOR_INTERVAL", "10"))
NODE_ENTRY = os.environ.get("NODE_ENTRY", "dist/index.js")
RESTART_DELAY = int(os.environ.get("RESTART_DELAY", "1"))
HEALTH_PORT = int(os.environ.get("HEALTH_PORT", "18000"))

K8S_LABEL = os.environ.get("K8S_LABEL", "app.kubernetes.io/name=android")
K8S_API = os.environ.get("K8S_API", "https://kubernetes.default.svc")

K8S_TOKEN_PATH = "/var/run/secrets/kubernetes.io/serviceaccount/token"
K8S_CACERT = "/var/run/secrets/kubernetes.io/serviceaccount/ca.crt"
K8S_NS_PATH = "/var/run/secrets/kubernetes.io/serviceaccount/namespace"

IS_K8S = os.path.exists(K8S_TOKEN_PATH)

log.info(f"运行模式: {'k8s' if IS_K8S else 'docker'}")
log.info(
    f"配置: WAIT_LIMIT={WAIT_LIMIT}s MONITOR_INTERVAL={MONITOR_INTERVAL}s "
    f"ADB_PORT={ADB_PORT} RETRY_COUNT={RETRY_COUNT} "
    f"NODE_ENTRY={NODE_ENTRY} HEALTH_PORT={HEALTH_PORT}"
)

if IS_K8S:
    TOKEN = open(K8S_TOKEN_PATH).read().strip()
    NAMESPACE = open(K8S_NS_PATH).read().strip()

node_proc: subprocess.Popen | None = None
stop_event = threading.Event()
restarting = threading.Event()


def cleanup(signum=None, frame=None):
    log.info("收到退出信号，清理中...")
    stop_event.set()
    if node_proc and node_proc.poll() is None:
        node_proc.terminate()
    subprocess.run(["adb", "kill-server"], capture_output=True)
    sys.exit(0)


signal.signal(signal.SIGINT, cleanup)
signal.signal(signal.SIGTERM, cleanup)


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/healthz":
            self._respond(200, "ok")
        elif self.path == "/readyz":
            node_ok = node_proc is not None and node_proc.poll() is None
            device_ok = bool(connected_ips())
            if node_ok and device_ok:
                self._respond(200, "ready")
            elif restarting.is_set():
                self._respond(503, "restarting")
            else:
                self._respond(503, f"node_ok={node_ok} device_ok={device_ok}")
        else:
            self._respond(404, "not found")

    def _respond(self, code: int, body: str):
        data = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format, *args):
        pass


threading.Thread(
    target=lambda: HTTPServer(("", HEALTH_PORT), HealthHandler).serve_forever(),
    daemon=True,
).start()
log.info(f"健康检查服务启动: :{HEALTH_PORT} /healthz /readyz")


def get_pods() -> list[str]:
    if IS_K8S:
        try:
            ctx = ssl.create_default_context(cafile=K8S_CACERT)
            url = (
                f"{K8S_API}/api/v1/namespaces/{NAMESPACE}/pods"
                f"?labelSelector={urllib.parse.quote(K8S_LABEL)}"
            )
            req = urllib.request.Request(
                url, headers={"Authorization": f"Bearer {TOKEN}"}
            )
            with urllib.request.urlopen(req, context=ctx, timeout=5) as resp:
                items = json.loads(resp.read()).get("items", [])
            return [
                item["status"]["podIP"]
                for item in items
                if item.get("status", {}).get("phase") == "Running"
                and item.get("metadata", {}).get("deletionTimestamp") is None
                and item.get("status", {}).get("podIP")
            ]
        except Exception as e:
            log.warning(f"get_pods 失败: {e}")
            return []
    else:
        raw = os.environ.get("ANDROID_IPS", "")
        return [ip.strip() for ip in raw.split(",") if ip.strip()]


def adb(*args, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(["adb", *args], capture_output=True, text=True, **kwargs)


def connected_ips() -> set[str]:
    result = adb("devices")
    ips = set()
    for line in result.stdout.splitlines():
        if f":{ADB_PORT}" in line and "offline" not in line:
            ips.add(line.split(":")[0])
    return ips


def is_ready(ip: str) -> bool:
    adb("connect", f"{ip}:{ADB_PORT}")
    for _ in range(RETRY_COUNT):
        result = adb("-s", f"{ip}:{ADB_PORT}", "shell", "echo", "ok")
        if "ok" in result.stdout:
            return True
        time.sleep(1)
    return False


def wait_for_any_device(pods: list[str]) -> bool:
    if not pods:
        return False
    with ThreadPoolExecutor(max_workers=len(pods)) as ex:
        futures = {ex.submit(is_ready, ip): ip for ip in pods}
        for future in as_completed(futures):
            ip = futures[future]
            try:
                if future.result():
                    log.info(f"设备已就绪: {ip}")
                    return True
            except Exception as e:
                log.warning(f"探测 {ip} 异常: {e}")
    return False


def sync_devices(new_ips: list[str]) -> bool:
    new_set = set(new_ips)
    curr_set = connected_ips()

    for ip in curr_set - new_set:
        log.info(f"断开已消失的设备: {ip}")
        adb("disconnect", f"{ip}:{ADB_PORT}")

    added = new_set - curr_set
    if added:
        with ThreadPoolExecutor(max_workers=len(added)) as ex:
            futures = {ex.submit(is_ready, ip): ip for ip in added}
            for future in as_completed(futures):
                ip = futures[future]
                try:
                    if future.result():
                        log.info(f"新设备已就绪: {ip}")
                    else:
                        log.warning(f"{ip} 连接失败，跳过")
                except Exception as e:
                    log.warning(f"连接 {ip} 异常: {e}")

    return bool(curr_set - new_set)


def monitor():
    global node_proc
    while not stop_event.is_set():
        stop_event.wait(MONITOR_INTERVAL)
        if stop_event.is_set():
            break

        new_pods = get_pods()

        if set(new_pods) != connected_ips():
            log.info("检测到设备变更，重新同步...")
            has_lost = sync_devices(new_pods)
            if has_lost and node_proc and node_proc.poll() is None:
                log.info("设备减少，触发 ws-scrcpy 重启")
                restarting.set()
                node_proc.terminate()


subprocess.run(["adb", "kill-server"], capture_output=True)
subprocess.run(["adb", "start-server"], capture_output=True)

log.info(f"等待 Android 设备就绪（最多 {WAIT_LIMIT} 秒）...")
waited = 0
while True:
    if waited >= WAIT_LIMIT:
        log.error(f"等待超时（{WAIT_LIMIT}s），退出")
        sys.exit(1)
    pods = get_pods()
    if wait_for_any_device(pods):
        log.info("至少一个设备已就绪，继续启动")
        break
    log.info(f"等待中，2 秒后重试...（已等待 {waited}s）")
    time.sleep(2)
    waited += 2

threading.Thread(target=monitor, daemon=True).start()

log.info("启动 ws-scrcpy")
while not stop_event.is_set():
    node_proc = subprocess.Popen(["node", NODE_ENTRY])
    restarting.clear()
    node_proc.wait()
    if stop_event.is_set():
        break
    log.info(f"ws-scrcpy 退出，{RESTART_DELAY} 秒后重启...")
    time.sleep(RESTART_DELAY)
