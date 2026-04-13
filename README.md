# WardenWG

WardenWG 是一个轻量的 WireGuard 管理面 MVP。它不承接用户 VPN 数据面，只做用户管理、订阅生成、peer 同步和基于 `wg show dump` 的流量采集。

## 1. 总体架构设计

### 1.1 模块划分

- `app/main.py`：FastAPI 入口与生命周期管理
- `app/models/`：用户、节点、peer、流量快照、日汇总、订阅访问日志
- `app/services/users.py`：创建用户、生成三节点 peer、订阅状态校验
- `app/services/subscription.py`：渲染 `main.yaml` 和 `nodes.yaml`
- `app/services/node_sync.py`：将 peer 配置同步到各节点
- `app/services/traffic.py`：解析 `wg show wg0 dump` 并写入快照与日汇总
- `app/routers/`：管理 API 与订阅 API
- `app/tasks/scheduler.py`：APScheduler 定时采集
- `scripts/seed_nodes.py`：初始化 3 个现有节点

### 1.2 数据流

1. 管理员通过 API 创建用户。
2. 系统为每个用户在 206/100/101 三个节点上各生成 1 个 WireGuard peer。
3. 用户只拿一个订阅入口：`/sub/<token>/main.yaml`。
4. `main.yaml` 引用 `/sub/<token>/nodes.yaml`，其中包含 3 个 `type: wireguard` 节点。
5. 客户端流量直接进入原生 WireGuard 节点，不经过 WardenWG。
6. 管理面定时通过 SSH 执行 `wg show wg0 dump`，只采集控制信息和计数器。
7. 采集结果写入 `peer_traffic_snapshots`，并累加到 `daily_traffic_summaries`。

### 1.3 为什么不会明显拖慢 VPN 性能

- 订阅下发和流量统计都在管理面完成，不在转发路径。
- VPN 数据仍然是客户端直连 3 台 WireGuard 节点。
- 统计只读取 WireGuard peer 计数器，不做统一入口、不做中转代理、不做额外封装。
- 定时采集频率默认 5 分钟一次，对节点的负载远低于中转代理方案。

## 2. 数据库表结构

### 2.1 `users`

```sql
CREATE TABLE users (
  id INTEGER PRIMARY KEY,
  username VARCHAR(64) UNIQUE NOT NULL,
  subscription_token VARCHAR(128) UNIQUE NOT NULL,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  expires_at TIMESTAMP NULL,
  total_quota_bytes BIGINT NULL,
  used_bytes BIGINT NOT NULL DEFAULT 0,
  remark TEXT NULL,
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL
);
CREATE INDEX ix_users_username ON users(username);
CREATE INDEX ix_users_subscription_token ON users(subscription_token);
CREATE INDEX ix_users_is_active ON users(is_active);
```

### 2.2 `nodes`

```sql
CREATE TABLE nodes (
  id INTEGER PRIMARY KEY,
  name VARCHAR(64) UNIQUE NOT NULL,
  display_name VARCHAR(128) NOT NULL,
  public_ip VARCHAR(64) UNIQUE NOT NULL,
  private_ip VARCHAR(64) NULL,
  ssh_port INTEGER NOT NULL DEFAULT 5522,
  ssh_host VARCHAR(128) NOT NULL,
  wg_endpoint_host VARCHAR(128) NOT NULL,
  wg_port INTEGER NOT NULL,
  wg_public_key VARCHAR(128) NOT NULL,
  wg_network VARCHAR(32) NOT NULL,
  reserved_host_octet INTEGER NOT NULL DEFAULT 10,
  sort_order INTEGER NOT NULL DEFAULT 100,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL
);
```

### 2.3 `peers`

