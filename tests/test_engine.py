import unittest
from pathlib import Path
from src.engine.stockfish_client import StockfishClient


class TestEngine(unittest.TestCase):
    def test_stockfish_client_creation_and_state(self):
        client = StockfishClient(binary_path=Path("non_existent_stockfish"))
        self.assertFalse(client.available)
        self.assertEqual(client.skill_level, 10)


if __name__ == "__main__":
    unittest.main()
