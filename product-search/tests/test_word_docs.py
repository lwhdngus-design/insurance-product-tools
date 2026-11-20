"""Fictional Office fixtures only: native tables, link exclusion and cache refresh."""
import importlib.util
from pathlib import Path
import os
import sys
import tempfile
import unittest
import zipfile
from xml.sax.saxutils import escape

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
import word_docs
import serve


def make_docx(path, paragraphs=(), rows=()):
    def p(text):
        return '<w:p><w:r><w:t xml:space="preserve">' + escape(text) + '</w:t></w:r></w:p>'
    body = ''.join(p(text) for text in paragraphs)
    if rows:
        body += '<w:tbl>' + ''.join('<w:tr>' + ''.join('<w:tc>' + p(cell) + '</w:tc>' for cell in row) + '</w:tr>' for row in rows) + '</w:tbl>'
    document = '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>' + body + '</w:body></w:document>'
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml', '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
        z.writestr('_rels/.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
        z.writestr('word/document.xml', document)


class WordDocuments(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / '원본'
        self.root.mkdir()
        self.saved_cache, self.saved_db = serve.CACHE_DIR, serve.DB_PATH
        serve.CACHE_DIR = Path(self.temp.name) / 'cache'
        serve.DB_PATH = serve.CACHE_DIR / 'index.db'
        serve.init_db()

    def tearDown(self):
        serve.CACHE_DIR, serve.DB_PATH = self.saved_cache, self.saved_db
        self.temp.cleanup()

    def test_rows_keep_period_and_rate_together(self):
        path = self.root / '교육상품_사업방법서_수정3.docx'
        make_docx(path, ['1. 보험종목의 명칭', '교육상품'], [('경과기간', '적용이율'), ('10년 이내', '2%'), ('10년 초과', '3%')])
        result = word_docs.read_native(path)
        self.assertEqual(result['text_kind'], 'section')
        self.assertIn('10년 이내 | 2%', '\n'.join(result['pages']))
        self.assertIn('10년 초과 | 3%', '\n'.join(result['pages']))

    def test_deleted_revisions_are_not_current_text(self):
        path = self.root / '개정.docx'
        with zipfile.ZipFile(path, 'w') as z:
            z.writestr('word/document.xml', '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:del><w:r><w:delText>옛값9%</w:delText></w:r></w:del><w:ins><w:r><w:t>현재2%</w:t></w:r></w:ins></w:p></w:body></w:document>')
        text = ''.join(word_docs.read_native(path)['pages'])
        self.assertIn('현재2%', text)
        self.assertNotIn('옛값', text)

    def test_same_size_same_timestamp_content_change_reindexes(self):
        path = self.root / '교육상품_약관.docx'
        make_docx(path, ['가입금액 1000만원'])
        first = serve.list_docs(self.root)['files'][0]
        self.assertIsInstance(first['mtime'], str)
        pages = word_docs.read_native(path)
        serve.index_doc({**first, **pages, 'error': ''})
        self.assertTrue(serve.list_docs(self.root)['files'][0]['indexed'])
        before = path.stat()
        # A second same-length payload and identical timestamp must still invalidate the Word index.
        raw = path.read_bytes()
        with zipfile.ZipFile(path, 'w', zipfile.ZIP_STORED) as z:
            z.writestr('word/document.xml', 'changed')
        data = path.read_bytes()
        if len(data) < len(raw):
            with path.open('ab') as stream:
                stream.write(b'\0' * (len(raw) - len(data)))
        os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
        second = serve.list_docs(self.root)['files'][0]
        self.assertEqual(second['size'], first['size'])
        self.assertEqual(second['mtime'], first['mtime'])
        self.assertNotEqual(second['fingerprint'], first['fingerprint'])
        self.assertFalse(second['indexed'])

    def test_link_only_never_indexes_document_contents(self):
        for kind in word_docs.LINK_TYPES:
            path = self.root / (kind + '.docx')
            make_docx(path, ['분석에반영하면안되는비밀문구'])
            item = next(f for f in serve.list_docs(self.root)['files'] if kind in f['path'])
            self.assertEqual(item['fingerprint'], '')
            saved = serve.index_doc({**item, 'reader_version': word_docs.READER_VERSION, 'pages': ['분석에반영하면안되는비밀문구']})
            self.assertEqual(serve.doc_pages(saved['id']), [])
            self.assertEqual(saved['features'], {})
        self.assertEqual(serve.search_ids(['분석에반영하면안되는비밀문구']), [])

    def test_lock_files_and_symlinks_outside_root_are_excluded(self):
        make_docx(self.root / '~$열린문서.docx', ['잠금파일'])
        outside = Path(self.temp.name) / 'outside.docx'
        make_docx(outside, ['폴더밖'])
        (self.root / 'link.docx').symlink_to(outside)
        self.assertEqual(serve.list_docs(self.root)['files'], [])

    def test_failed_word_can_be_retried_after_program_install(self):
        path = self.root / '이전문서.doc'
        path.write_bytes(b'fixture')
        item = serve.list_docs(self.root)['files'][0]
        serve.index_doc({**item, 'reader_version': word_docs.READER_VERSION, 'error': 'Word not installed', 'pages': []})
        self.assertFalse(serve.list_docs(self.root)['files'][0]['indexed'])

    def test_original_file_is_unchanged_by_native_reader(self):
        path = self.root / '원문.docx'
        make_docx(path, ['보험기간 종신'])
        before = (path.read_bytes(), path.stat().st_mtime_ns)
        word_docs.read_native(path)
        self.assertEqual(before, (path.read_bytes(), path.stat().st_mtime_ns))

    def test_hwpx_table_cells_are_not_duplicated_by_outer_paragraph(self):
        path = self.root / '예전문서.hwpx'
        with zipfile.ZipFile(path, 'w') as z:
            z.writestr('Contents/section0.xml', '<s xmlns:h="urn:fixture"><h:p><h:tbl><h:tr><h:tc><h:p><h:t>10년 이내 2%</h:t></h:p></h:tc><h:tc><h:p><h:t>10년 초과 3%</h:t></h:p></h:tc></h:tr></h:tbl></h:p></s>')
        text = ''.join(word_docs.read_native(path)['pages'])
        self.assertEqual(text.count('10년 이내'), 1)
        self.assertIn('10년 초과 3%', text)


if __name__ == '__main__':
    unittest.main()
