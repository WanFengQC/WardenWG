# WardenWG

WardenWG 是一个用于管理 WireGuard 节点、用户和订阅下发的服务端项目。

## Features
- 用户与设备管理（创建、禁用、删除、限额）
- 订阅生成：`/sub/{token}/main.yaml` 与 `/sub/{token}/nodes.yaml`
- 节点 Peer 同步与流量采集
- 管理后台与用户前台页面

## Endpoints
- 管理后台：`$ADMIN_WEB_PATH/login`（默认 `/console/login`）
- 用户登录：`/portal/login`
- 订阅入口：`/sub/{token}/main.yaml`

## Quick Start
```bash
docker compose up -d --build
```

## Environment
请使用 `.env` 配置运行参数，常见项包括：
- `DATABASE_URL`
- `ADMIN_WEB_PATH`
- `SUBSCRIPTION_BASE_URL`
- `SSH_USERNAME` / `SSH_PASSWORD`
- `WG_CONFIG_NAME`

## Security Notes
- 请勿将服务器地址、密钥、账号密码提交到仓库。
- 建议将敏感文件加入 `.gitignore`，并使用环境变量或密钥管理系统。
