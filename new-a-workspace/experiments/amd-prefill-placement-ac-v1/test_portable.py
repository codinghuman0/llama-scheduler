import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import measure


class PortablePlacementTests(unittest.TestCase):
    def test_desktop_without_an_adapter_and_laptop_on_battery(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertIsNone(measure.ac_online(False, root))
            adapter = root / "ACAD"
            adapter.mkdir()
            (adapter / "type").write_text("Mains")
            (adapter / "online").write_text("0")
            self.assertEqual(measure.ac_online(False, root), 0)
            with self.assertRaises(RuntimeError):
                measure.ac_online(True, root)
            (adapter / "online").write_text("1")
            self.assertEqual(measure.ac_online(True, root), 1)

    def test_protocol_uses_discovered_hardware_and_preserves_the_comparison(self):
        for vendor, cpus, resources in (("Intel", [1, 3, 5, 7, 8, 9], "intel-fixed6"),
                                        ("AMD", [4, 6, 10, 12, 18], "physical")):
            policy = "fixed6" if len(cpus) == 6 else "phase-fixed"
            effective = {"cpus": cpus, "resources": resources, "policy": policy,
                         "topology": {"summary": {"cpu_model": vendor}}}
            with patch.object(measure.subprocess, "check_output", return_value=json.dumps({"effective": effective})) as doctor:
                protocol = measure.portable_protocol(Path("/fixture/build"))
            self.assertIn("--reserve-controller", doctor.call_args.args[0])
            self.assertEqual(protocol["server_cpus"], cpus)
            self.assertEqual(protocol["cpu25"]["cpu"], cpus[-1])
            self.assertEqual(protocol["policy"], policy)
            self.assertEqual(list(measure.schedule(protocol)), list(measure.schedule()))
