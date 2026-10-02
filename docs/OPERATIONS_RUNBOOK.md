# 生产运行、备份恢复与账号运维

2026-10-02。首次部署见 [部署教程](DEPLOYMENT_GUIDE.md)，业务操作见 [使用教程](USER_GUIDE.md)。本手册命令均注明目录；真实配置与凭据只由学校运维保存。当前候选需要schema `20261002_03`。

## 发布与运行检查

发布顺序：已审核固定提交→停写/备份（已有环境）→迁移→基础初始化/正式建号（首次环境）→API与独立worker→ready→功能复核→入口流量。Compose从仓库根目录执行；直接Python从`backend/`读取`.env`。

```sh
# Compose，仓库根目录
docker compose ps
curl --fail http://127.0.0.1:8000/api/ready
docker compose logs --tail 100 api worker
```

health是进程存活；ready的数据库、schema和worker应全部正常，生产需保持`REQUIRE_WORKER_HEARTBEAT=true`。worker启动立即tick，此后每分钟执行，PostgreSQL advisory lock保证同时只有一个tick；启动短暂503需等待，持续503核对revision与`worker_last_success_at`。`outbox_pending`是待发送数，ready不因其增加自动失败，学校要另设告警。微信未配置/未绑定可显示failed，不能把消息记录存在当发送成功。

JSON日志带`request_id`/`job_id`，记录请求编号、时间和动作进行排障，不公开真实业务数据。Docker日志轮转由学校Docker守护进程策略设置；直接Python用journalctl与学校日志留存策略。告警包括readiness、磁盘、worker心跳、消息失败增长、证书到期和备份失败。

## 20261002_03迁移与回滚

`users`增加`session_version`和`must_change_password`，新增`password_reset_credentials`（仅凭证摘要/到期/使用状态）与`admin_audit_logs`。完整旧库迁移链为20260813_01→20260813_02→20261002_03。

迁移前备份并在隔离库验证旧版本兼容。此迁移的downgrade主动拒绝破坏性降级。代码可切回已验收版本，但不能假设旧代码兼容新schema；不兼容则按以下同恢复点流程恢复到**新空库与新媒体目录/卷**，验收后再切换，保留原环境，不直接删生产表。

## 基础数据与正式账号

`init_reference_data.py`沿用`app/reference_data.py`的12房间/10规则，学校先核对。它只补缺失项，不更新、启用、删除现有房间/规则，不改系统参数、不建账号。默认规则删除后重新初始化会补回，停用应在管理页禁用。PostgreSQL并发初始化使用事务级锁。

直接Python（backend目录，使用部署虚拟环境）：

```sh
../.venv/bin/alembic upgrade head
../.venv/bin/python init_reference_data.py
../.venv/bin/python create_admin.py
```

Compose（仓库根目录，配置已准备、db健康）：

```sh
docker compose run --rm migrate
docker compose run --rm --no-deps api python init_reference_data.py
docker compose run --rm --no-deps api python create_admin.py
```

首次基础初始化输出12/10，重复0/0。建号保留交互终端，不放密码在命令行；已存在账号拒绝覆盖/提升角色。生产禁止seed/demo_seed，不通过修改APP_ENV绕过。学校还需创建实际管理员、登记负责人、受控保管与轮换；技术脚本存在不等于学校建号已完成。

人工密码恢复：管理员按学校流程核验本人，用户详情输入自己的密码与核验原因，签发30分钟一次性凭证；重发失效旧凭证，成功恢复撤销旧会话与微信绑定。日常改密撤销旧会话和未用凭证。日志不保存明文凭证。管理员本人改密使用“我的→修改密码”，忘记密码由另一授权管理员核验处理。

## 辅导员授权导入

学校CSV字段按`Sheet_20250907.example.csv`核对，实际姓名/联系方式与初始密码不得进入Git。CLI仅处理职务为辅导员/执行院长/副院长的有效行；数字联系方式作为登录标识，否则staff_姓名。已有辅导员保留，标识与学生冲突整批拒绝。

Compose已运行API后，从仓库根目录：

```sh
docker compose cp /学校受控路径/counselors.csv api:/tmp/counselors.csv
docker compose exec --user root api chown app:app /tmp/counselors.csv
docker compose exec --user root api chmod 600 /tmp/counselors.csv
docker compose exec -e COUNSELOR_CSV_PATH=/tmp/counselors.csv -e COUNSELOR_CREDENTIALS_OUTPUT=/app/credentials/counselor-credentials-唯一批次.json api python import_counselors.py
docker compose exec api rm /tmp/counselors.csv
```

