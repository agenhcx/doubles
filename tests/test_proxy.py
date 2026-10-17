"""Offline regression tests for explicit proxy and connection failures."""
import argparse
import csv
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import collect_isu_seasons as isu


class ProxyIsolationTests(unittest.TestCase):
    def test_explicit_http_proxy_ignores_environment_https_proxy(self):
        with patch.dict(os.environ, {"HTTPS_PROXY": "https://127.0.0.1:18888",
                                  "HTTP_PROXY": "https://127.0.0.1:18888"}):
            sess = isu.configure_session("http://127.0.0.1:10808")
            self.assertFalse(sess.trust_env)
            merged = sess.merge_environment_settings("https://results.isu.org", {}, None, None, None)
            self.assertEqual(merged["proxies"]["https"], "http://127.0.0.1:10808")
            self.assertEqual(merged["proxies"]["http"], "http://127.0.0.1:10808")
            sess.close()

    def test_reject_bare_proxy_address(self):
        with self.assertRaisesRegex(ValueError, "--proxy"):
            isu.configure_session("127.0.0.1:10808")

    def test_network_block_fails_fast_preserves_manifest(self):
        with tempfile.TemporaryDirectory() as root:
            args = argparse.Namespace(
                out=str(Path(root) / "out"), cache=str(Path(root) / "cache"),
                proxy="http://127.0.0.1:10808", no_env_proxy=False,
                level="senior,junior", season_start=2018, season_end=2019,
                offline=False, refresh=False, timeout=5, delay=0,
            )
            with patch.object(isu, "download", side_effect=isu.DownloadFailed(
                    "ProxyError: test proxy failed", network_block=True)) as fake:
                rc = isu.run(args)
            self.assertEqual(rc, 2)
            self.assertEqual(fake.call_count, 1)
            manifest = json.loads((Path(root) / "out/manifest.json").read_text())
            self.assertEqual(manifest["source_pages_requested"], 8)
            self.assertEqual(manifest["source_pages_attempted"], 1)
            self.assertEqual(manifest["source_pages_skipped"], 7)
            self.assertEqual(manifest["source_pages_ok"], 0)
            with (Path(root) / "out/source_inventory.csv").open(encoding="utf-8-sig") as f:
                inventory = list(csv.DictReader(f))
            self.assertEqual(len(inventory), 8)
            self.assertEqual(inventory[1]["status"], "skipped_network")


if __name__ == "__main__":
    unittest.main()
