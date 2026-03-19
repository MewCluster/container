#!/bin/bash
set -e

API="https://kubernetes.default.svc"
TOKEN=$(cat /var/run/secrets/kubernetes.io/serviceaccount/token)
CACERT="/var/run/secrets/kubernetes.io/serviceaccount/ca.crt"
NAMESPACE=$(cat /var/run/secrets/kubernetes.io/serviceaccount/namespace)
LABEL="app.kubernetes.io%2Fname=redroid"

NODE_PID=""
MONITOR_PID=""
NODE_PID_FILE="/tmp/ws_scrcpy_node.pid"
WAIT_LIMIT=120

# ──────────────────────────────────────────────
# 退出时清理所有子进程
# ──────────────────────────────────────────────
cleanup() {
    trap - INT TERM EXIT
    echo "收到退出信号，清理中..."
    [ -n "$MONITOR_PID" ] && kill "$MONITOR_PID" 2>/dev/null || true
    [ -n "$NODE_PID" ]    && kill "$NODE_PID"    2>/dev/null || true
    rm -f "$NODE_PID_FILE"
    adb kill-server 2>/dev/null || true
    exit 0
}
trap cleanup INT TERM EXIT

# ──────────────────────────────────────────────
# 从 K8s API 获取运行中且未被删除的 Pod IP 列表
# ──────────────────────────────────────────────
get_pods() {
    curl -s --max-time 5 --cacert "$CACERT" \
        -H "Authorization: Bearer $TOKEN" \
        "$API/api/v1/namespaces/$NAMESPACE/pods?labelSelector=$LABEL" \
        | jq -r '.items[]
			| select(.status.phase=="Running")
			| select(.metadata.deletionTimestamp == null)
			| .status.podIP // empty'
}

# ──────────────────────────────────────────────
# 检测单个 IP 的 adb 是否就绪（带超时重试）
# ──────────────────────────────────────────────
is_ready() {
    local _ip="$1"
    adb connect "$_ip:5555" >/dev/null 2>&1
    local _tries=0
    while [ "$_tries" -lt 3 ]; do
        if adb -s "$_ip:5555" shell echo ok 2>/dev/null | grep -q ok; then
            return 0
        fi
        _tries=$((_tries + 1))
        sleep 1
    done
    return 1
}

# ──────────────────────────────────────────────
# 重新同步：断开旧连接，连接并验证所有新 Pod
# ──────────────────────────────────────────────
sync_devices() {
    local _new_pods="$1"

    for _dev in $(adb devices | grep '5555' | awk '{print $1}'); do
        local _ip
        _ip=$(echo "$_dev" | cut -d: -f1)
        if ! echo "$_new_pods" | grep -q "$_ip"; then
            echo "断开已消失的设备: $_ip"
            adb disconnect "$_dev" >/dev/null 2>&1 || true
        fi
    done

    local IFS=$'\n'
    for _ip in $_new_pods; do
        if ! adb devices | grep -q "$_ip:5555"; then
            if is_ready "$_ip"; then
                echo "新设备已就绪: $_ip"
            else
                echo "警告: $_ip 连接失败，跳过"
            fi
        fi
    done
}

# ──────────────────────────────────────────────
# 后台监控：Pod IP 变化时重新同步，设备减少时重启 node
# ──────────────────────────────────────────────
monitor() {
    set +e
    while true; do
        sleep 10

        NEW_PODS=$(get_pods 2>/dev/null)
        if [ $? -ne 0 ] || [ -z "$NEW_PODS" ]; then
            echo "警告: get_pods 失败或无 Running Pod，跳过本轮"
            continue
        fi

        CURRENT_IPS=$(adb devices | grep '5555' | awk '{print $1}' | cut -d: -f1 | sort | grep -v '^$' || true)
        EXPECTED_IPS=$(echo "$NEW_PODS" | sort | grep -v '^$')

        if [ "$CURRENT_IPS" != "$EXPECTED_IPS" ]; then
            echo "检测到设备变更，重新同步..."
            sync_devices "$NEW_PODS"

            LOST=$(comm -23 <(echo "$CURRENT_IPS") <(echo "$EXPECTED_IPS"))
            if [ -n "$LOST" ]; then
                echo "设备减少: $LOST，重启 ws-scrcpy..."
                local _pid
                _pid=$(cat "$NODE_PID_FILE" 2>/dev/null)
                if [ -n "$_pid" ] && kill -0 "$_pid" 2>/dev/null; then
                    kill "$_pid" 2>/dev/null || true
                fi
            fi
        fi
    done
}

# ──────────────────────────────────────────────
# 主流程
# ──────────────────────────────────────────────
adb kill-server 2>/dev/null || true
adb start-server

echo "等待 redroid 设备就绪（最多 ${WAIT_LIMIT} 秒）..."
WAITED=0
while true; do
    if [ "$WAITED" -ge "$WAIT_LIMIT" ]; then
        echo "等待超时（${WAIT_LIMIT}s），退出"
        exit 1
    fi
    PODS=$(get_pods 2>/dev/null) || PODS=""
    if [ -n "$PODS" ]; then
        FOUND=""
        OLD_IFS="$IFS"        # 保存原 IFS
        IFS=$'\n'
        for ip in $PODS; do
            if is_ready "$ip"; then
                echo "$ip 已就绪"
                FOUND="$ip"
            fi
        done
        IFS="$OLD_IFS"        # 恢复原 IFS
        [ -n "$FOUND" ] && break
    fi
    echo "等待中，2 秒后重试...（已等待 ${WAITED}s）"
    sleep 2
    WAITED=$((WAITED + 2))
done

monitor &
MONITOR_PID=$!

echo "所有设备已就绪，启动 ws-scrcpy"
while true; do
    node dist/index.js &
    NODE_PID=$!
    echo "$NODE_PID" > "$NODE_PID_FILE"
    wait "$NODE_PID" || true
    NODE_PID=""
    echo "ws-scrcpy 退出，1 秒后重启..."
    sleep 1
done