## ShareusBot (NcatBot Migration)

迁移执行计划见：`/Users/zhaojl/Development/Projects/ShareusBot/docs/migration-todo.md`  
迁移接力文档见：`/Users/zhaojl/Development/Projects/ShareusBot/docs/migration-handover.md`

当前已完成首批 P0 迁移：
- 黑名单命令 `/拉黑 QQ [原因]`
- 入群请求黑名单拦截
- 求文模板解析 + MeiliSearch 检索 + Redis 频控
- 文件消息归档（下载 + PDF水印 + R2 上传 + 入库 + Meili 索引 + 失败回滚）
- 群管理基础迁移（管理群转发、/help、/resetAlistPwd、违禁词撤回禁言、入群欢迎、Bot进群通知）
- 定时任务基础迁移（APScheduler、日报/周报/月报、求文轮询/反馈/热榜、随机内容发送、QQ 信息刷新、重置密码、黑名单巡检、失效成员清理）

### 快速开始

1. 复制环境变量模板并填写：
   - `cp .env.example .env`
2. 安装依赖并运行：
   - `uv sync`
   - `uv run main.py`

### Docker 部署

1. 准备配置：
   - `cp .env.example .env`
   - 准备 `config.yaml`
2. 一键构建并部署：
   - `bash scripts/docker-deploy.sh deploy`
3. 查看运行状态或日志：
   - `bash scripts/docker-deploy.sh status`
   - `bash scripts/docker-deploy.sh logs`
