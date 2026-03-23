# ws-scrcpy

基于 [NetrisTV/ws-scrcpy](https://github.com/NetrisTV/ws-scrcpy) 构建，集成 ADB 自动发现，推荐使用 [redroid](https://github.com/remote-android/redroid-doc) 作为 Android 容器。

## 功能

- 自动发现并连接 Android Pod（K8s）或静态 IP（Docker）
- 监控设备变化，设备减少时自动重启 ws-scrcpy
- 启动时等待至少一个设备就绪后再启动服务

## 使用

### Kubernetes

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ws-scrcpy
spec:
  template:
    spec:
      containers:
        - name: ws-scrcpy
          image: ghcr.io/mewcluster/ws-scrcpy:latest
          env:
            - name: K8S_LABEL
              value: "app.kubernetes.io/name=android"
```

android Pod 需打上对应 label，entrypoint 会通过 K8s API 自动发现。

### Docker Compose

```yaml
services:
  ws-scrcpy:
    image: ghcr.io/mewcluster/ws-scrcpy:latest
    environment:
      - ANDROID_IPS=192.168.1.10,192.168.1.11
```

## 环境变量

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `ANDROID_IPS` | 空 | Docker 模式下的 android IP，逗号分隔 |
| `K8S_LABEL` | `app.kubernetes.io/name=android` | K8s Pod 筛选 label |
| `K8S_API` | `https://kubernetes.default.svc` | K8s API 地址 |
| `ADB_PORT` | `5555` | android ADB 端口 |
| `WAIT_LIMIT` | `120` | 启动等待超时（秒） |
| `RETRY_COUNT` | `3` | 单个设备就绪检测重试次数 |
| `MONITOR_INTERVAL` | `10` | 设备变化监控间隔（秒） |
| `NODE_ENTRY` | `dist/index.js` | ws-scrcpy 入口文件 |
| `RESTART_DELAY` | `1` | ws-scrcpy 崩溃后重启等待（秒） |