# 从空服务器到学校部署验收

适用于2026-10-02候选源码。主线是原生`miniprogram/`与FastAPI `backend/`，生产数据库PostgreSQL 16。提供Docker Compose和直接Python两条路径；本文不把本地临时容器演练写成学校服务器已上线。

学校首次使用Docker部署可先读 [管理员逐步操作版](DOCKER_DEPLOYMENT_GUIDE.md)，按命令顺序完成安装、配置、启动和HTTPS；本文保留两条部署路径、升级和回滚的完整说明。

## 1. 明确版本、责任和资源

由维护者提供固定提交或不可变标签及源码校验值，运维记录接收提交、配置版本、镜像ID、执行人。不要直接下载随时变化的分支作为正式交付版本。当前 [v0.1.0-rc.1](https://github.com/syann2788-arch/DUT-duxue-space-booking/releases/tag/v0.1.0-rc.1)已于2026-10-03（北京时间）发布，目标提交为`3e63bf919322a3dca416569cc26c48b190cfb664`；状态仍是待部署验收。源码ZIP按随包记录核对，不包含真实`.env`、数据库、人员CSV或照片。

| 资源/确认 | 负责人 | 部署前结果 |
|---|---|---|
| Linux服务器、维护账号、磁盘/告警、入站443 | 学校运维 | Docker或Python3.12+运行环境；出站可访问微信API |
| 域名DNS、受信任证书及续期 | 学校网络/运维 | 类似`space-api.example.edu.cn`指向该服务器 |
| PostgreSQL16及备份/媒体持久化 | 学校运维 | 数据库不对公网开放；备份可独立恢复 |
| 小程序主体、开发者/体验权限、AppSecret、模板 | 小程序管理员 | AppID与后端一致；密钥安全注入 |
| 基础房间/规则、可信身份、密码核验、隐私期限 | 书院业务/隐私负责人 | 书面核对默认12房间/10规则，处理待确认业务歧义 |

Docker Engine与Compose插件由运维按 [Docker官方Ubuntu安装文档](https://docs.docker.com/engine/install/ubuntu/) 安装；本文采用Ubuntu24.04 LTS作为示例，其他系统按各自官方步骤。安装后运行`docker version`、`docker compose version`，并在Linux执行`sudo systemctl enable --now docker`启用服务。sudo/运维权限按学校策略配置。

## 2. 取得固定源码

以下在服务器终端执行，部署根目录举例`/srv/duxue/app`，父目录须先由运维建立并授权：

```sh
cd /srv/duxue
git clone https://github.com/syann2788-arch/DUT-duxue-space-booking.git app
cd app
# 先设为维护者实际提供的完整提交编号
DEPLOY_COMMIT='替换为已审核完整提交'
git checkout --detach "$DEPLOY_COMMIT"
git rev-parse HEAD
git status --porcelain
```

预期HEAD等于交付记录，工作区为空。若使用源码ZIP，在该目录解压、核对包校验值并记录对应提交；跳过Git命令。真实配置与数据放在学校受控目录，不覆盖源代码。首次部署前不要在该目录运行seed。

## 3A. Compose配置

下列命令从部署根目录执行：

```sh
cp .env.example .env
chmod 600 .env
mkdir -m 700 backups backup-keys
```

用学校受控编辑器填入`.env`。`POSTGRES_PASSWORD`与`SECRET_KEY`各自使用不同的强随机值，例如在受控终端分别运行`openssl rand -hex 32`生成。数据库密码采用十六进制字符，避免Compose拼接URL时遇到`@/:#`等保留字符。不要把生成值发到公开聊天或Git。

| 配置 | 要求 |
|---|---|
| APP_ENV | production |
| POSTGRES_PASSWORD / SECRET_KEY | 不同强随机值；JWT密钥至少32字符；首次初始化后不能只改`.env`假设现有数据库密码自动改变 |
| CORS_ORIGINS | 学校实际允许的Web域名（微信原生请求不靠CORS验证） |
| WECHAT_APP_ID | 当前已有wx78c441ce72d765fc；核对与构建AppID一致 |
| WECHAT_APP_SECRET与四模板ID | 从学校密钥库注入，API和worker均需要；空值只能验收普通业务 |
| BACKUP_DIR / BACKUP_KEY_DIR | 建议设置学校受控的绝对宿主机路径，备份与密钥分开保管 |
| BACKUP_AGE_RECIPIENT / BACKUP_SOURCE_COMMIT | 按运行手册生成加密公钥、填入交付完整提交编号 |

Compose的`${...}`来自当前shell或根`.env`（可以显式`--env-file /受控路径/compose.env`），**不会自动读取backend/.env**。如采用显式文件，以下每条`docker compose`命令均须加同一`--env-file`。不要公开运行`docker compose config`的完整结果，它可能含密钥；使用`docker compose config --quiet`只校验配置。

```sh
docker compose config --quiet
docker compose build api migrate worker
docker compose --profile ops build ops
docker compose up -d --wait --wait-timeout 60 db
docker compose ps db
```

预期db健康；数据库无宿主机端口映射。API只绑定`127.0.0.1:8000`，由同宿主机nginx对外提供HTTPS。若构建依赖下载失败，检查学校出站网络/批准代理后重试，不把开发者代理写入正式配置。

## 4A. 迁移、基础数据与正式建号

```sh
docker compose run --rm migrate
docker compose run --rm --no-deps api python init_reference_data.py
docker compose run --rm --no-deps api python create_admin.py
docker compose up -d api worker
```

空库迁移目标`20261002_03`。首次基础初始化输出`created_rooms=12, created_rules=10`，重复为0/0；只补缺失默认项，保留已有容量/停用/规则，不创建账号。默认规则删除后再次初始化会补回，暂停应在管理页禁用。

建号保留交互终端（不传`-T`），输入学校账号、姓名、至少8位含字母数字的新密码，两次确认。不要在命令行放密码。已有账号会拒绝覆盖或提升权限。所有步骤成功前不开放入口；失败保持停写，检查数据库健康、配置和迁移日志，再重试相应步骤。

## 5A. 服务、持久化与重启

```sh
docker compose ps
curl --fail http://127.0.0.1:8000/api/health
curl --fail http://127.0.0.1:8000/api/ready
docker compose logs --tail 80 api worker
```

预期health为ok；ready为200、schema.current/required=`20261002_03`、worker.ok=true。worker启动立即执行一次tick，若暂时503，等待首次tick完成再查；持续失败按 [运行手册](OPERATIONS_RUNBOOK.md) 排查，不关闭心跳要求来冒充通过。

| 命名卷（实际名称带Compose项目名前缀） | 内容 | 注意 |
|---|---|---|
| postgres_data | PostgreSQL数据 | `down -v`会删除，学校环境禁止随意使用 |
| uploads | 公开留言照片 | 通过受限`/uploads/message_*`路由，不含玉兰卡 |
| private_uploads | 玉兰卡/清扫照片 | 仅管理员鉴权；API与worker共享，默认90天清理 |
| counselor_credentials | CLI初始凭据 | 受控发放后按学校策略加密保管/清理，不归入普通媒体备份 |

按使用教程上传虚构照片后执行`docker compose restart api worker db`，等待ready恢复，复核照片能读取、记录和账号仍在。Linux Docker服务启用后，db/api/worker的`unless-stopped`恢复策略可在宿主机重启时恢复运行；**学校仍须实际重启验收**，手动stop的服务需再次up启动。升级时迁移job要显式重新执行。

## 3B–5B. 直接运行Python（无需Docker）

学校先安装Python3.12+、PostgreSQL16、nginx，创建专用系统服务账号和空数据库。应用数据库用户拥有该库public schema建表/迁移所需权限；不给网络远程访问或多余跨库权限。备份工具需Python3.12+、PostgreSQL16客户端、age。

安装包按学校批准的软件源取得；PostgreSQL服务运行后，在首次空环境由运维创建系统账号、数据库角色和库（同名已存在时先核查，不重复覆盖）：

```sh
sudo useradd --system --home /srv/duxue --shell /usr/sbin/nologin duxue
sudo -u postgres createuser --pwprompt duxue_app
sudo -u postgres createdb --owner=duxue_app duxue_school
sudo install -d -o duxue -g duxue -m 700 /srv/duxue/media/public /srv/duxue/media/private
```

createuser交互输入新的强密码；默认不授超级用户/建角色权限。配置DATABASE_URL使用该角色和库。服务账号需要读部署目录/虚拟环境，在服务账号可读的目录部署，避免用户私人目录权限阻断。

从部署根目录：

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
cp backend/.env.example backend/.env
chmod 600 backend/.env
```

把配置文件授权给服务账号（例如`sudo chown duxue:duxue backend/.env`且保持0600），需要时由授权运维编辑。编辑`backend/.env`为`APP_ENV=production`、强随机SECRET_KEY、`DATABASE_URL=postgresql+asyncpg://用户:URL编码密码@主机:5432/学校库`、学校微信配置、`REQUIRE_WORKER_HEARTBEAT=true`和两个独立持久化目录。如`/srv/duxue/media/public`、`/srv/duxue/media/private`，运维预先创建并授权服务账号，私密目录建议0700。进程从`backend/`工作目录启动，设置文件权限使服务账号可读；shell同名环境变量优先于`.env`，升级时核对避免误连其他库。

```sh
cd backend
sudo -u duxue ../.venv/bin/alembic upgrade head
sudo -u duxue ../.venv/bin/python init_reference_data.py
sudo -u duxue ../.venv/bin/python create_admin.py
sudo -u duxue ../.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
# 另一个终端从backend目录：sudo -u duxue ../.venv/bin/python -m app.worker
```

正式长驻改用systemd。仓库 [API模板](../deploy/duxue-api.service.example) 和 [worker模板](../deploy/duxue-worker.service.example) 默认`/srv/duxue/app`与`duxue`系统账号；先按实际路径/账号编辑，然后放入`/etc/systemd/system/duxue-api.service`与`duxue-worker.service`，执行：

```sh
sudo systemctl daemon-reload
sudo systemctl enable --now duxue-api duxue-worker
sudo systemctl status duxue-api duxue-worker
curl --fail http://127.0.0.1:8000/api/ready
```

两服务使用相同backend工作目录/环境。不要同时运行Compose和systemd的API/worker连接同一库作为“备份服务”。日志用`journalctl -u duxue-api -u duxue-worker`，备份时两者都停止；systemd模板需在学校Linux独立验收，本机macOS没有实际执行systemd。

## 6. DNS、HTTPS与微信

学校DNS管理员把域名指向服务器，用学校批准流程取得受信任证书，私钥只授予nginx所需权限，配置续期。复制 [nginx模板](../deploy/nginx.conf) 到站点配置，替换server_name和证书路径；代理指向同宿主机`127.0.0.1:8000`（若nginx也在容器内，应由运维改为容器网络地址，不能沿用该回环地址）。

```sh
sudo nginx -t
sudo systemctl reload nginx
curl --fail https://学校实际API域名/api/ready
```

学校防火墙仅开放所需443和运维入口；数据库不开放公网，禁止公开私密媒体目录或将所有`uploads`直接作为静态磁盘服务。nginx模板上传上限10MB，后端默认单图8MB；更改需同步。

域名/证书/反向代理验证通过后，小程序管理员按 [微信教程](WECHAT_SETUP.md) 配置request/uploadFile/downloadFile合法域名、隐私声明及模板。开发者按 [构建指南](BUILD_ARTIFACT_GUIDE.md) 注入四项配置、校验产物、导入dist、上传体验版。AppSecret仅注入后端，不进入构建环境、前端或交付文档正文。

## 7. 运维交接与联合验收

授权CSV导入、初始密码受控发放、密钥轮换、备份/恢复、日志和故障处理详见 [运行手册](OPERATIONS_RUNBOOK.md)。管理员独立按 [使用教程](USER_GUIDE.md) 完成一次四场景及清扫/恢复流程；运维执行数据库和公开/私密照片同恢复点演练，记录恢复耗时和丢失窗口。

保存版本/镜像ID/配置登记（不含真实密钥）、健康检查、媒体重启验证、恢复报告和学校操作记录。随后完成iPhone/Android、微信绑定与消息、可信身份/业务/隐私决定、签字；这些条件不能由空服务器教程替代。当前本地演练范围见 [05–11报告](HANDOVER_DOCUMENTATION_REPORT.md)。

## 8. 升级与回滚

从已验收提交升级到另一个经审核固定提交，先关闭入口并停止全部API/worker/导入写入，按手册备份同一时间点数据库和两个媒体目录，记录旧镜像与配置。更新源码→构建新镜像/依赖→显式`docker compose run --rm migrate`（或backend目录alembic）→API/worker→ready与功能复核→恢复流量。

代码可切回旧提交/镜像，但要先证明它兼容新schema。`20261002_03`不允许破坏性downgrade；不兼容时，在隔离的新库/新媒体目录恢复旧备份并验收，再由学校决定切换，不直接删除生产表或移走现有数据。Compose升级不要使用`down -v`，也不能只restart旧容器期待它加载新源码。恢复后故障重试和责任记录见运行手册。
