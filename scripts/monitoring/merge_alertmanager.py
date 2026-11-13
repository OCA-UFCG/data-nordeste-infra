#!/usr/bin/env python3
"""Junta o trecho do Data Nordeste ao alertmanager.yml compartilhado da VM.

Substitui o que uma execução anterior tiver posto (a rota com
project="datane", os receptores datane-* e as inibições que partem de alertas
Datane*) e deixa o resto do arquivo como estava. Pode rodar quantas vezes for.
Cópia do scripts/monitoring/merge_alertmanager.py do OCA-UFCG/SAP-frontend.

    python3 merge_alertmanager.py alertmanager.yml alertmanager-datane.yml > novo.yml
"""

import sys

import yaml

DATANE_MATCHER = 'project="datane"'


def is_datane_route(route: dict) -> bool:
    return DATANE_MATCHER in route.get("matchers", [])


def is_datane_inhibition(rule: dict) -> bool:
    return any('alertname="Datane' in m for m in rule.get("source_matchers", []))


def merge(config: dict, datane: dict) -> dict:
    root = config.setdefault("route", {})
    routes = [r for r in root.get("routes", []) if not is_datane_route(r)]
    root["routes"] = [datane["route"], *routes]

    inhibitions = [r for r in config.get("inhibit_rules", []) if not is_datane_inhibition(r)]
    config["inhibit_rules"] = inhibitions + datane["inhibit_rules"]

    receivers = [r for r in config.get("receivers", []) if not r["name"].startswith("datane-")]
    config["receivers"] = receivers + datane["receivers"]
    return config


def main() -> None:
    with open(sys.argv[1], encoding="utf-8") as current, open(sys.argv[2], encoding="utf-8") as snippet:
        merged = merge(yaml.safe_load(current), yaml.safe_load(snippet))
    yaml.safe_dump(merged, sys.stdout, allow_unicode=True, sort_keys=False, width=1000)


if __name__ == "__main__":
    main()
