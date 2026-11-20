import unittest
from backend.app.agent_tools import calculate


class CalculatorToolTests(unittest.TestCase):
    def test_basic_arithmetic(self):
        self.assertEqual(calculate("(1250 * 3) - 500")["result"], 3250)

    def test_division(self):
        self.assertEqual(calculate("10 / 4")["result"], 2.5)

    def test_rejects_python_execution(self):
        with self.assertRaises((ValueError, TypeError)):
            calculate("__import__('os').getcwd()")

    def test_rejects_names_and_attributes(self):
        with self.assertRaises((ValueError, TypeError)):
            calculate("open('/etc/passwd')")

    def test_rejects_extreme_exponents(self):
        with self.assertRaises(ValueError):
            calculate("2 ** 101")


if __name__ == "__main__":
    unittest.main()
