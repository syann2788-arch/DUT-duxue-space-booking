"""Isolated Git/ZIP tests; never read school configuration or alter this repo."""
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import zipfile

from package_handover import CONFIGS, GUIDES, ROOT, digest, forbidden_path, inventory, json_bytes, pack, read_zip, verify, zip_bytes


class HandoverTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='duxue-package-test-')
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.repo = self.base / 'repo'
        self.repo.mkdir()
        for name in GUIDES + CONFIGS:
            target = self.repo / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text('Synthetic handover fixture\n')
        (self.repo / 'package.json').write_text('{"version":"0.1.0-rc.1"}\n')
        (self.repo / 'miniprogram').mkdir()
        for name, content in {'app.js': 'App({})', 'app.json': '{}', 'config.js': 'module.exports={}', 'build.config.js': 'module.exports={}', 'utils/api.js': 'module.exports={}'}.items():
            target = self.repo / 'miniprogram' / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
        (self.repo / 'project.config.json').write_text('{"appid":"wx78c441ce72d765fc","miniprogramRoot":"miniprogram/"}')
        scripts = self.repo / 'scripts'
        scripts.mkdir()
        for name in ['build-miniprogram.mjs', 'verify-miniprogram-build.mjs']:
            shutil.copyfile(ROOT / 'scripts' / name, scripts / name)
        self.git('init', '-q')
        self.git('config', 'user.name', 'Synthetic Test')
        self.git('config', 'user.email', 'test@example.invalid')
        self.commit()
        self.git('update-ref', 'refs/remotes/origin/main', 'HEAD')

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.repo), *args], stderr=subprocess.PIPE).decode().strip()

    def commit(self):
        self.git('add', '.')
        self.git('commit', '-qm', 'Synthetic handover fixture')

    def create(self, name='package', **kwargs):
        return pack(self.repo, output=self.base / name, **kwargs)

    def test_fixed_git_export_and_repeatable_bytes(self):
        (self.repo / '.gitignore').write_text('.env\nbackend/.env\n*.db\n')
        self.commit()
        self.git('update-ref', 'refs/remotes/origin/main', 'HEAD')
        (self.repo / '.env').write_text('UNTRACKED_SECRET=synthetic-do-not-export')
        (self.repo / 'backend/.env').write_text('UNTRACKED_SECRET=synthetic-do-not-export')
        (self.repo / 'backend/synthetic.db').write_text('do not export')
        left, right = self.create('left'), self.create('right')
        self.assertEqual(verify(left)['sourceCommit'], self.git('rev-parse', 'HEAD'))
        self.assertEqual({p.name: p.read_bytes() for p in left.iterdir()}, {p.name: p.read_bytes() for p in right.iterdir()})
        members = read_zip((left / 'source.zip').read_bytes())
        self.assertIn('source/.env.example', members)
        self.assertNotIn('source/.env', members)
        self.assertNotIn('source/backend/synthetic.db', members)
        self.assertFalse(any(b'synthetic-do-not-export' in value for value in members.values()))
        with self.assertRaises(ValueError):
            self.create('left')

    def test_dirty_and_unmerged_ref_are_refused_and_draft_is_explicit(self):
        (self.repo / 'README.md').write_text('uncommitted change')
        with self.assertRaises(ValueError): self.create()
        self.commit()
        with self.assertRaises(subprocess.CalledProcessError): self.create()
        target = self.create(draft=True)
        self.assertEqual(verify(target)['status'], 'draft-before-main-review')

    def test_tracked_secrets_database_and_symlink_are_refused(self):
        for name in ['.env', 'backend/live.db', 'staff.csv', 'backup-keys/private.key']:
            self.assertTrue(forbidden_path(name))
        path = self.repo / '.env'
        path.write_text('synthetic sensitive fixture')
        self.commit()
        with self.assertRaises(ValueError): self.create(draft=True)
        path.unlink()
        (self.repo / 'external').symlink_to('/tmp')
        self.commit()
        with self.assertRaises(ValueError): self.create(draft=True)

    def test_tag_mismatch_is_refused(self):
        self.git('tag', 'v0.1.0-rc.1')
        (self.repo / 'README.md').write_text('later change')
        self.commit()
        with self.assertRaises(ValueError): self.create(draft=True)

    def test_missing_modified_extra_files_are_detected(self):
        target = self.create()
        source = target / 'source.zip'
        original = source.read_bytes()
        source.write_bytes(original + b'tampered')
        with self.assertRaises(ValueError): verify(target)
        source.write_bytes(original)
        extra = target / 'extra.txt'
        extra.write_text('unexpected')
        with self.assertRaises(ValueError): verify(target)
        extra.unlink()
        source.unlink()
        with self.assertRaises(ValueError): verify(target)

    def test_unsafe_duplicate_and_symlink_zip_members_are_refused(self):
        for name in ['../escape', '/absolute', 'x\\evil', 'C:drive', 'a//b']:
            with self.assertRaises(ValueError): read_zip(zip_bytes({name: b'bad'}))
        with self.assertRaises(ValueError): read_zip(zip_bytes({'link': b'/tmp'}, {'link': 0o120777}))
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as archive:
            archive.writestr('same', b'one')
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter('ignore', UserWarning)
                archive.writestr('same', b'two')
        with self.assertRaises(ValueError): read_zip(stream.getvalue())

    def test_embedded_source_mismatch_is_detected_even_with_outer_checksums_updated(self):
        target = self.create()
        manifest = json.loads((target / 'handover-manifest.json').read_bytes())
        materials = read_zip((target / 'handover.zip').read_bytes())
        materials['source.zip'] = b'substituted source'
        outer = zip_bytes(materials)
        (target / 'handover.zip').write_bytes(outer)
        manifest['handoverFiles'] = inventory(materials)
        archives = {name: (target / name).read_bytes() for name in ['source.zip', 'handover.zip']}
        manifest['archives'] = inventory(archives)
        (target / 'handover-manifest.json').write_bytes(json_bytes(manifest))
        archives['handover-manifest.json'] = json_bytes(manifest)
        (target / 'SHA256SUMS').write_text(''.join(f'{digest(data)}  {name}\n' for name, data in sorted(archives.items())))
        with self.assertRaises(ValueError): verify(target)

    def test_optional_wechat_build_uses_same_commit_and_is_repeatable(self):
        import os
        from unittest.mock import patch
        with patch.dict(os.environ, {'MINIPROGRAM_APP_ID': 'wx78c441ce72d765fc', 'MINIPROGRAM_API_BASE_URL': 'https://synthetic.example.invalid/api'}):
            left, right = self.create('left', miniprogram=True), self.create('right', miniprogram=True)
        self.assertTrue(verify(left)['hasMiniprogramBuild'])
        self.assertEqual((left / 'miniprogram.zip').read_bytes(), (right / 'miniprogram.zip').read_bytes())
        self.assertEqual((left / 'handover.zip').read_bytes(), (right / 'handover.zip').read_bytes())

    def test_production_cannot_use_rc_draft_or_missing_acceptance(self):
        with self.assertRaises(ValueError): self.create(kind='production')
        (self.repo / 'package.json').write_text('{"version":"0.1.0"}')
        self.commit()
        with self.assertRaises(ValueError): self.create(kind='production', draft=True, miniprogram=True)
        with self.assertRaises(ValueError): self.create(kind='production', miniprogram=True)


if __name__ == '__main__':
    unittest.main(verbosity=2)
