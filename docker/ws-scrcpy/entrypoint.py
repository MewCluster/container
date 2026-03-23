#!/usr/bin/env python3
import os
import subprocess
import threading
import requests
import time
import signal
import sys

WAIT_LIMIT = int(os.environ.get("WAIT_LIMIT", "120"))
ADB_PORT = int(os.environ.get("ADB_PORT", "5555"))
RETRY_COUNT = int(os.environ.get("RETRY_COUNT", "3"))
MONITOR_INTERVAL = int(os.environ.get("MONITOR_INTERVAL", "10"))
NODE_ENTRY = os.environ.get("NODE_ENTRY", "dist/index.js")
RESTART_DELAY = int(os.environ.get("RESTART_DELAY", "1"))

K8S_LABEL = os.environ.get("K8S_LABEL", "app.kubernetes.io/name=android")
ANDROID_IPS = os.environ.get("ANDROID_IPS", "")

K8S_TOKEN_PATH = "/var/run/secrets/kubernetes.io/serviceaccount/token"
K8S_CACERT = "/var/run/secrets/kubernetes.io/serviceaccount/ca.crt"
K8S_NS_PATH = "/var/run/secrets/kubernetes.io/serviceaccount/namespace"
K8S_API = os.environ.get("K8S_API", "https://kubernetes.default.svc")

IS_K8S = os.path.exists(K8S_TOKEN_PATH)
print(f"运行模式: {'k8s' if IS_K8S else 'docker'}")
print(
    f"配置: WAIT_LIMIT={WAIT_LIMIT}s MONITOR_INTERVAL={MONITOR_INTERVAL}s "
    f"ADB_PORT={ADB_PORT} RETRY_COUNT={RETRY_COUNT} NODE_ENTRY={NODE_ENTRY}"
)

if IS_K8S:
    TOKEN = open(K8S_TOKEN_PATH).read().strip()
    NAMESPACE = open(K8S_NS_PATH).read().strip()

node_proc: subprocess.Popen | None = None
stop_event = threading.Event()


def cleanup(signum=None, frame=None):
    print("收到退出信号，清理中...")
    stop_event.set()
    if node_proc and node_proc.poll() is None:
        node_proc.terminate()
    subprocess.run(["adb", "kill-server"], capture_output=True)
    sys.exit(0)


signal.signal(signal.SIGINT, cleanup)
signal.signal(signal.SIGTERM, cleanup)


def get_pods() -> list[str]:
    if IS_K8S:
        try:
            resp = requests.get(
                f"{K8S_API}/api/v1/namespaces/{NAMESPACE}/pods",
                params={"labelSelector": K8S_LABEL},
                headers={"Authorization": f"Bearer {TOKEN}"},
                verify=K8S_CACERT,
                timeout=5,
            )
            resp.raise_for_status()
            items = resp.json().get("items", [])
            return [
                item["status"]["podIP"]
                for item in items
                if item.get("status", {}).get("phase") == "Running"
                and item.get("metadata", {}).get("deletionTimestamp") is None
                and item.get("status", {}).get("podIP")
            ]
        except Exception as e:
            print(f"警告: get_pods 失败: {e}")
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


def sync_devices(new_ips: list[str]) -> bool:
    """同步设备，返回是否有设备减少"""
    new_set = set(new_ips)
    curr_set = connected_ips()

    for ip in curr_set - new_set:
        print(f"断开已消失的设备: {ip}")
        adb("disconnect", f"{ip}:{ADB_PORT}")

    for ip in new_set - curr_set:
        if is_ready(ip):
            print(f"新设备已就绪: {ip}")
        else:
            print(f"警告: {ip} 连接失败，跳过")

    lost = curr_set - new_set
    return bool(lost)


def monitor():
    global node_proc
    while not stop_event.is_set():
        stop_event.wait(MONITOR_INTERVAL)
        if stop_event.is_set():
            break

        new_pods = get_pods()
        if not new_pods:
            print("警告: 无 Running Pod，跳过本轮")
            continue

        if set(new_pods) != connected_ips():
            print("检测到设备变更，重新同步...")
            has_lost = sync_devices(new_pods)
            if has_lost and node_proc and node_proc.poll() is None:
                print("设备减少，重启 ws-scrcpy...")
                node_proc.terminate()


subprocess.run(["adb", "kill-server"], capture_output=True)
subprocess.run(["adb", "start-server"], capture_output=True)

print(f"等待 Android 设备就绪（最多 {WAIT_LIMIT} 秒）...")
waited = 0
while True:
    if waited >= WAIT_LIMIT:
        print(f"等待超时（{WAIT_LIMIT}s），退出")
        sys.exit(1)
    pods = get_pods()
    if any(is_ready(ip) for ip in pods):
        print("至少一个设备已就绪")
        break
    print(f"等待中，2 秒后重试...（已等待 {waited}s）")
    time.sleep(2)
    waited += 2

threading.Thread(target=monitor, daemon=True).start()

print("所有设备已就绪，启动 ws-scrcpy")
while not stop_event.is_set():
    node_proc = subprocess.Popen(["node", NODE_ENTRY])
    node_proc.wait()
    if stop_event.is_set():
        break
    print(f"ws-scrcpy 退出，{RESTART_DELAY} 秒后重启...")
    time.sleep(RESTART_DELAY)
