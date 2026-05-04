import unittest

import utils


class TestTemperatureHelpers(unittest.TestCase):
    def test_decode_temperature_register_uses_signed_value(self):
        self.assertEqual(utils.decode_temperature_register(0xFF9C, 1.0), -10.0)

    def test_decode_temperature_register_falls_back_to_plausible_scale(self):
        self.assertEqual(utils.decode_temperature_register(15458, 1.0), 15.458)

    def test_normalize_temperature_value_from_legacy_db_row(self):
        self.assertEqual(utils.normalize_temperature_value(15458.0), 15.458)


if __name__ == "__main__":
    unittest.main()
