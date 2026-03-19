# container

集群镜像仓库，仅适配 kubernetes。

## 镜像标签

每个镜像同时维护两条构建线：

| 标签              | 示例             | 含义                                  |
| ----------------- | ---------------- | ------------------------------------- |
| `<release>-<sha>` | `v2.1.3-abc1f3d` | 跟随上游 release，sha 为本仓库 commit |
| `latest`          | `latest`         | 始终指向最新 release 构建             |
| `main-<sha>`      | `master-abc1f3d` | 跟随上游默认分支，sha 为上游 commit   |
| `edge`            | `edge`           | 始终指向最新默认分支构建              |

生产环境建议使用 `<release>-<sha>`，测试环境可使用 `edge`。

## 添加新镜像

在 `docker/` 下新建目录，添加 Dockerfile。模板如下：

```dockerfile
FROM ...

ARG UPSTREAM_VERSION=<上游默认分支>
ARG UPSTREAM_SHA

LABEL upstream-repo=owner/repo

LABEL org.opencontainers.image.version="${UPSTREAM_VERSION}"
LABEL org.opencontainers.image.revision="${UPSTREAM_SHA}"
LABEL org.opencontainers.image.source="https://github.com/MewCluster/container"
# 使用 UPSTREAM_VERSION 拉取对应版本的源码
RUN git clone --depth=1 --branch ${UPSTREAM_VERSION} https://github.com/owner/repo.git
```

> `UPSTREAM_VERSION` 的默认值须与上游默认分支名一致，CI 会动态获取上游默认分支并传入该值。

## 构建触发

- **每日构建**：自动检测所有镜像的上游是否有新 release 或新默认分支 commit，有变化则触发构建
- **main 分支更新**：检测 `docker/` 下有变动的目录，自动构建新镜像
