"""Decode a celaut.ConfigurationFile that protoc wrote.

The hand-rolled encoder in wire.py can drift from the proto. This fixture was
produced with:

    protoc --encode=celaut.ConfigurationFile -I <nodo>/protos celaut.proto

against celaut-project/nodo dev @ 698e6583. If a live tree is present, the
test encodes again and compares.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "service"))

from config import environment_variables, gateway_uris  # noqa: E402

# gateway { uri_slot { internal_port: 4041, uri { ip: "192.168.200.1" port: 4041 } } }
# config { environment_variables { key: "TARGET" value: "1.2.3.4:4040" } }
PROTOC_FIXTURE = bytes.fromhex(
    "0a19121708c91f12120a0d3139322e3136382e3230302e3110c91f"
    "12180a160a06544152474554120c312e322e332e343a34303430"
)

TEXTPB = """\
gateway {
  uri_slot {
    internal_port: 4041
    uri { ip: "192.168.200.1" port: 4041 }
  }
}
config {
  environment_variables { key: "TARGET" value: "1.2.3.4:4040" }
}
"""

NODO_PROTOS = Path.home() / "celaut-audit" / "nodo" / "protos"


class ProtocFixtureTests(unittest.TestCase):
    def test_checked_in_fixture_matches_the_decoder(self):
        self.assertEqual(
            gateway_uris(PROTOC_FIXTURE),
            [("192.168.200.1", 4041)],
        )
        self.assertEqual(
            environment_variables(PROTOC_FIXTURE),
            {"TARGET": "1.2.3.4:4040"},
        )

    @unittest.skipUnless(
        shutil.which("protoc") and (NODO_PROTOS / "celaut.proto").is_file(),
        "protoc or nodo protos not on this host",
    )
    def test_live_protoc_encode_matches_the_fixture(self):
        with tempfile.NamedTemporaryFile("w", suffix=".txtpb", delete=False) as handle:
            handle.write(TEXTPB)
            text_path = handle.name
        try:
            with open(text_path, "rb") as text:
                encoded = subprocess.check_output(
                    [
                        "protoc",
                        "--encode=celaut.ConfigurationFile",
                        "-I",
                        str(NODO_PROTOS),
                        "celaut.proto",
                    ],
                    stdin=text,
                )
        finally:
            os.unlink(text_path)
        self.assertEqual(encoded, PROTOC_FIXTURE)
        self.assertEqual(gateway_uris(encoded), [("192.168.200.1", 4041)])
        self.assertEqual(
            environment_variables(encoded),
            {"TARGET": "1.2.3.4:4040"},
        )


if __name__ == "__main__":
    unittest.main()
