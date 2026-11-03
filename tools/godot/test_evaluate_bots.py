"""Evidence rejection tests; these do not simulate or certify gameplay."""
import copy
import json
import unittest

from evaluate_bots import MARKER, read_matches


class EvidenceContract(unittest.TestCase):
    def setUp(self):
        self.matches = []
        for count, seed in [(4, "46271"), (12, "81439")]:
            self.matches.append({"schema": 1, "participants": count, "policy_seed": seed,
                                 "purpose": "short-native-liveness-not-policy-promotion",
                                 "physics_frames_observed": 480,
                                 "manager_cost_usec": {"samples": 480},
                                 "eliminations": {"discarded": 0}, "roster": [{} for _ in range(count)]})

    def log(self, matches):
        return "\n".join(MARKER + json.dumps(value) for value in matches)

    def test_requires_exact_complete_nonduplicated_scenario_set(self):
        self.assertEqual(len(read_matches(self.log(self.matches))), 2)
        for broken in [[], self.matches[:1], self.matches + self.matches[:1]]:
            with self.subTest(broken=broken), self.assertRaises(ValueError):
                read_matches(self.log(broken))

    def test_rejects_missing_samples_roster_or_causal_evidence(self):
        for key, value in [("physics_frames_observed", 0), ("manager_cost_usec", {"samples": 0}),
                           ("eliminations", {"discarded": 1}), ("roster", [])]:
            broken = copy.deepcopy(self.matches)
            broken[0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                read_matches(self.log(broken))

    def test_rejects_wrong_or_malformed_identity(self):
        for key, value in [("schema", 2), ("participants", True), ("policy_seed", {}),
                           ("policy_seed", "unknown-seed"), ("purpose", "pretend-tournament")]:
            broken = copy.deepcopy(self.matches)
            broken[0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                read_matches(self.log(broken))


if __name__ == "__main__":
    unittest.main()
