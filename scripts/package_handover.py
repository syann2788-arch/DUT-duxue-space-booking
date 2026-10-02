"""Export a fixed Git tree as reproducible, independently verifiable handover ZIPs.

Uses only the Python standard library; Node is needed for optional WeChat builds
and production acceptance-record validation. Never reads live .env or databases.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
GUIDES = ['README.md', 'CHANGELOG.md', 'ROADMAP.md', 'CONTRIBUTING.md', 'SECURITY.md', 'SUPPORT.md', 'CODE_OF_CONDUCT.md', 'AGENTS.md', 'CLAUDE.md', 'docs/HANDOVER_GUIDE.md', 'docs/USER_GUIDE.md', 'docs/DEPLOYMENT_GUIDE.md', 'docs/WECHAT_SETUP.md', 'docs/OPERATIONS_RUNBOOK.md', 'docs/BUILD_ARTIFACT_GUIDE.md', 'docs/PROJECT_FILE_GUIDE.md', 'docs/RELEASE_CHECKLIST.md', 'docs/PILOT_RELEASE_BASELINE.md']
CONFIGS = ['.env.example', 'backend/.env.example', 'docker-compose.yml', 'project.config.json', 'deploy/nginx.conf', 'deploy/duxue-api.service.example', 'deploy/duxue-worker.service.example']
MAX_BYTES = 256 * 1024 * 1024


def digest(data):
    return hashlib.sha256(data).hexdigest()


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode()


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], stderr=subprocess.PIPE)


def safe_path(name):
    return bool(name) and '\\' not in name and '\x00' not in name and not name.startswith('/') and ':' not in name and all(part not in ('', '.', '..') for part in name.split('/'))


def forbidden_path(name):
    parts = PurePosixPath(name.lower()).parts
    base = parts[-1]
    if any(part in {'.git', '.venv', 'node_modules', '__pycache__', '.pytest_cache', 'backups', 'backup-keys', 'uploads', 'private_uploads', 'credentials', 'dist'} for part in parts):
        return True
    if base == 'project.private.config.json' or base.startswith('.env') and base != '.env.example':
        return True
    if base.endswith(('.db', '.sqlite', '.sqlite3', '.log', '.zip', '.age', '.pem', '.key', '.p12', '.docx')):
        return True
    return base.endswith('.csv') and not base.endswith('.example.csv')


def inventory(files):
    return [{'path': name, 'size': len(files[name]), 'sha256': digest(files[name])} for name in sorted(files)]


def zip_bytes(files, modes=None):
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = ((modes or {}).get(name, 0o100644) << 16)
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, files[name], compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return output.getvalue()


def read_zip(data):
    files = {}
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        members = archive.infolist()
        if len(members) > 10000 or sum(info.file_size for info in members) > MAX_BYTES:
            raise ValueError('ZIP exceeds handover limits')
        for info in members:
            if not safe_path(info.filename) or info.filename in files or info.is_dir() or (info.external_attr >> 16) & 0o170000 not in (0, 0o100000):
                raise ValueError('Unsafe, duplicate or unsupported ZIP member')
            files[info.filename] = archive.read(info)
    return files


def snapshot(root, ref):
    commit = git(root, 'rev-parse', '--verify', '--end-of-options', f'{ref}^{{commit}}').decode().strip()
    files, modes, objects = {}, {}, []
    for entry in git(root, 'ls-tree', '-rz', '--full-tree', commit).split(b'\0'):
        if not entry:
            continue
        metadata, name = entry.split(b'\t', 1)
        mode, kind, oid = metadata.decode().split()
        name = name.decode('utf8')
        if kind != 'blob' or mode not in ('100644', '100755') or not safe_path(name) or forbidden_path(name):
            raise ValueError(f'Git tree contains a prohibited path or file type: {name}')
        objects.append((name, oid))
        modes[name] = int(mode, 8)
    # Batch reads immutable blobs, never the working-tree copies or untracked data.
    result = subprocess.run(['git', '-C', str(root), 'cat-file', '--batch'], input=''.join(oid + '\n' for _, oid in objects).encode(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    stream = io.BytesIO(result.stdout)
    for name, _ in objects:
        header = stream.readline().decode().split()
        size = int(header[2])
        files[name] = stream.read(size)
        if stream.read(1) != b'\n':
            raise ValueError('Invalid Git blob response')
    if sum(map(len, files.values())) > MAX_BYTES:
        raise ValueError('Source exceeds handover limit')
    return commit, files, modes


def pack(root=ROOT, ref='HEAD', output=None, draft=False, miniprogram=False, kind='candidate', acceptance=None):
    if kind not in {'candidate', 'production'}:
        raise ValueError('Unknown handover kind')
    if git(root, 'status', '--porcelain').strip():
        raise ValueError('Working tree must be clean; commit changes before exporting')
    commit, files, modes = snapshot(root, ref)
    version = json.loads(files['package.json'])['version']
    pattern = r'\d+\.\d+\.\d+-rc\.\d+' if kind == 'candidate' else r'\d+\.\d+\.\d+'
    if not re.fullmatch(pattern, version):
        raise ValueError('Candidate requires -rc.N; production requires a stable version')
    if kind == 'production' and (draft or not acceptance or not miniprogram):
        raise ValueError('Production requires acceptance, a WeChat build, and cannot be draft')
    if not draft:
        subprocess.run(['git', '-C', str(root), 'merge-base', '--is-ancestor', commit, 'origin/main'], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    missing = [name for name in GUIDES + CONFIGS if name not in files]
    if missing:
        raise ValueError('Missing handover documents/configuration: ' + ', '.join(missing))
    tag = 'v' + version
    existing = git(root, 'tag', '--list', tag).decode().strip()
    if existing:
        if git(root, 'rev-parse', f'refs/tags/{tag}^{{commit}}').decode().strip() != commit:
            raise ValueError('Version tag points to a different commit')
    else:
        tag = None
    record = {'schemaVersion': 1, 'version': version, 'sourceCommit': commit, 'tag': tag, 'kind': kind, 'status': 'draft-before-main-review' if draft else 'pending-school-deployment-acceptance' if kind == 'candidate' else 'production-materials-with-declared-acceptance', 'automaticallyPublished': False, 'automaticallyDeployed': False, 'schoolAcceptance': 'pending' if kind == 'candidate' else 'record-completeness-checked', 'formalDirectories': ['miniprogram/', 'backend/'], 'historicalDirectories': ['frontend/', 'cloudfunctions/'], 'hasMiniprogramBuild': miniprogram}
    archives = {'source.zip': zip_bytes({'source/' + name: data for name, data in files.items()}, {'source/' + name: mode for name, mode in modes.items()})}
    with tempfile.TemporaryDirectory(prefix='duxue-handover-') as temporary:
        stage = Path(temporary)
        for name, data in files.items():
            target = stage / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        if kind == 'production':
            for name in ['student-space-guide.png', 'student-my-reservations.png', 'admin-review.png']:
                if f'docs/assets/screenshots/{name}' not in files:
                    raise ValueError('Production requires actual redacted screenshots')
            checker = "import fs from 'node:fs'; import {validateAcceptance} from './scripts/release-check.mjs'; const errors=validateAcceptance(JSON.parse(fs.readFileSync(process.argv[1],'utf8')),process.argv[2],process.argv[3]); if(errors.length) {console.error(errors.join('\\n')); process.exit(1)}"
            checked = subprocess.run(['node', '--input-type=module', '-e', checker, str(Path(acceptance).resolve()), version, commit], cwd=stage, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            # A mistaken .env/credential path may make JSON.parse include its
            # contents in a diagnostic. Never echo that controlled input.
            if checked.returncode:
                raise ValueError('验收记录未通过；请用正式发布检查核对结构与完整性')
        if miniprogram:
            env = dict(os.environ, RELEASE_VERSION=version, GIT_COMMIT=commit)
            subprocess.run(['node', 'scripts/build-miniprogram.mjs', 'production'], cwd=stage, env=env, check=True, stdout=subprocess.DEVNULL)
            built = stage / 'dist/miniprogram-production'
            manifest = json.loads((built / 'build-manifest.json').read_text())
            # Avoid a wall-clock timestamp making otherwise identical ZIPs differ.
            epoch = int(git(root, 'show', '-s', '--format=%ct', commit).decode())
            from datetime import datetime, timezone
            manifest['createdAt'] = datetime.fromtimestamp(epoch, timezone.utc).isoformat().replace('+00:00', 'Z')
            # Preserve object-field order expected by the Node schema-2 verifier.
            (built / 'build-manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
            subprocess.run(['node', 'scripts/verify-miniprogram-build.mjs', str(built)], cwd=stage, check=True, stdout=subprocess.DEVNULL)
            build_files = {path.relative_to(built).as_posix(): path.read_bytes() for path in built.rglob('*') if path.is_file()}
            archives['miniprogram.zip'] = zip_bytes(build_files)
    materials = {name: files[name] for name in GUIDES + CONFIGS}
    materials.update({name: data for name, data in files.items() if name.startswith('docs/')})
    materials.update(archives)
    materials['handover-record.json'] = json_bytes(record)
    materials['HANDOVER_RECEIPT.md'] = f'# 交付接收登记\n\n版本：{version}；提交：{commit}；状态：{record["status"]}\n\n| 项目 | 接收时填写 |\n|---|---|\n| 接收单位/负责人角色 | 待确认 |\n| 交付/接收日期、包校验结论 | 待确认 |\n| 服务器与微信管理员 | 待确认 |\n| 维护期限、支持范围、联系方式 | 待双方书面约定 |\n| 密钥受控交接记录编号 | 单独受控登记，不填写密钥 |\n| 学校部署/业务验收结论 | 待执行 |\n'.encode()
    materials['START_HERE.md'] = f'# {version} 交付材料\n\n源码提交：{commit}\n状态：{record["status"]}\n\n1. 在外层运行交付校验工具，核对两份ZIP和manifest；通过独立渠道核对SHA256SUMS。\n2. 解压source.zip得到source/，从source/README.md和docs/HANDOVER_GUIDE.md开始。这里也附有教程副本与配置模板。\n3. 按角色阅读使用、部署、微信和备份恢复教程。填写HANDOVER_RECEIPT.md，约定维护期限。\n4. {'miniprogram.zip是构建目录包，仍须微信开发者工具上传和平台审核。' if miniprogram else '未附学校微信构建包；配置AppID、HTTPS API后从固定源码构建。'}\n\n本包没有自动创建Release或部署服务器。候选源码接收不等于学校正式验收。真实密钥、账号密码、数据和照片通过学校受控渠道单独交接。\n'.encode()
    archives['handover.zip'] = zip_bytes(materials)
    manifest = {'schemaVersion': 1, 'digestAlgorithm': 'sha256', 'record': record, 'sourceFiles': inventory(files), 'handoverFiles': inventory(materials), 'archives': inventory(archives)}
    target = Path(output) if output else root / 'dist/handover' / f'{version}-{commit[:12]}'
    if target.exists():
        raise ValueError('Output already exists; never overwrite an earlier handover')
    target.parent.mkdir(parents=True, exist_ok=True)
    # Everything is prepared and validated before creating the output directory.
    target.mkdir()
    try:
        for name, data in archives.items():
            (target / name).write_bytes(data)
        (target / 'handover-manifest.json').write_bytes(json_bytes(manifest))
        checksummed = dict(archives, **{'handover-manifest.json': json_bytes(manifest)})
        (target / 'SHA256SUMS').write_text(''.join(f'{digest(checksummed[name])}  {name}\n' for name in sorted(checksummed)))
        verify(target)
    except Exception:
        import shutil
        shutil.rmtree(target)
        raise
    return target


def verify(directory):
    directory = Path(directory)
    manifest_bytes = (directory / 'handover-manifest.json').read_bytes()
    manifest = json.loads(manifest_bytes)
    if manifest.get('schemaVersion') != 1 or manifest.get('digestAlgorithm') != 'sha256':
        raise ValueError('Unsupported handover manifest')
    record = manifest['record']
    kind = record.get('kind')
    version_pattern = r'\d+\.\d+\.\d+-rc\.\d+' if kind == 'candidate' else r'\d+\.\d+\.\d+'
    statuses = {'draft-before-main-review', 'pending-school-deployment-acceptance'} if kind == 'candidate' else {'production-materials-with-declared-acceptance'}
    if kind not in {'candidate', 'production'} or not re.fullmatch(version_pattern, record['version']) or record.get('status') not in statuses or not isinstance(record.get('hasMiniprogramBuild'), bool) or record.get('tag') not in (None, 'v' + record['version']):
        raise ValueError('Invalid handover phase/version/tag')
    if not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', record['sourceCommit']) or record.get('automaticallyPublished') is not False or record.get('automaticallyDeployed') is not False:
        raise ValueError('Invalid handover provenance')
    names = [item['path'] for item in manifest['archives']]
    if set(names) != ({'source.zip', 'handover.zip', 'miniprogram.zip'} if record['hasMiniprogramBuild'] else {'source.zip', 'handover.zip'}) or len(names) != len(set(names)):
        raise ValueError('Invalid archive inventory')
    if {path.name for path in directory.iterdir()} != set(names) | {'handover-manifest.json', 'SHA256SUMS'} or any(not path.is_file() or path.is_symlink() for path in directory.iterdir()):
        raise ValueError('Unexpected, missing or unsafe handover files')
    archives = {name: (directory / name).read_bytes() for name in names}
    if inventory(archives) != manifest['archives']:
        raise ValueError('Archive checksum/size mismatch')
    expected_sums = ''.join(f'{digest(data)}  {name}\n' for name, data in sorted(dict(archives, **{'handover-manifest.json': manifest_bytes}).items()))
    if (directory / 'SHA256SUMS').read_text() != expected_sums:
        raise ValueError('SHA256SUMS mismatch')
    source = read_zip(archives['source.zip'])
    if any(not name.startswith('source/') or forbidden_path(name[7:]) for name in source):
        raise ValueError('Source contains prohibited paths')
    source = {name[7:]: data for name, data in source.items()}
    if inventory(source) != manifest['sourceFiles'] or json.loads(source['package.json'])['version'] != record['version']:
        raise ValueError('Source inventory/version mismatch')
    if any(name not in source for name in GUIDES + CONFIGS):
        raise ValueError('Source lacks required handover materials')
    materials = read_zip(archives['handover.zip'])
    if inventory(materials) != manifest['handoverFiles'] or materials.get('source.zip') != archives['source.zip'] or json.loads(materials['handover-record.json']) != record:
        raise ValueError('Handover material inventory/provenance mismatch')
    if any(materials.get(name) != source[name] for name in GUIDES + CONFIGS):
        raise ValueError('Handover guides/templates differ from source')
    if record['hasMiniprogramBuild']:
        if materials.get('miniprogram.zip') != archives['miniprogram.zip']:
            raise ValueError('Embedded WeChat ZIP differs')
        build = read_zip(archives['miniprogram.zip'])
        metadata = json.loads(build['build-manifest.json'])
        if metadata['commit'] != record['sourceCommit'] or metadata['version'] != record['version'] or metadata['environment'] != 'production':
            raise ValueError('WeChat build provenance mismatch')
        with tempfile.TemporaryDirectory(prefix='duxue-build-check-') as temporary:
            stage = Path(temporary)
            for name, data in build.items():
                (stage / name).parent.mkdir(parents=True, exist_ok=True)
                (stage / name).write_bytes(data)
            expected_source = {name: data for name, data in source.items() if name == 'project.config.json' or name.startswith('miniprogram/')}
            if metadata.get('sourceFiles') != inventory(expected_source):
                raise ValueError('WeChat build source inventory differs from source ZIP')
            # Execute the already trusted local verifier, never code read from
            # the archive being checked. The extracted build contains data only.
            subprocess.run(['node', str(ROOT / 'scripts/verify-miniprogram-build.mjs'), str(stage)], check=True, stdout=subprocess.DEVNULL)
    return record


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    export = commands.add_parser('pack')
    export.add_argument('--ref', default='HEAD')
    export.add_argument('--output', type=Path)
    export.add_argument('--draft', action='store_true', help='Local pre-review artifact; not an approved delivery')
    export.add_argument('--miniprogram', action='store_true')
    export.add_argument('--kind', choices=['candidate', 'production'], default='candidate')
    export.add_argument('--acceptance', type=Path)
    check = commands.add_parser('verify')
    check.add_argument('directory', type=Path)
    args = parser.parse_args()
    try:
        if args.command == 'pack':
            target = pack(ref=args.ref, output=args.output, draft=args.draft, miniprogram=args.miniprogram, kind=args.kind, acceptance=args.acceptance)
            print(f'交付包生成并校验通过: {target}')
        else:
            record = verify(args.directory)
            print(f'交付包校验通过: {record["version"]} {record["sourceCommit"]} {record["status"]}')
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError, zipfile.BadZipFile) as error:
        parser.exit(1, f'交付包操作失败: {error}\n')
