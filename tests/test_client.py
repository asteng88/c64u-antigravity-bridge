import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from c64u_bridge.client import C64UClient, C64UClientError
from c64u_bridge.server import MCPServerHandler, create_tool_definitions, parse_address


class TestClient(unittest.TestCase):
    def test_client_init(self):
        client = C64UClient(host="192.168.1.100", port=8080, password="secret")
        self.assertEqual(client.base_url, "http://192.168.1.100:8080/v1")
        self.assertEqual(client._headers(), {"X-Password": "secret"})

    def test_parse_address(self):
        self.assertEqual(parse_address("$0400"), 0x0400)
        self.assertEqual(parse_address("0xD020"), 0xD020)
        self.assertEqual(parse_address("1024"), 1024)
        self.assertEqual(parse_address("d800"), 0xD800)

    @patch("c64u_bridge.client.httpx.Client")
    def test_play_sid_uploads_binary_attachment_and_subtune(self, client_class):
        response = Mock()
        response.content = b'{"errors": []}'
        response.json.return_value = {"errors": []}
        client_class.return_value.__enter__.return_value.post.return_value = response

        with TemporaryDirectory() as temp_dir:
            sid_path = Path(temp_dir) / "test tune.sid"
            sid_path.write_bytes(b"PSID payload")
            result = C64UClient(host="c64u.test", password="secret").play_sid(sid_path, song=2)

        response.raise_for_status.assert_called_once_with()
        post = client_class.return_value.__enter__.return_value.post
        post.assert_called_once()
        url = post.call_args.args[0]
        kwargs = post.call_args.kwargs
        self.assertEqual(url, "http://c64u.test:80/v1/runners:sidplay")
        self.assertEqual(kwargs["content"], b"PSID payload")
        self.assertEqual(kwargs["params"], {"songnr": "2"})
        self.assertEqual(kwargs["headers"]["X-Password"], "secret")
        self.assertEqual(
            kwargs["headers"]["Content-Disposition"],
            'attachment; filename="test tune.sid"',
        )
        self.assertEqual(result["bytes_sent"], len(b"PSID payload"))

    @patch("c64u_bridge.client.httpx.Client")
    def test_play_sid_surfaces_firmware_errors(self, client_class):
        response = Mock()
        response.content = b'{"errors": ["invalid SID"]}'
        response.json.return_value = {"errors": ["invalid SID"]}
        client_class.return_value.__enter__.return_value.post.return_value = response

        with self.assertRaisesRegex(C64UClientError, "invalid SID"):
            C64UClient(host="c64u.test").play_sid(b"bad")

    def test_play_sid_rejects_invalid_subtune(self):
        with self.assertRaisesRegex(ValueError, "1 or greater"):
            C64UClient(host="c64u.test").play_sid(b"PSID", song=0)

    def test_mcp_sid_tool_is_exposed_and_dispatched(self):
        definitions = create_tool_definitions()
        tool_names = {tool["name"] for tool in definitions}
        self.assertIn("c64_play_sid", tool_names)
        self.assertIn("c64_compile_sid", tool_names)

        fake_client = Mock()
        fake_client.play_sid.return_value = {"errors": []}
        with TemporaryDirectory() as temp_dir:
            sid_path = Path(temp_dir) / "music.sid"
            sid_path.write_bytes(b"PSID")
            result = MCPServerHandler(client=fake_client).execute_tool(
                "c64_play_sid",
                {"sid_path": str(sid_path), "song": 3},
            )

        fake_client.play_sid.assert_called_once_with(sid_path, song=3)
        self.assertIn("subtune 3", result)


if __name__ == "__main__":
    unittest.main()
