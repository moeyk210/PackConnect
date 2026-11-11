import hashlib
import tempfile
import unittest
from pathlib import Path

from scripts.migrate import migration_digests


class MigrationDigestTests(unittest.TestCase):
    def digests_for(self, content):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "m.sql"
            path.write_bytes(content)
            return migration_digests(path)

    def test_line_endings_do_not_change_migration_identity(self):
        lf_digest, lf_accepted = self.digests_for(b"BEGIN;\nSELECT 1;\nCOMMIT;\n")
        crlf_digest, crlf_accepted = self.digests_for(b"BEGIN;\r\nSELECT 1;\r\nCOMMIT;\r\n")
        self.assertEqual(lf_digest, crlf_digest)
        self.assertEqual(lf_accepted, crlf_accepted)
        # Histories recorded from either checkout style remain valid.
        self.assertIn(hashlib.sha256(b"BEGIN;\nSELECT 1;\nCOMMIT;\n").hexdigest(), lf_accepted)
        self.assertIn(hashlib.sha256(b"BEGIN;\r\nSELECT 1;\r\nCOMMIT;\r\n").hexdigest(), lf_accepted)

    def test_content_changes_are_still_detected(self):
        _, accepted = self.digests_for(b"SELECT 1;\n")
        changed, _ = self.digests_for(b"SELECT 2;\n")
        self.assertNotIn(changed, accepted)


if __name__ == "__main__":
    unittest.main()
