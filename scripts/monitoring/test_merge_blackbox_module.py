"""Testes do merge_blackbox_module.py.

    python3 -m unittest scripts/monitoring/test_merge_blackbox_module.py
"""

import importlib.util
import pathlib
import unittest

import yaml

HERE = pathlib.Path(__file__).parent
spec = importlib.util.spec_from_file_location("merge_blackbox_module", HERE / "merge_blackbox_module.py")
merge_blackbox_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(merge_blackbox_module)
merge = merge_blackbox_module.merge

SNIPPET = (HERE / "blackbox-datane.yml").read_text(encoding="utf-8")
WANTED = yaml.safe_load(SNIPPET)["modules"]

# O arquivo do role ansible (ansible/roles/monitor/templates/blackbox), sem newline no fim.
SHARED = """# Compartilhado: OCA, SEDES, Atlas e Data Nordeste.
modules:
  http_2xx:
    prober: http
    timeout: 5s
    http:
      valid_status_codes: [200, 201]"""


class MergeBlackboxModuleTest(unittest.TestCase):
    def test_adds_the_module_and_keeps_the_rest_of_the_file(self):
        merged = merge(SHARED, SNIPPET)

        self.assertTrue(merged.startswith(SHARED + "\n"))
        self.assertTrue(merged.endswith("\n"))
        self.assertEqual(yaml.safe_load(merged)["modules"], {**yaml.safe_load(SHARED)["modules"], **WANTED})

    def test_keeps_comments_inside_the_shared_file(self):
        shared = SHARED.replace("prober: http\n", "prober: http  # não mexer\n", 1)

        self.assertIn("# não mexer", merge(shared, SNIPPET))
        self.assertIn("# Compartilhado", merge(shared, SNIPPET))

    def test_running_twice_changes_nothing(self):
        once = merge(SHARED, SNIPPET)

        self.assertEqual(merge(once, SNIPPET), once)

    def test_creates_the_modules_key_when_the_file_has_none(self):
        merged = merge("# vazio\n", SNIPPET)

        self.assertEqual(yaml.safe_load(merged)["modules"], WANTED)

    def test_creates_the_file_content_when_it_is_empty(self):
        self.assertEqual(yaml.safe_load(merge("", SNIPPET))["modules"], WANTED)

    def test_refuses_a_module_that_exists_with_another_definition(self):
        edited = SHARED + "\n  datane_certificado:\n    prober: tcp\n"

        with self.assertRaises(SystemExit) as raised:
            merge(edited, SNIPPET)
        self.assertIn("outra definição", str(raised.exception))

    def test_refuses_when_modules_is_not_the_last_key(self):
        # As linhas acrescentadas cairiam sob `other:`.
        with self.assertRaises(SystemExit) as raised:
            merge(SHARED + "\nother:\n  key: value\n", SNIPPET)
        self.assertIn("mudaria mais", str(raised.exception))

    def test_refuses_a_shared_file_that_is_not_valid_yaml(self):
        with self.assertRaises(SystemExit):
            merge("modules: [", SNIPPET)


if __name__ == "__main__":
    unittest.main()
