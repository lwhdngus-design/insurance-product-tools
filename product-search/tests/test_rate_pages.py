"""Real SQLite query: table continuation, document isolation, existing AND semantics."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("search_server", Path(__file__).resolve().parents[1] / "serve.py")
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)


class RatePages(unittest.TestCase):
    def test_table_continuation(self):
        with tempfile.TemporaryDirectory() as folder:
            server.CACHE_DIR = Path(folder)
            server.DB_PATH = Path(folder) / "index.db"
            server.init_db()
            with server.connect() as connection:
                connection.executemany("INSERT INTO pages(doc_id,page_no,text) VALUES(?,?,?)", [
                    (1, 1, "상품 안내"), (1, 2, "적 용 이 율: 10년 이내 2%"),
                    (1, 3, "10년 초과 3%"), (1, 4, "관련 없는 조항"),
                    (2, 2, "다른 문서의 이율"),
                    (3, 1, "최저보증금리 10년 이내 1%, 10년 초과 0.5%"),
                ])
            self.assertEqual([p["page"] for p in server.pages_with([1], ["이율"])], [2])
            result = server.pages_with([1], ["이율"], neighbors=1)
            self.assertEqual([p["page"] for p in result], [1, 2, 3])
            self.assertTrue(all(p["id"] == 1 for p in result))
            self.assertEqual(server.pages_with([1], ["이율", "없는단어"], neighbors=1), [])
            self.assertEqual(server.pages_with([], ["이율"], neighbors=1), [])
            self.assertEqual([p["id"] for p in server.pages_with([1, 3], ["이율", "금리"], match_any=True)], [1, 3])


if __name__ == "__main__":
    unittest.main()
