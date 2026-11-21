"""Testes do ensure_prometheus_entries.py.

    python3 -m unittest scripts/monitoring/test_ensure_prometheus_entries.py
"""

import importlib.util
import pathlib
import unittest

import yaml

spec = importlib.util.spec_from_file_location(
    "ensure_prometheus_entries", pathlib.Path(__file__).parent / "ensure_prometheus_entries.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
ensure_entry, ensure_entries = module.ensure_entry, module.ensure_entries

ENTRY = "datane/datane-alerts.yml"


def listed(text: str, key: str = "rule_files") -> list:
    return yaml.safe_load(text)[key]


class EnsurePrometheusEntriesTest(unittest.TestCase):
    def test_inserts_under_a_bare_key(self):
        text = 'rule_files:\n  - "prometheus-alerts.yml"\nscrape_configs: []\n'

        self.assertEqual(listed(ensure_entry(text, "rule_files", ENTRY)), [ENTRY, "prometheus-alerts.yml"])

    def test_inserts_under_a_key_with_a_trailing_comment(self):
        text = 'rule_files:  # OCA\n  - "prometheus-alerts.yml"\n'

        after = ensure_entry(text, "rule_files", ENTRY)

        self.assertEqual(listed(after), [ENTRY, "prometheus-alerts.yml"])
        self.assertIn("# OCA", after)

    def test_follows_the_indentation_of_the_existing_items(self):
        text = 'rule_files:\n    - "prometheus-alerts.yml"\n'

        self.assertEqual(listed(ensure_entry(text, "rule_files", ENTRY)), [ENTRY, "prometheus-alerts.yml"])
        self.assertIn('    - "datane/datane-alerts.yml"', ensure_entry(text, "rule_files", ENTRY))

    def test_follows_a_list_indented_like_its_key(self):
        text = 'rule_files:\n- "prometheus-alerts.yml"\n'

        self.assertEqual(listed(ensure_entry(text, "rule_files", ENTRY)), [ENTRY, "prometheus-alerts.yml"])

    def test_adds_the_key_when_it_is_missing(self):
        text = "global:\n  scrape_interval: 15s"

        after = ensure_entry(text, "rule_files", ENTRY)

        self.assertEqual(listed(after), [ENTRY])
        self.assertEqual(yaml.safe_load(after)["global"], {"scrape_interval": "15s"})

    def test_uses_the_default_indent_under_an_empty_key(self):
        self.assertEqual(listed(ensure_entry("rule_files:\nglobal: {}\n", "rule_files", ENTRY)), [ENTRY])

    def test_a_commented_out_entry_does_not_count(self):
        text = f'rule_files:\n  # - "{ENTRY}"\n  - "prometheus-alerts.yml"\n'

        self.assertEqual(listed(ensure_entry(text, "rule_files", ENTRY)), [ENTRY, "prometheus-alerts.yml"])

    def test_an_entry_already_listed_changes_nothing_even_unquoted(self):
        text = f"rule_files:\n  - {ENTRY}\n"

        self.assertEqual(ensure_entry(text, "rule_files", ENTRY), text)

    def test_running_twice_changes_nothing(self):
        once = ensure_entries("rule_files:\nscrape_configs: []\n", [("rule_files", ENTRY), ("scrape_config_files", "datane/p.yml")])

        self.assertEqual(ensure_entries(once, [("rule_files", ENTRY), ("scrape_config_files", "datane/p.yml")]), once)

    def test_keeps_the_comments_of_the_file(self):
        text = '# do OCA\nrule_files:\n  - "a.yml"  # não mexer\n'

        after = ensure_entry(text, "rule_files", ENTRY)

        self.assertIn("# do OCA", after)
        self.assertIn("# não mexer", after)

    def test_refuses_a_key_written_in_flow_style(self):
        with self.assertRaises(SystemExit) as raised:
            ensure_entry('rule_files: ["a.yml"]\n', "rule_files", ENTRY)
        self.assertIn("em linha", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
