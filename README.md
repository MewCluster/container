# container

集群镜像仓库，详情参考 `docker` 下各个文件夹。

## 镜像标签

每个正式镜像同时维护两条构建线，并提供独立的分支/PR测试标签：

| 标签              | 示例             | 含义                                  |
| ----------------- | ---------------- | ------------------------------------- |
| `<release>-<sha>` | `v2.1.3-abc1f3d` | 跟随上游 release，sha 为本仓库 commit |
| `latest`          | `latest`         | 始终指向最新 release 构建             |
| `main-<sha>`      | `main-abc1f3d`   | 跟随上游默认分支，sha 为上游 commit，无论上游默认分支为何此处都为 main   |
| `edge`            | `edge`           | 始终指向最新默认分支构建              |
| `pr-<number>`     | `pr-12`          | (测试) 始终指向该 PR 的最新构建          |
| `<branch-name>`   | `feat-new-app`   | (测试) 始终指向该分支的最新构建 (含字符安全过滤) |
| `sha-<hash>`      | `sha-abc1f3d`    | (测试) 分支/PR 测试构建绑定的短 SHA 标签 |

生产环境建议使用 `<release>-<sha>`，正式环境测试可使用 `edge`，开发调试拉取 `<branch-name>` 或 `pr-<number>`。

## 添加新镜像

在 `docker/` 下新建目录，添加 `Dockerfile`。

### 多变体支持
CI 支持在同一个目录下放置多个变体 Dockerfile，通过不同的文件名自动生成对应的镜像标签：
- 默认：`docker/apps/Dockerfile` -> 构建为 `ghcr.io/mewcluster/apps:latest` (及对应的版本号 tags)
- 变体：`docker/apps/python-11.3.Dockerfile` -> 构建为 `ghcr.io/mewcluster/apps:latest-python-11.3` (所有的基础 tags 会自动在末尾追加 `-python-11.3` 后缀，例如 `v1.2.3-python-11.3`)

### Dockerfile 模板

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

- **每日构建**：自动检测所有 Dockerfile 标注的 `upstream-repo` 是否有新 release 或新 commit，有变化则触发正式构建
- **main 分支推送**：检测 `docker/` 下有变动的 `*Dockerfile`，自动构建正式版新镜像
- **非 main 分支或 PR 推送**：拦截进入测试构建通道，推送带有分支特性前缀的临时测试镜像，不覆盖 `latest` 和 `edge`
