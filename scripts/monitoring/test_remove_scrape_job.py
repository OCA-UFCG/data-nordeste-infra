"""Testes do remove_scrape_job.py.

    python3 -m unittest scripts/monitoring/test_remove_scrape_job.py
"""

import importlib.util
import pathlib
import unittest

import yaml

spec = importlib.util.spec_from_file_location("remove_scrape_job", pathlib.Path(__file__).parent / "remove_scrape_job.py")
remove_scrape_job_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(remove_scrape_job_module)
remove_scrape_job = remove_scrape_job_module.remove_scrape_job

NEIGHBOR = """\

  # SEDES – não mexer
  - job_name: sedes-x
    static_configs:
      - targets: [localhost:9100]
"""


def config(job_block: str, tail: str = NEIGHBOR) -> str:
    return "global:\n  scrape_interval: 15s\nscrape_configs:\n" + job_block + tail


def names(text: str) -> list[str]:
    return [c["job_name"] for c in yaml.safe_load(text)["scrape_configs"] or []]


class RemoveScrapeJobTest(unittest.TestCase):
    def test_removes_the_job_and_leaves_the_neighbor_byte_for_byte(self):
        job = "  - job_name: datane\n    metrics_path: /probe\n"

        after = remove_scrape_job(config(job), "datane")

        self.assertEqual(after, config("", NEIGHBOR))

    def test_removes_a_job_name_followed_by_a_comment(self):
        job = "  - job_name: datane  # blackbox /health\n    metrics_path: /probe\n"

        self.assertEqual(names(remove_scrape_job(config(job), "datane")), ["sedes-x"])

    def test_removes_a_job_whose_name_is_not_the_first_key(self):
        job = "  - metrics_path: /probe\n    job_name: datane\n    scrape_interval: 5m\n"

        self.assertEqual(names(remove_scrape_job(config(job), "datane")), ["sedes-x"])

    def test_removes_a_quoted_job_name(self):
        self.assertEqual(names(remove_scrape_job(config('  - job_name: "datane"\n'), "datane")), ["sedes-x"])

    def test_removes_a_job_written_in_flow_style(self):
        job = "  - {job_name: datane, metrics_path: /probe}\n"

        self.assertEqual(names(remove_scrape_job(config(job), "datane")), ["sedes-x"])

    def test_keeps_the_blank_line_and_comment_that_belong_to_the_next_job(self):
        after = remove_scrape_job(config("  - job_name: datane\n    metrics_path: /probe\n"), "datane")

        self.assertIn("\n\n  # SEDES – não mexer\n", after)

    def test_drops_a_comment_in_column_zero_inside_the_job(self):
        job = "  - job_name: datane\n# nano comenta assim\n    metrics_path: /probe\n"

        after = remove_scrape_job(config(job), "datane")

        self.assertNotIn("nano comenta", after)
        self.assertEqual(names(after), ["sedes-x"])

    def test_handles_a_list_indented_like_its_key(self):
        text = "scrape_configs:\n- job_name: datane\n  metrics_path: /probe\n- job_name: sedes-x\n"

        self.assertEqual(remove_scrape_job(text, "datane"), "scrape_configs:\n- job_name: sedes-x\n")

    def test_handles_four_space_indentation(self):
        text = "scrape_configs:\n    - job_name: datane\n      metrics_path: /probe\n    - job_name: sedes-x\n"

        self.assertEqual(names(remove_scrape_job(text, "datane")), ["sedes-x"])

    def test_leaves_the_file_alone_when_the_job_does_not_exist(self):
        text = config("  - job_name: outro\n")

        self.assertEqual(remove_scrape_job(text, "datane"), text)

    def test_leaves_the_file_alone_without_scrape_configs(self):
        self.assertEqual(remove_scrape_job("global: {}\n", "datane"), "global: {}\n")

    def test_stops_when_the_job_would_remain_in_a_format_it_does_not_recognize(self):
        # Lista em linha: não há blocos `- ...` para o script reconhecer.
        text = "scrape_configs: [{job_name: datane}, {job_name: sedes-x}]\n"

        with self.assertRaises(SystemExit) as raised:
            remove_scrape_job(text, "datane")
        self.assertIn("continua no arquivo", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
