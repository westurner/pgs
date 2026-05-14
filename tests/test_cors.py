import unittest
import webtest
import pgs.app


class TestCors(unittest.TestCase):
    def setUp(self):
        conf = {"pgs.root_path": ".", "pgs.cors": "https://example.com"}
        self.app = webtest.TestApp(pgs.app.make_app(conf))

    def test_cors_headers_get(self):
        rsp = self.app.get("/")
        self.assertIn("Access-Control-Allow-Origin", rsp.headers)
        self.assertEqual(
            rsp.headers["Access-Control-Allow-Origin"], "https://example.com"
        )
        self.assertEqual(
            rsp.headers["Access-Control-Allow-Methods"],
            "GET, POST, PUT, DELETE, OPTIONS",
        )

    def test_cors_headers_options(self):
        rsp = self.app.options("/")
        self.assertIn("Access-Control-Allow-Origin", rsp.headers)
        self.assertEqual(
            rsp.headers["Access-Control-Allow-Origin"], "https://example.com"
        )
        self.assertEqual(
            rsp.headers["Access-Control-Allow-Methods"],
            "GET, POST, PUT, DELETE, OPTIONS",
        )
        self.assertEqual(rsp.status_code, 200)


class TestCorsNotEnabled(unittest.TestCase):
    def setUp(self):
        conf = {"pgs.root_path": "."}
        self.app = webtest.TestApp(pgs.app.make_app(conf))

    def test_no_cors_headers(self):
        rsp = self.app.get("/")
        self.assertNotIn("Access-Control-Allow-Origin", rsp.headers)
