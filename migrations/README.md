MVP 阶段先通过 SQLAlchemy `create_all` 起库。
生产环境建议补齐 Alembic 初始化脚本，并将 `users/nodes/peers/peer_traffic_snapshots/daily_traffic_summaries/subscription_access_logs` 纳入版本控制。

