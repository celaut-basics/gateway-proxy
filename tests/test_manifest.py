"""Packer-facing checks that do not need a node."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICE_JSON = ROOT / ".service" / "service.json"
DOCKERFILE = ROOT / ".service" / "Dockerfile"
PACK_CONFIG = ROOT / ".service" / "pack_config.json"


def _rewrite_copy_sources(line: str) -> str:
    """Same rule as nodo prepare_directory.__dockerfile_copy_from."""
    stripped = line.strip()
    if not stripped.startswith("COPY "):
        return line
    parts = stripped.split()
    flags = [p for p in parts[1:] if p.startswith("--")]
    if len(parts) >= 3 and not any(f.startswith("--from") for f in flags):
        start = 1
        while start < len(parts) and parts[start].startswith("--"):
            start += 1
        for j in range(start, len(parts) - 1):
            if parts[j].startswith("."):
                parts[j] = "service" + parts[j][1:]
        return " ".join(parts)
    return stripped


class ManifestTests(unittest.TestCase):
    def test_service_json_is_object_json(self):
        data = json.loads(SERVICE_JSON.read_text())
        self.assertEqual(data["architecture"], "linux/amd64")
        self.assertEqual(data["tag"], "gateway-proxy")
        self.assertEqual(data["init"]["entry_path"], ["service", "entrypoint.py"])
        self.assertEqual(data["api"][0]["port"], 4040)
        self.assertEqual(data["api"][0]["transport"], "tcp")
        self.assertEqual(data["network"][0]["tags"], ["*"])
        self.assertTrue(data["network"][0]["prose"])
        self.assertGreaterEqual(data["resources"]["at_init"]["mem_limit"], 128000000)
        self.assertGreaterEqual(data["resources"]["at_init"]["disk_space"], 128000000)

    def test_pack_config_includes_only_service(self):
        data = json.loads(PACK_CONFIG.read_text())
        self.assertEqual(data["include"], ["service"])
        self.assertIn("tests/", data["ignore"])

    def test_dockerfile_copy_sources_start_with_dot(self):
        copies = [
            line
            for line in DOCKERFILE.read_text().splitlines()
            if line.strip().startswith("COPY ")
        ]
        self.assertTrue(copies)
        for line in copies:
            parts = line.strip().split()
            start = 1
            while start < len(parts) and parts[start].startswith("--"):
                start += 1
            for src in parts[start:-1]:
                if src.startswith("--from"):
                    continue
                self.assertTrue(
                    src.startswith("."),
                    "COPY source %r must start with '.' so the packer "
                    "rewrites it into .service/service/" % (src,),
                )

    def test_rewritten_copy_lands_on_the_included_tree(self):
        rewritten = _rewrite_copy_sources("COPY ./service /service")
        self.assertEqual(rewritten, "COPY service/service /service")
        # Without the dot the packer leaves the source as context-relative
        # `.service/service`, which is the whole project tree, not /service/*.py.
        self.assertEqual(_rewrite_copy_sources("COPY service /service"), "COPY service /service")


if __name__ == "__main__":
    unittest.main()
