import unittest
from c64u_bridge.client import C64UClient
from c64u_bridge.server import parse_address


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


if __name__ == "__main__":
    unittest.main()
