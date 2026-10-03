# Docker 部署步骤：学校管理员操作版

编写日期：2026-10-03。目标：在一台学校 Linux 服务器上运行空间预约系统的数据库、后端和后台任务，接通 HTTPS，交给小程序管理员完成微信联调。

当前可下载版本是 [v0.1.0-rc.1](https://github.com/syann2788-arch/DUT-duxue-space-booking/releases/tag/v0.1.0-rc.1)，固定提交 `3e63bf919322a3dca416569cc26c48b190cfb664`，属于**待部署验收的候选版**。本教程在该版本发布后新增，可作为独立补充教程配合它使用；已发布 ZIP 不会被修改或覆盖。

以 **Ubuntu 24.04 LTS、首次空服务器部署、同宿主机 nginx** 为例。Windows/macOS 电脑用于 SSH 连接和微信开发者工具，以下服务器命令在 SSH 终端执行。已有业务数据的服务器应走 [升级与回滚流程](DEPLOYMENT_GUIDE.md#8-升级与回滚)，不要重复初始化或覆盖配置。

操作顺序：准备资源 → 安装 Docker → 下载并校验源码 → 填配置 → 构建 → 数据库迁移与建号 → 启动 → HTTPS → 微信联调 → 接收验收。

## 1. 先准备这些资料

| 资料 | 谁提供 | 用在哪里 |
|---|---|---|
| Linux 服务器地址、SSH 账号、sudo 权限 | 学校运维 | 登录、安装及管理服务 |
| 实际 API 域名、DNS、受信任证书与私钥、续期安排 | 学校网络/运维 | nginx 对外 HTTPS |
| AppID、小程序成员权限 | 小程序管理员 | 当前 AppID 为 `wx78c441ce72d765fc`，仍需核对学校主体 |
| AppSecret、四类订阅消息模板 ID | 小程序管理员 | 仅填后端配置；普通业务可先启动，微信绑定和消息须配置后验证 |
| 管理员账号及接收责任人 | 书院业务负责人 | 第 6 步交互创建；不使用演示账号 |
| 备份存储、加密公钥、密钥保管责任 | 学校运维 | 开放使用前完成备份与恢复演练 |

服务器需要能下载 Docker 镜像、Python 依赖，并能访问微信接口。对外开放学校批准的 SSH 运维入口和 443；本项目数据库不映射公网端口，API 只映射服务器自身的 `127.0.0.1:8000`。

## 2. 安装并确认 Docker

如果学校已经安装 Docker Engine 和 Compose 插件，先运行：

```sh
sudo docker version
sudo docker compose version
```

两条均成功即可继续。首次安装采用 [Docker 官方 Ubuntu 安装流程](https://docs.docker.com/engine/install/ubuntu/) 的 apt 软件源方案；已有 Docker/containerd 工作负载由运维先核查，不直接卸载。

首次空服务器可执行：

```sh
sudo apt update
sudo apt install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

sudo tee /etc/apt/sources.list.d/docker.sources >/dev/null <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: noble
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF

sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo docker version
sudo docker compose version
```

这里的 `noble` 仅适用于 Ubuntu 24.04；其他系统按官方对应版本安装。后续统一写 `sudo docker compose`，无需额外修改用户组。`up --wait` 用于等待服务健康；`run --rm` 用于执行迁移、建号等一次性任务，见 [up 文档](https://docs.docker.com/reference/cli/docker/compose/up/) 和 [run 文档](https://docs.docker.com/reference/cli/docker/compose/run/)。

## 3. 下载、校验并解压交付包

先安装接收所需工具，再建立本次部署目录：

```sh
sudo apt install -y python3 unzip openssl nano
sudo install -d -m 0750 -o "$(id -un)" -g "$(id -gn)" /srv/duxue/releases/v0.1.0-rc.1
cd /srv/duxue/releases/v0.1.0-rc.1
mkdir -p artifacts
cd artifacts
```

确认artifacts是本次新建的空目录；已有同版本目录时先核对交付记录，不重下覆盖。将 Release 中这四个附件上传到artifacts目录，也可直接下载：

```sh
curl --fail --location --output source.zip https://github.com/syann2788-arch/DUT-duxue-space-booking/releases/download/v0.1.0-rc.1/source.zip
curl --fail --location --output handover.zip https://github.com/syann2788-arch/DUT-duxue-space-booking/releases/download/v0.1.0-rc.1/handover.zip
curl --fail --location --output handover-manifest.json https://github.com/syann2788-arch/DUT-duxue-space-booking/releases/download/v0.1.0-rc.1/handover-manifest.json
curl --fail --location --output SHA256SUMS https://github.com/syann2788-arch/DUT-duxue-space-booking/releases/download/v0.1.0-rc.1/SHA256SUMS
sha256sum --check SHA256SUMS
```

预期三个被校验文件均显示 `OK`。与维护者通过独立可信渠道确认的摘要比对；当前版本源码 ZIP 的 SHA-256 为：

```text
f451e6e8e45f0a09e1f16c6ac8e166d7f4ba384c863a3bd0fe624d30842b7d63
```

通过后解压源码，再做完整包校验：

```sh
unzip source.zip -d ..
python3 ../source/scripts/package_handover.py verify .
cd ../source
pwd
```

预期校验通过，版本 `0.1.0-rc.1`、提交 `3e63bf919322a3dca416569cc26c48b190cfb664`、状态 `pending-school-deployment-acceptance`；当前目录为 `/srv/duxue/releases/v0.1.0-rc.1/source`。artifacts目录只保留四份附件，解压目录在它旁边；校验器会拒绝附件目录里的额外文件或文件夹。

**从第 4 步到日常维护，所有 Compose 命令都在这个 source 目录执行。** 保持部署目录和 Compose 项目名不变，避免换目录后连接到另一组空数据卷。

## 4. 填写服务器配置

首次配置：

```sh
cp -n .env.example .env
chmod 600 .env
mkdir -p backups backup-keys
chmod 700 backups backup-keys
nano .env
```

已有 `.env` 时先核对，不覆盖。需要填写的内容如下：

| 配置项 | 填写要求 |
|---|---|
| `APP_ENV` | 保持 `production` |
| `POSTGRES_PASSWORD` | 强随机数据库密码；建议 64 位十六进制字符 |
| `SECRET_KEY` | 另一个独立随机密钥；不能与数据库密码相同 |
| `CORS_ORIGINS` | 学校实际允许的 Web 来源；可先填实际 HTTPS API 来源，替换示例域名 |
| `WECHAT_APP_ID` | 核对 `wx78c441ce72d765fc` 与学校小程序一致 |
| `WECHAT_APP_SECRET` | 学校提供的真实 AppSecret，仅服务器保存 |
| 四个 `WECHAT_TEMPLATE_*` | 学校批准的提交、审核、提醒、资格变更模板 ID；空值不具备真实消息能力 |
| `BACKUP_DIR` / `BACKUP_KEY_DIR` | 建议改成学校指定的绝对路径，备份和解密密钥分开保管 |
| `BACKUP_AGE_RECIPIENT` | 备份加密公钥，按 [运维手册](OPERATIONS_RUNBOOK.md) 设置 |
| `BACKUP_SOURCE_COMMIT` | `3e63bf919322a3dca416569cc26c48b190cfb664` |

在受控终端分别执行两次下列命令，得到不同的数据库密码与系统密钥，保存到学校密码库并填入 `.env`：

```sh
openssl rand -hex 32
```

保存后只检查配置是否有效：

```sh
sudo docker compose config --quiet
```

预期无错误并返回终端。Compose 读取**源码根目录 `.env`**，不读取 `backend/.env`；运维使用显式 `--env-file` 时，后续每条命令必须使用同一配置文件。同名 shell 环境变量也可能覆盖文件值。

真实 `.env`、密码、AppSecret 不提交 GitHub，也不发到公开群聊。不要公开完整 `docker compose config` 输出，它可能包含密钥。

## 5. 构建镜像，启动数据库

```sh
sudo docker compose build api migrate worker
sudo docker compose --profile ops build ops
sudo docker compose up -d --wait --wait-timeout 120 db
sudo docker compose ps db
```

第一次会下载镜像和依赖，耗时取决于网络。预期 `db` 状态为 `healthy`；`ops` 是备用的备份/恢复工具镜像，不是日常常驻服务。失败时检查下载网络或数据库日志，再重试此步骤。

## 6. 创建数据表、初始化房间、创建管理员

按下面顺序执行，上一条成功后再运行下一条：

```sh
sudo docker compose run --rm migrate
sudo docker compose run --rm --no-deps api python init_reference_data.py
sudo docker compose run --rm --no-deps api python create_admin.py
```

预期结果：

1. 迁移完成，数据库版本为 `20261002_03`。
2. 空库初始化显示 `created_rooms=12, created_rules=10`；再次执行通常为 `0/0`，只补缺失基础数据。
3. 建号提示输入管理员账号、姓名和新密码，密码至少 8 位且包含字母、数字，两次输入一致。终端输入密码时不显示字符属于正常行为；不要加 `-T` 或把密码写在命令参数里。

已有同账号会拒绝覆盖，交给管理员恢复流程处理。**学校环境不执行 `seed.py`，不使用 `admin001/admin123` 演示账号。** 基础房间容量、规则和学校身份核验方案仍须业务负责人确认。

## 7. 启动后端和后台任务

```sh
sudo docker compose up -d --wait --wait-timeout 120 api worker
sudo docker compose ps
curl --fail http://127.0.0.1:8000/api/health
curl --fail http://127.0.0.1:8000/api/ready
```

预期：`db`、`api` 健康，`worker` 运行；`health` 返回正常，`ready` 返回 HTTP 200，`schema.current/required` 都是 `20261002_03`，`worker.ok=true`。迁移容器完成后显示 `Exited (0)` 是正常结果。

首次后台任务尚未完成一次 tick 时可能短暂未就绪，稍后重查；持续失败则查看日志：

```sh
sudo docker compose logs --tail 80 api worker
sudo docker compose logs --tail 80 migrate db
```

本步骤证明服务器本机可用。此时 API 绑定 `127.0.0.1`，其他电脑或手机不能通过 `http://服务器IP:8000` 访问；第 8 步通过 HTTPS 对外提供入口。

## 8. 配置学校域名和 HTTPS

由学校运维确认 DNS 已指向该服务器，受信任证书覆盖实际域名，证书与私钥已放到学校批准的服务器路径并安排续期。本教程使用**同宿主机 nginx**；nginx 若在另一个容器中运行，需另行配置容器网络，不能照搬 `127.0.0.1:8000`。

Ubuntu 首次安装 nginx 并编辑本项目站点：

```sh
sudo apt install -y nginx
sudo cp -n deploy/nginx.conf /etc/nginx/sites-available/duxue
sudo nano /etc/nginx/sites-available/duxue
```

只在该站点尚不存在时执行 `cp`；已有文件由运维先保存副本并合并配置。把模板中的三项替换成学校实际值：

```nginx
server_name 学校实际API域名;
ssl_certificate /学校证书绝对路径/fullchain.pem;
ssl_certificate_key /学校私钥绝对路径/privkey.pem;
```

保留模板的 `/api/`、`/uploads/` 代理和 `proxy_pass http://127.0.0.1:8000`，私密照片由后端鉴权提供。然后启用站点并检查：

```sh
sudo ln -s /etc/nginx/sites-available/duxue /etc/nginx/sites-enabled/duxue
sudo nginx -t
sudo systemctl enable --now nginx
sudo systemctl reload nginx
```

链接已存在时不重复创建。`nginx -t` 通过后才 reload。学校防火墙放行 443，同时保留运维入口；从另一台能够访问学校服务的电脑验证：

```sh
curl --fail https://学校实际API域名/api/ready
```

预期 HTTP 200，无证书错误；不使用 `curl -k` 掩盖证书问题。由运维按学校制度配置证书续期，并验证续期后 nginx 能重新加载证书。

## 9. 交给小程序管理员连接微信

服务器部署到此完成，微信端按 [微信配置教程](WECHAT_SETUP.md) 和 [构建教程](BUILD_ARTIFACT_GUIDE.md) 操作：

1. 核对小程序主体/AppID，将开发者和体验人员加入项目。
2. 将实际 HTTPS 域名加入 request、uploadFile、downloadFile 合法域名； API 基地址为 `https://学校实际API域名/api`。
3. 在开发者电脑从固定源码构建，注入 AppID、API 地址、版本和完整提交，校验后导入对应构建目录。
4. 上传体验版，用学校授权测试人员完成预约、审核、照片、清扫、密码恢复与四类订阅消息的真机验证。

Docker 部署的是数据库、API 和 worker；微信开发者工具只上传小程序前端。AppSecret 不进入前端构建配置。

## 10. 验收和登记

正式开放使用前，学校运维和业务管理员填写：

- [ ] 记录版本、完整提交、服务器、部署目录、Compose 项目名、执行日期及接收负责人。
- [ ] `db/api` 健康、worker 运行，外部 HTTPS `/api/ready` 返回 200。
- [ ] 正式管理员能登录；房间和规则已核对；不使用演示账号和人员。
- [ ] 使用授权测试数据验证预约、审核、照片和清扫；重启后数据库及媒体仍可读取。
- [ ] 设置独立备份及加密密钥保管，按 [运维手册](OPERATIONS_RUNBOOK.md) 在空目标完成数据库和公开/私密照片同一恢复点演练。
- [ ] 验证宿主机重启恢复、证书续期和故障处理，确认维护期限及支持范围。
- [ ] 学校本人核验/可信注册、隐私和真机消息验证完成，按 [阶段发布清单](RELEASE_CHECKLIST.md) 完成正式验收。

源码接收、服务器健康和学校正式验收分别记录；完整接收表见 [交付指南](HANDOVER_GUIDE.md)。记录中只填配置/密钥的保管编号，不写真实密码。

## 日常最常用的命令

先进入 `/srv/duxue/releases/v0.1.0-rc.1/source`，再操作：

| 目的 | 命令 |
|---|---|
| 查看状态 | `sudo docker compose ps` |
| 查看最近日志 | `sudo docker compose logs --tail 80 api worker` |
| 重启 API/worker | `sudo docker compose restart api worker` |
| 暂停写入和后台任务 | `sudo docker compose stop api worker`，并暂停所有外部导入/写入 |
| 恢复服务 | `sudo docker compose up -d api worker`，再检查 ready |
| 更新 AppSecret/模板配置后生效 | `sudo docker compose up -d --force-recreate api worker` |

`restart` 不会加载修改后的容器环境。数据库初始化后不能只修改 `.env` 的 `POSTGRES_PASSWORD` 来完成密码轮换。持久化数据位于 Compose 命名卷，不保存在容器临时文件层；不要执行 `docker compose down -v`，它会删除数据卷。升级及备份恢复使用 [完整部署教程](DEPLOYMENT_GUIDE.md) 和 [运维手册](OPERATIONS_RUNBOOK.md)。

## 常见问题

| 现象 | 先检查什么 |
|---|---|
| `docker compose` 命令不存在 | 是否安装官方 Compose 插件；使用空格写法，不是旧 `docker-compose` |
| 提示没有权限访问 Docker | 使用本教程的 `sudo docker compose`；学校运维确认 sudo 权限 |
| 报 `POSTGRES_PASSWORD` / `SECRET_KEY` 未设置 | 是否在正确 source 目录，根 `.env` 是否填写，有无同名环境变量覆盖 |
| 构建下载失败 | 服务器访问镜像库/依赖源的网络，由学校配置批准的出口；本机 7898 代理不能直接套用到学校服务器 |
| 数据库 authentication failed | 初始化时数据库密码与当前配置是否一致，不删卷重建业务数据库 |
| ready 一直失败 | 查看迁移目标和 worker 日志，不关闭 worker 心跳检查来绕过失败 |
| HTTPS 返回 502 | 先查本机 ready，再查 nginx 代理与监听；宿主机模板不能直接用于容器 nginx |
| 上传提示过大 | 模板 nginx 上限 10MB、后端默认单图 8MB，调整时同步核对 |
| 预约成功但微信没有消息 | AppSecret、模板字段、用户绑定/订阅授权、出站网络和 worker；空模板不发送真实消息 |

本文命令已按当前仓库配置及官方 Docker 文档核对；Ubuntu 安装、学校域名/证书和真实微信操作需由学校在自己的环境执行验收。
