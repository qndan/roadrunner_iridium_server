import unittest

from roadrunner_iridium_server.simulator import Simulator
from roadrunner_iridium_server.results import LoadModelResult

BASIC_TESTING_MODEL = """
A + $Z -> B; k1*A
B -> C; k2*B
k1 = 0.35; k2 = 0.2
B = 0; C = 0
A = 10
$Z = 15
"""

class TestSession(unittest.TestCase):
    def test_get_model_info(self):
        simulator = Simulator()
        simulator.load_code(BASIC_TESTING_MODEL)
        result = simulator.get_model_info()
        self.assertEqual(
            result,
            LoadModelResult(
                floating_species={ "A": 10, "B": 0, "C": 0 },
                boundary_species={ "Z": 15 },
                reactions=["_J0", "_J1"],
                parameters={ "k1": 0.35, "k2": 0.2 },
            )
        )

    def test_load_code_throws(self):
        simulator = Simulator()
        self.assertRaises(ValueError, simulator.load_code, "abcaweofkoakk aokoefkawofko")
