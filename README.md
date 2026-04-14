# WardenWG

WardenWG 是一个面向 WireGuard 原生节点的轻量管理面 MVP。它不承接 VPN 数据转发，只负责用户管理、订阅下发、Peer 同步、流量采集和基础页面展示。

## 1. 入口

- 管理 API：`/api/v1/*`
- 订阅接口：`/sub/{token}/main.yaml`、`/sub/{token}/nodes.yaml`
- 管理后台：`/admin/login`
- 用户前台：`/portal/login`

如果已经通过 NPM 反代 `sub.wfqc8.cn`，则网页入口可以直接使用：

- `https://sub.wfqc8.cn/admin/login`
- `https://sub.wfqc8.cn/portal/login`

## 2. MVP 能力

- 创建用户时自动生成三台节点的 WireGuard Peer
- 为每个用户生成独立订阅 token
- 输出 Mihomo / Clash.Meta 可直接导入的 `main.yaml` 和 `nodes.yaml`
- 通过 SSH 到各节点执行 `wg show wg0 dump` 采集 Peer 计数器
- 按用户、按节点、按日汇总流量
- 管理后台支持创建用户、启停用户、轮换 token、触发流量采集、触发 Peer 同步
- 用户前台支持查看订阅链接、节点信息和流量统计

## 3. 核心目录

```text
WardenWG/
├─ app/
│  ├─ core/
│  ├─ db/
│  ├─ models/
│  ├─ routers/
│  ├─ schemas/
│  ├─ services/
│  ├─ tasks/
│  ├─ templates/
│  ├─ main.py
│  └─ web.py
├─ scripts/
│  ├─ seed_nodes.py
│  └─ wardenwg_merge_peers.py
├─ migrations/
├─ Dockerfile
├─ docker-compose.yml
├─ pyproject.toml
└─ .env.example
```

## 4. 数据模型

主要表：

- `users`
- `nodes`
- `peers`
- `peer_traffic_snapshots`
- `daily_traffic_summaries`
- `subscription_access_logs`

用途：

- `users`：用户状态、订阅 token、流量配额
- `nodes`：节点出口、SSH 与 WireGuard 基本信息
- `peers`：每个用户在每台节点上的独立 Peer
- `peer_traffic_snapshots`：定时采集到的累计计数器快照
- `daily_traffic_summaries`：按日汇总后的用户流量
- `subscription_access_logs`：订阅访问记录

## 5. 管理后台

地址：

- `GET /admin/login`
- `GET /admin`

功能：

- 创建用户
- 查看用户的三节点 Peer 地址
- 查看订阅主链接
- 启用 / 禁用用户
- 轮换订阅 token
- 立即采集流量
- 立即同步 Peer 到三台节点

认证：

- 登录输入 `.env` 中的 `ADMIN_API_KEY`
- 登录后服务端生成短期会话 Cookie

## 6. 用户前台

地址：

- `GET /portal/login`
- `GET /portal`

功能：

- 查看 `main.yaml`
- 查看 `nodes.yaml`
- 查看自己三台节点的 Peer 信息
- 查看按节点、按日的流量统计

登录方式：

- 输入自己的 `subscription_token`
- 或通过 `/portal?token=<subscription_token>` 直接进入

## 7. 环境变量

最关键的配置如下：

```env
APP_NAME=WardenWG
APP_ENV=prod
DEBUG=false
DATABASE_URL=sqlite:////app/data/wardenwg.db
TIMEZONE=Asia/Shanghai

MANAGER_BASE_URL=https://sub.wfqc8.cn
SUBSCRIPTION_BASE_URL=https://sub.wfqc8.cn
SUBSCRIPTION_DISPLAY_NAME=WFQC8
API_PREFIX=/api/v1

ADMIN_API_KEY=change-me

WG_CONFIG_NAME=wg0
WG_INTERFACE_MTU=1420
WG_PERSISTENT_KEEPALIVE=25

SSH_PORT=5522
SSH_USERNAME=root
SSH_PRIVATE_KEY_PATH=
SSH_PASSWORD=your-ssh-password

TRAFFIC_COLLECTION_INTERVAL_MINUTES=5
DEFAULT_RULESET_BASE_URL=https://raw.githubusercontent.com/MetaCubeX/meta-rules-dat/meta/geo
```

说明：

- Docker 容器内 SQLite 路径必须写成 `/app/data/...`
- SSH 认证支持“优先私钥，其次密码”
- 如果暂时没有密钥，可以先用 `SSH_PASSWORD`
- `SUBSCRIPTION_DISPLAY_NAME` 会作为客户端订阅卡片显示名称，默认 `WFQC8`

## 8. 部署

### 8.1 启动服务

```bash
docker compose up -d --build
```

### 8.2 初始化节点

```bash
docker compose exec api python scripts/seed_nodes.py
```

### 8.3 NPM 反代

将 `sub.wfqc8.cn` 反代到：

- Host：`10.0.0.206`
- Port：`8000`
- Scheme：`http`

建议开启：

- Force SSL
- HTTP/2
- HSTS
- Block Common Exploits

## 9. Peer 同步脚本

项目内置节点合并脚本：

- [scripts/wardenwg_merge_peers.py](/C:/Users/EDY/Desktop/server/WardenWG/scripts/wardenwg_merge_peers.py)

需要部署到三台节点：

- `/usr/local/bin/wardenwg-merge-peers`

并赋权：

```bash
chmod 755 /usr/local/bin/wardenwg-merge-peers
```

这个脚本会：

- 保留原有 `Interface` 和非托管 Peer
- 只替换 `managed-by=wardenwg` 标记区块
- 先通过 `wg-quick strip` 转成内核可接受格式
- 再执行 `wg syncconf`

## 10. 验证链路

### 10.1 健康检查

```bash
curl http://127.0.0.1:8000/healthz
```

### 10.2 创建用户

```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $ADMIN_API_KEY" \
  http://127.0.0.1:8000/api/v1/users \
  -d '{"username":"test001","remark":"first user"}'
```

### 10.3 同步 Peer

```bash
curl -X POST \
  -H "X-API-Key: $ADMIN_API_KEY" \
  http://127.0.0.1:8000/api/v1/tasks/sync-peers
```

### 10.4 采集流量

```bash
curl -X POST \
  -H "X-API-Key: $ADMIN_API_KEY" \
  http://127.0.0.1:8000/api/v1/tasks/collect-traffic
```

### 10.5 查询用户流量

```bash
curl \
  -H "X-API-Key: $ADMIN_API_KEY" \
  http://127.0.0.1:8000/api/v1/users/1/traffic
```

### 10.6 订阅卡片名称与流量条

订阅接口会返回以下响应头，兼容 Mihomo / Clash Verge 一类客户端：

- `Content-Disposition`：设置订阅显示名称，默认 `WFQC8`
- `Subscription-Userinfo`：显示流量进度条
- `Profile-Web-Page-Url`：跳转到用户前台
- `Profile-Update-Interval`：提示客户端 24 小时更新一次

## 11. 当前限制

- Alembic 目录已预留，但迁移脚本未完善
- Web 会话是进程内存会话，重启容器后需要重新登录
- 管理后台目前仍使用单一 `ADMIN_API_KEY` 登录，不是多管理员体系
- 用户前台当前基于 `subscription_token` 登录，尚未单独拆用户密码体系
- 生产环境建议后续切换到 PostgreSQL