凭据文件写入独立`counselor_credentials`卷、权限0600、名称必须每批唯一。学校运维受控取出并分别发放；首次登录强制换密。发放后清理临时CSV、剪贴板和无需保留的凭据；该卷不进入普通照片备份，按学校策略另行加密保存/清理。直接Python需显式设COUNSELOR_CSV_PATH和COUNSELOR_CREDENTIALS_OUTPUT并准备可写受控目录。小程序概览亦支持授权CSV导入，结果交管理员受控保存。

## 备份前提与新格式

`deploy/backup.sh`、`restore.sh`调用标准库工具`backup_restore.py`。需要Python3.12+、PostgreSQL16的pg_dump/pg_restore/psql及age；Compose的ops镜像自带这些工具。pg_dump得到数据库一致快照，但**不能与仍在变化的磁盘照片自动保持同一时点**；本方案采用停写窗口。数据库转储和恢复选项参考 [PostgreSQL官方pg_dump](https://www.postgresql.org/docs/16/app-pgdump.html)、[pg_restore](https://www.postgresql.org/docs/16/app-pgrestore.html)。

必须关闭所有入口并停止所有API实例、worker、后台导入、其他直接数据库写入与媒体清理，确认没有进行中的事务/上传后再备份。仅关闭小程序、只停一个API或仍运行worker不满足要求。环境变量`BACKUP_WRITES_STOPPED=yes`是操作人完成停写后的声明，脚本不会自动停止或证明其他实例已停。

每次生成独立`snapshot-UTC时间-随机编号/`，包含`database.dump.age`、`media.tar.gz.age`及`manifest.json`。媒体归档同时包含public/private目录，清单记录密文长度、SHA-256、schema revision、源库名称/主机和提交记录；没有数据库密码或用户资料。两个密文生成完整后才发布目录，临时明文结束清理；失败不发布不完整快照。

脚本不再自动删除14天前备份，保留/删除周期由学校书面策略负责；至少保存升级前恢复点，异地副本与解密密钥分开保存。新格式不兼容旧“两文件私密图”备份：旧备份不能直接交给新脚本，须在隔离环境使用对应旧工具恢复并补齐公开图片证据，不在生产盲目转换。

### Compose首次准备备份密钥

从仓库根目录（先完成ops构建）。示例`/学校受控密钥目录`应替换为真实绝对路径，与根`.env`的BACKUP_KEY_DIR一致；备份路径BACKUP_DIR也使用受控绝对路径。目录权限0700。

```sh
docker compose --profile ops build ops
# 一次性创建，不覆盖已有identity.txt；/keygen是临时可写挂载
docker compose --profile ops run --rm --no-deps -v /学校受控密钥目录:/keygen ops age-keygen -o /keygen/identity.txt
```

age-keygen输出的公钥填入根配置`BACKUP_AGE_RECIPIENT`，私钥identity.txt权限0600，通过学校密码库另存恢复副本。ops平时只读挂载`/keys`。加密/解密用法见 [age官方说明](https://github.com/FiloSottile/age/blob/main/README.md)。`BACKUP_SOURCE_COMMIT`填写实际部署完整提交；密钥缺失无法恢复，轮换时保留解密旧恢复点所需旧密钥。

### Compose生成同恢复点备份

仓库根目录（如有显式--env-file/项目名，所有命令保持一致）：

```sh
# 先由运维关闭全部外部入口/其他写入；以下停止本项目实例
docker compose stop api worker
docker compose --profile ops run --rm --no-deps -e BACKUP_WRITES_STOPPED=yes ops sh backup.sh
# 确认输出快照目录、两个密文和manifest存在，受控留存校验值后再恢复服务
docker compose up -d api worker
curl --fail http://127.0.0.1:8000/api/ready
```

db保持运行。ops直接挂载uploads/private_uploads命名卷为`/media/public`和`/media/private`，不猜Docker宿主机卷路径。生成的备份目录默认root持有且权限严格，宿主机查阅/复制由授权运维完成，不能为了方便改成公开可读。失败时保持停写、处理网络/磁盘/权限，重做成功快照后再决定恢复流量。

### Compose恢复到隔离新项目

从同一固定源码部署目录、使用同一明确配置文件执行。先停目标写入，保留原数据库/卷；新项目名`duxue-restore`必须尚无业务数据，与原项目不同。共享的是受控备份/密钥宿主机路径，不能把原业务命名卷接入新项目。API8000端口切换前确认原API已停止。

```sh
docker compose -p duxue-restore build api migrate worker
docker compose -p duxue-restore --profile ops build ops
docker compose -p duxue-restore up -d --wait --wait-timeout 60 db
# BACKUP_SET替换为本次选定的具体快照目录，目标空库名为shuyuan
docker compose -p duxue-restore --profile ops run --rm --no-deps -e RESTORE_WRITES_STOPPED=yes -e RESTORE_TARGET_CONFIRM=shuyuan -e BACKUP_SET=/backups/snapshot-实际编号 -e BACKUP_AGE_IDENTITY=/keys/identity.txt ops sh restore.sh
# ops恢复后文件可能为root属主，校正给API/worker的app用户
docker compose -p duxue-restore run --rm --no-deps --user root api sh -c 'chown -R app:app /app/uploads /app/private_uploads'
docker compose -p duxue-restore run --rm migrate
docker compose -p duxue-restore up -d api worker
curl --fail http://127.0.0.1:8000/api/ready
```

脚本核对POSTGRES_BACKUP_URL与DATABASE_URL的主机、端口、库名、用户相同，要求手工确认目标库名、空public schema和两个空媒体目录。先验证清单密文大小/摘要、解密两个文件、检查媒体归档路径与数据库归档，再单事务恢复数据库；不使用`--clean`直接覆盖现有库。恢复的revision须与快照一致；随后迁移是单独命令，通过同一Compose项目/配置连接该目标，避免在错误工作目录隐式连另一库。

任何失败都保持停写并保留源快照/原环境。数据库已恢复而媒体复制失败时不能启动，应查磁盘/权限；在新的空恢复目标重试，不混合已有目录或执行批量删除。验收成功后再由学校运维切换入口。这里的项目创建/切换是操作流程，脚本不会自动切生产流量。

### 直接Python/宿主机方式

不使用Docker时，在运维受控shell中设置POSTGRES_BACKUP_URL（`postgresql://`libpq格式）、BACKUP_DIR、UPLOAD_DIR、PRIVATE_UPLOAD_DIR、BACKUP_AGE_RECIPIENT、BACKUP_SOURCE_COMMIT；不要把SQLAlchemy的`postgresql+asyncpg://`交给pg_dump。密码从学校受控环境提供，避免在日志打印。

仓库根目录执行备份：停所有API/worker/导入后，`BACKUP_WRITES_STOPPED=yes sh deploy/backup.sh`。备份进程要能读取两个媒体目录并写受控备份目录。

恢复先准备新空数据库与新空媒体目录，在同一受控shell额外设置DATABASE_URL为该目标的asyncpg格式、RESTORE_TARGET_CONFIRM为目标库名、BACKUP_SET为具体快照、BACKUP_AGE_IDENTITY为私钥路径，再执行`RESTORE_WRITES_STOPPED=yes sh deploy/restore.sh`。成功后校正媒体属主给服务账号，进入backend目录，使用**同一DATABASE_URL shell环境**执行`../.venv/bin/alembic upgrade head`，启动API/worker并复核ready。脚本不会读取backend/.env，不能以为在那里填写值就自动传给备份工具。

## 恢复验收记录

每次演练记录源/目标环境（不含密码）、提交/镜像、停写时间、快照编号、schema、开始/结束时间、丢失窗口、管理员/学生虚构账号登录、订单/审计计数、公开/私密照片哈希与鉴权读取、worker心跳、重启后持久化、问题和责任人。至少季度及重大升级前复核；学校自主操作与主机重启仍需现场证据。

本地可复现演练（仓库根目录）：

```sh
docker build -t duxue-handover-local:01-02 backend
docker build -t duxue-ops-local:05-11 -f deploy/Dockerfile.ops .
python3 scripts/verify-deployment-recovery.py
```

脚本使用临时Compose项目、虚构资料、临时卷/网络/密钥，不连接学校数据库，验证首次部署、照片与数据库恢复、拒绝错误目标/坏备份/非空恢复点、API/worker与重启持久化，结束清理自己的临时资源。结果与范围见 [05–11报告](HANDOVER_DOCUMENTATION_REPORT.md)。早期01–02初始化/四场景独立复现仍可执行`python3 scripts/verify-container-handover.py`，详见 [01–02报告](REFERENCE_INITIALIZATION_REPORT.md)。

## 密钥轮换与事故响应

SECRET_KEY轮换使旧JWT失效；微信AppSecret轮换要同步API/worker并重建或重启使环境生效，再验微信绑定/消息。改根`.env`后仅`restart`不会更新既有容器环境，需`up -d --force-recreate api worker`。数据库密码变更必须同时修改数据库角色与所有连接配置，不能只改Compose文件；保留恢复通道。

敏感媒体泄露时按学校流程隔离访问、保留审计、通知安全负责人，不在公开Issue放人员资料。账号恢复本人核验、告警渠道、备份保留/清理、权利归属和维护期限由学校签字确认。
