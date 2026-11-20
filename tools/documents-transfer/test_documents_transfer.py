import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
import zipfile

SCRIPT = Path(__file__).with_name('documents_transfer.py')
spec = importlib.util.spec_from_file_location('transfer', SCRIPT)
transfer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(transfer)


def snapshot(folder):
    return {p.relative_to(folder).as_posix(): (p.read_bytes(), p.stat().st_mtime_ns) for p in folder.rglob('*') if p.is_file()}


class TransferTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.parent = Path(self.temp.name) / '공백과 한글 경로'
        self.source = self.parent / 'product-documents'
        self.source.mkdir(parents=True)

    def tearDown(self):
        self.temp.cleanup()

    def add(self, relative, content):
        p = self.source / relative
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(content)

    def test_independent_zip_archives_and_exact_round_trip(self):
        for i in range(7):
            self.add(f'판매중/2026.11.20/상품{i}/[약관] 문서.pdf', os.urandom(28000))
        self.add('download_log.csv', '상품명,저장경로\n한글상품,C:\\원본\\약관.pdf\n'.encode('utf-8-sig'))
        self.add('비어있는파일.txt', b'')
        before = snapshot(self.source)
        out = transfer.pack(self.source, 65000)
        m = json.loads((out / 'manifest.json').read_text())
        self.assertGreater(len(m['archives']), 1)
        self.assertEqual(m['split_files'], 0)
        names = []
        for item in m['archives']:
            p = out / item['name']
            self.assertLessEqual(p.stat().st_size, 65000)
            with zipfile.ZipFile(p) as z:
                self.assertIsNone(z.testzip())
                names.extend(z.namelist())
                self.assertTrue(all(n.startswith('product-documents/') for n in z.namelist()))
        self.assertEqual(len(names), len(before))
        restored = transfer.restore(out / 'manifest.json') / 'product-documents'
        self.assertEqual({k: v[0] for k, v in before.items()}, {k: v[0] for k, v in snapshot(restored).items()})
        self.assertEqual(snapshot(self.source), before)
        again = transfer.pack(self.source, 65000)
        self.assertNotEqual(out, again)
        self.assertTrue(out.is_dir())

    def test_oversized_file_automatically_split_and_reassembled(self):
        self.add('판매중지/아주 큰 상품.pdf', os.urandom(220000))
        self.add('작은파일.pdf', b'%PDF-' + b'abc' * 10000)
        before = snapshot(self.source)
        out = transfer.pack(self.source, 65000)
        m = json.loads((out / 'manifest.json').read_text())
        self.assertEqual(m['split_files'], 1)
        self.assertTrue(all((out / a['name']).stat().st_size <= 65000 for a in m['archives']))
        result = transfer.restore(out / 'manifest.json') / 'product-documents'
        self.assertEqual({k: v[0] for k, v in snapshot(result).items()}, {k: v[0] for k, v in before.items()})
        self.assertEqual(snapshot(self.source), before)

    def test_corruption_and_missing_archive_are_detected_before_restore(self):
        self.add('문서.pdf', os.urandom(40000))
        out = transfer.pack(self.source, 65000)
        part = next(out.glob('*.zip'))
        data = bytearray(part.read_bytes()); data[len(data) // 2] ^= 1
        part.write_bytes(data)
        with self.assertRaisesRegex(ValueError, '손상'):
            transfer.restore(out / 'manifest.json')
        self.assertFalse(list(out.glob('restored-*')))
        part.unlink()
        with self.assertRaises(FileNotFoundError):
            transfer.restore(out / 'manifest.json')

    def test_path_traversal_is_rejected(self):
        self.add('문서.pdf', b'%PDF-test')
        out = transfer.pack(self.source, 65000)
        p = out / 'manifest.json'
        m = json.loads(p.read_text());m['files'][0]['path'] = '../escape.pdf'
        p.write_text(json.dumps(m))
        with self.assertRaisesRegex(ValueError, '경로'):
            transfer.restore(p)
        self.assertFalse((out.parent / 'escape.pdf').exists())
        self.assertTrue(list(out.glob('restored-*/INCOMPLETE.txt')))

    def test_empty_source_and_symlink_do_not_create_output(self):
        with self.assertRaisesRegex(ValueError, '없습니다'):
            transfer.pack(self.source)
        external = self.parent / 'external.pdf';external.write_bytes(b'outside')
        (self.source / 'shortcut.pdf').symlink_to(external)
        with self.assertRaisesRegex(ValueError, '연결'):
            transfer.pack(self.source)
        self.assertFalse(list(self.parent.glob('product-documents-transfer-*')))

    def test_source_changed_during_pack_fails_without_manifest(self):
        self.add('문서.pdf', b'first')
        original_finish = transfer.sha256
        def mutate(path):
            value = original_finish(path)
            (self.source / '새파일.pdf').write_bytes(b'new')
            return value
        transfer.sha256 = mutate
        try:
            with self.assertRaisesRegex(ValueError, '변경'):
                transfer.pack(self.source, 65000)
        finally:
            transfer.sha256 = original_finish
        out = next(self.parent.glob('product-documents-transfer-*'))
        self.assertTrue((out / 'INCOMPLETE.txt').is_file())
        self.assertFalse((out / 'manifest.json').exists())

    def test_existing_education_pdf_bytes_survive(self):
        sample = next((SCRIPT.parents[2] / 'product-search/sample-기초서류폴더').rglob('*.pdf'))
        self.add('교육용 가상상품/약관.pdf', sample.read_bytes())
        out = transfer.pack(self.source, 65000)
        result = transfer.restore(out / 'manifest.json') / 'product-documents/교육용 가상상품/약관.pdf'
        self.assertEqual(hashlib.sha256(sample.read_bytes()).hexdigest(), transfer.sha256(result))

    def test_public_download_matches_sources_and_has_no_pc_path(self):
        bundle = SCRIPT.parents[2] / 'downloads/documents-transfer-500MB.zip'
        with zipfile.ZipFile(bundle) as archive:
            self.assertIsNone(archive.testzip())
            self.assertEqual(len(archive.namelist()), 3)
            for name in ('documents_transfer.py', '1_pack_490MB.bat', 'README.txt'):
                content = archive.read('documents-transfer-500MB/' + name)
                self.assertEqual(content, SCRIPT.with_name(name).read_bytes())
                self.assertNotIn(b'C:\\Users\\', content)


if __name__ == '__main__':
    with contextlib.redirect_stdout(io.StringIO()):
        unittest.main(verbosity=2)