```sql
CREATE TABLE peers (
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  node_id INTEGER NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
  name VARCHAR(128) NOT NULL,
  client_address VARCHAR(32) NOT NULL,
  private_key VARCHAR(128) NOT NULL,
  public_key VARCHAR(128) NOT NULL,
  preshared_key VARCHAR(128) NULL,
  allowed_ips VARCHAR(128) NOT NULL DEFAULT '0.0.0.0/0, ::/0',
  persistent_keepalive INTEGER NOT NULL DEFAULT 25,
  latest_handshake_at TIMESTAMP NULL,
  transfer_rx_total BIGINT NOT NULL DEFAULT 0,
  transfer_tx_total BIGINT NOT NULL DEFAULT 0,
  last_synced_at TIMESTAMP NULL,
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL,
  UNIQUE(node_id, public_key),
  UNIQUE(node_id, client_address)
);
CREATE INDEX ix_peers_user_id ON peers(user_id);
CREATE INDEX ix_peers_node_id ON peers(node_id);
CREATE INDEX ix_peers_public_key ON peers(public_key);
```

### 2.4 `peer_traffic_snapshots`

```sql
CREATE TABLE peer_traffic_snapshots (
  id INTEGER PRIMARY KEY,
  peer_id INTEGER NOT NULL REFERENCES peers(id) ON DELETE CASCADE,
  node_id INTEGER NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
  captured_at TIMESTAMP NOT NULL,
  transfer_rx_total BIGINT NOT NULL,
  transfer_tx_total BIGINT NOT NULL,
  delta_rx_bytes BIGINT NOT NULL DEFAULT 0,
  delta_tx_bytes BIGINT NOT NULL DEFAULT 0,
  latest_handshake_at TIMESTAMP NULL,
  UNIQUE(peer_id, captured_at)
);
CREATE INDEX ix_peer_traffic_snapshots_peer_id ON peer_traffic_snapshots(peer_id);
CREATE INDEX ix_peer_traffic_snapshots_captured_at ON peer_traffic_snapshots(captured_at);
```

### 2.5 `daily_traffic_summaries`

```sql
CREATE TABLE daily_traffic_summaries (
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  node_id INTEGER NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
  traffic_date DATE NOT NULL,
  rx_bytes BIGINT NOT NULL DEFAULT 0,
  tx_bytes BIGINT NOT NULL DEFAULT 0,
  total_bytes BIGINT NOT NULL DEFAULT 0,
  latest_handshake_at TIMESTAMP NULL,
  updated_at TIMESTAMP NOT NULL,
  UNIQUE(user_id, node_id, traffic_date)
);
CREATE INDEX ix_daily_traffic_summaries_user_id ON daily_traffic_summaries(user_id);
CREATE INDEX ix_daily_traffic_summaries_traffic_date ON daily_traffic_summaries(traffic_date);
```

### 2.6 `subscription_access_logs`

```sql
CREATE TABLE subscription_access_logs (
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token VARCHAR(128) NOT NULL,
  resource VARCHAR(64) NOT NULL,
  client_ip VARCHAR(64) NULL,
  user_agent VARCHAR(512) NULL,
  requested_at TIMESTAMP NOT NULL
);
CREATE INDEX ix_subscription_access_logs_user_id ON subscription_access_logs(user_id);
CREATE INDEX ix_subscription_access_logs_token ON subscription_access_logs(token);
CREATE INDEX ix_subscription_access_logs_requested_at ON subscription_access_logs(requested_at);
```

