"""Testes do merge_alertmanager.py.

Os casos do ruamel.yaml só rodam onde ele está instalado:

    sudo apt install python3-ruamel.yaml
    python3 -m unittest scripts/monitoring/test_merge_alertmanager.py
"""

import contextlib
import copy
import importlib.util
import io
import os
import pathlib
import unittest
from unittest import mock

import yaml

HERE = pathlib.Path(__file__).parent
spec = importlib.util.spec_from_file_location("merge_alertmanager", HERE / "merge_alertmanager.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

SNIPPET_TEXT = (HERE / "alertmanager-datane.yml").read_text(encoding="utf-8")
SNIPPET = yaml.safe_load(SNIPPET_TEXT)
HAS_RUAMEL = module.YAML is not None

# Um arquivo compartilhado com o OCA e o SEDES, com comentários de quem o edita.
SHARED_TEXT = """\
# Alertmanager da oca-monitor: OCA, SEDES e Atlas.
route:
  receiver: oca-email
  routes:
    # SEDES: não mexer
    - matchers: ['project="sedes"']
      receiver: sedes-email

inhibit_rules:
  - source_matchers: ['alertname="SedesDown"']  # nota do SEDES
    target_matchers: ['alertname="SedesSlow"']

receivers:
  - name: oca-email
  - name: sedes-email
"""
SHARED = yaml.safe_load(SHARED_TEXT)


def merged(config: dict, project: str = "datane") -> dict:
    return module.merge(copy.deepcopy(config), copy.deepcopy(SNIPPET), project)


class MergeSemanticsTest(unittest.TestCase):
    def test_puts_the_project_route_first_and_keeps_the_others(self):
        routes = merged(SHARED)["route"]["routes"]

        self.assertIn('project="datane"', routes[0]["matchers"])
        self.assertEqual(routes[1]["receiver"], "sedes-email")

    def test_appends_receivers_and_inhibitions_and_keeps_the_others(self):
        result = merged(SHARED)

        self.assertEqual([r["name"] for r in result["receivers"]], ["oca-email", "sedes-email", "datane-email", "datane-silencio"])
        self.assertEqual(result["inhibit_rules"][0], SHARED["inhibit_rules"][0])
        self.assertEqual(len(result["inhibit_rules"]), 2)

    def test_running_twice_gives_the_same_result(self):
        self.assertEqual(merged(merged(SHARED)), merged(SHARED))

    def test_does_not_crash_when_a_list_is_present_but_empty(self):
        # `routes:` sem valor volta do YAML como None.
        config = yaml.safe_load("route:\n  receiver: oca\n  routes:\ninhibit_rules:\nreceivers:\n")

        result = merged(config)

        self.assertEqual(len(result["route"]["routes"]), 1)
        self.assertEqual(len(result["receivers"]), 2)

    def test_creates_the_route_when_the_file_has_none(self):
        self.assertEqual(len(merged({"receivers": [{"name": "oca"}]})["route"]["routes"]), 1)

    def test_takes_the_project_name_as_a_parameter(self):
        snippet = yaml.safe_load(
            """
route: {matchers: ['project="sedes"'], receiver: sedes-email}
inhibit_rules:
  - source_matchers: ['alertname="SedesDown"']
    target_matchers: ['alertname="SedesSlow"']
receivers: [{name: sedes-novo}]
"""
        )
        config = {"route": {"routes": [{"matchers": ['project="sedes"'], "receiver": "velho"}]},
                  "receivers": [{"name": "sedes-velho"}, {"name": "datane-email"}],
                  "inhibit_rules": [{"source_matchers": ['alertname="SedesDown"']}]}

        result = module.merge(config, snippet, "sedes")

        self.assertEqual([r["receiver"] for r in result["route"]["routes"]], ["sedes-email"])
        self.assertEqual([r["name"] for r in result["receivers"]], ["datane-email", "sedes-novo"])
        self.assertEqual(len(result["inhibit_rules"]), 1)


@unittest.skipIf(HAS_RUAMEL, "sem o ruamel.yaml é que o script recusa")
class WithoutRuamelTest(unittest.TestCase):
    def test_refuses_to_rewrite_the_shared_file(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ALERTMANAGER_ALLOW_COMMENT_LOSS", None)
            with self.assertRaises(SystemExit) as raised:
                module.merged_text(SHARED_TEXT, SNIPPET_TEXT, "datane")

        self.assertIn("ruamel.yaml", str(raised.exception))

    def test_loses_the_comments_only_when_asked_to(self):
        with mock.patch.dict(os.environ, {"ALERTMANAGER_ALLOW_COMMENT_LOSS": "1"}), \
                contextlib.redirect_stderr(io.StringIO()) as warning:
            text = module.merged_text(SHARED_TEXT, SNIPPET_TEXT, "datane")

        self.assertEqual(yaml.safe_load(text), merged(SHARED))
        self.assertNotIn("# SEDES", text)
        self.assertIn("comentários", warning.getvalue())


@unittest.skipUnless(HAS_RUAMEL, "precisa do ruamel.yaml")
class WithRuamelTest(unittest.TestCase):
    def test_keeps_the_comments_of_the_shared_file(self):
        text = module.merged_text(SHARED_TEXT, SNIPPET_TEXT, "datane")

        self.assertIn("# Alertmanager da oca-monitor", text)
        self.assertIn("# SEDES: não mexer", text)
        self.assertIn("# nota do SEDES", text)
        self.assertEqual(yaml.safe_load(text), merged(SHARED))

    def test_running_twice_gives_the_same_text(self):
        once = module.merged_text(SHARED_TEXT, SNIPPET_TEXT, "datane")

        self.assertEqual(module.merged_text(once, SNIPPET_TEXT, "datane"), once)


if __name__ == "__main__":
    unittest.main()