## 3. 项目目录结构

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
│  └─ main.py
├─ migrations/
├─ scripts/
├─ .env.example
├─ Dockerfile
├─ docker-compose.yml
├─ pyproject.toml
└─ README.md
```

## 4. 核心代码骨架

### 4.1 创建用户

- `POST /api/v1/users`
- 自动生成订阅 token
- 自动生成 3 个节点 peer
- 自动分配 `10.66.x.0/24` 中未占用地址

### 4.2 管理接口

- `GET /api/v1/users`
- `GET /api/v1/users/{id}`
- `POST /api/v1/users/{id}/enable`
- `POST /api/v1/users/{id}/disable`
- `GET /api/v1/users/{id}/subscription`
- `GET /api/v1/users/{id}/traffic`
- `POST /api/v1/users/{id}/rotate-token`
- `GET /api/v1/nodes`
- `POST /api/v1/nodes/seed`
- `POST /api/v1/tasks/collect-traffic`
- `POST /api/v1/tasks/sync-peers`

### 4.3 订阅接口

- `GET /sub/{token}/main.yaml`
- `GET /sub/{token}/nodes.yaml`

## 5. 订阅模板

- `main.yaml.j2`：一个主配置，包含 `proxy-providers` 和 `rule-providers`
- `nodes.yaml.j2`：用户自己的 3 个 WireGuard 节点
- 规则集默认使用 MetaCubeX `meta-rules-dat`

规则集 URL 基于官方仓库：

- [MetaCubeX/meta-rules-dat](https://github.com/MetaCubeX/meta-rules-dat)

## 6. 流量采集逻辑

1. 调度器每 5 分钟执行一次。
2. 对每个节点执行 `wg show wg0 dump`。
3. 通过 `public_key` 映射数据库中的 `peers`。
4. 与上次累计值比较，得到 `delta_rx_bytes` 和 `delta_tx_bytes`。
5. 写入 `peer_traffic_snapshots`。
6. 以天为粒度累加到 `daily_traffic_summaries`。

## 7. 节点同步机制建议

MVP 建议：

- 不直接整个覆盖 `/etc/wireguard/wg0.conf`
- 只维护一段 `managed-by=wardenwg` 的 peer 区块
- 在节点上准备一个合并脚本，将 managed peers 合并进主配置
- 合并后执行 `wg syncconf` 或 `wg setconf`

为什么这样做：

- 比全文件覆盖更稳，能保留已有 Interface/NAT 配置
- 比完全依赖热更新脚本更容易落地
- 后续可以演进为“数据库为源 + 节点持久化配置双写”

## 8. 部署方案

### 8.1 在 `10.0.0.206` 部署

建议放在 manager 节点 `10.0.0.206`，因为它已经有：

- Docker Swarm manager
- Nginx Proxy Manager
- Portainer

### 8.2 Docker Compose

```bash
cp .env.example .env
docker compose up -d --build
```

### 8.3 NPM 反代

- 域名：`sub.wfqc8.cn`
- Forward Host：WardenWG 容器所在主机 IP
- Forward Port：`8000`
- 勾选 WebSocket 支持
- 申请 Let’s Encrypt 证书

### 8.4 环境变量

- `DATABASE_URL`：开发先用 SQLite，生产换 PostgreSQL
- `ADMIN_API_KEY`：管理接口鉴权
- `SSH_PRIVATE_KEY_PATH` / `SSH_PASSWORD`：用于拉取 `wg dump` 和同步 peer，优先私钥，其次密码
- `SUBSCRIPTION_BASE_URL`：对外订阅地址前缀

## 9. 安全设计

- 用户订阅 token 使用 `secrets.token_urlsafe`
- 支持 token 轮换接口，旧 token 立即失效
- 管理 API 使用 `X-API-Key`
- 订阅 URL 足够长，不建议弱 token
- `nodes.yaml` 含用户私钥，只能通过用户专属 token 返回
- 日志不打印 `private_key`、`subscription_token`
- SSH 私钥通过 Docker secret 或宿主机只读挂载注入
- 如果当前只有 SSH 账号密码，也可以先用 `SSH_PASSWORD` 跑 MVP，后续再切到密钥认证

## 10. 下一步最小实施路径

1. 先在本机启动 API 与 SQLite，验证用户创建、订阅生成、流量接口可用。
2. 执行 `python scripts/seed_nodes.py` 写入 3 个现有节点。
3. 创建一个测试用户，检查 `main.yaml` 和 `nodes.yaml` 是否能被 Mihomo 导入。
4. 在 206 节点先准备 `wardenwg-merge-peers` 合并脚本，再打通 `sync-peers`。
5. 最后再接入真实 SSH 拉取 `wg show wg0 dump`，验证日统计闭环。

## 11. 当前限制

- Alembic 仅留目录说明，未生成完整迁移脚本。
- 远程节点合并脚本未内置到服务器，需要你在 206/100/101 上补一个统一脚本。
- 生产环境建议把 SQLite 切换成 PostgreSQL。
