#!/usr/bin/env python3
"""Junta o trecho de um projeto ao alertmanager.yml compartilhado da VM.

Substitui o que uma execução anterior tiver posto (a rota com project="<projeto>",
os receptores <projeto>-* e as inibições que partem de alertas <Projeto>*) e deixa
o resto do arquivo como estava. Pode rodar quantas vezes for. O nome do projeto
é o terceiro argumento (padrão: datane), para o mesmo script servir a qualquer
projeto da VM. Baseado no scripts/monitoring/merge_alertmanager.py do
OCA-UFCG/SAP-frontend.

Os comentários do arquivo (que o OCA, o Atlas e o SEDES também usam) só ficam
com o ruamel.yaml (sudo apt install python3-ruamel.yaml). Sem ele o script para,
a não ser que ALERTMANAGER_ALLOW_COMMENT_LOSS=1 aceite perdê-los.

    python3 merge_alertmanager.py alertmanager.yml alertmanager-datane.yml [projeto] > novo.yml
"""

import io
import os
import sys

import yaml

try:
    from ruamel.yaml import YAML
except ImportError:  # pragma: no cover - depende da máquina
    YAML = None


def items(container, key):
    """A lista sob `key`, criada se não existe (`routes:` sem valor volta como None)."""
    if container.get(key) is None:
        container[key] = []
    return container[key]


def drop_where(sequence, predicate) -> None:
    # No lugar e de trás para frente: com o ruamel, assim os comentários dos
    # itens que ficam continuam presos a eles.
    for index in range(len(sequence) - 1, -1, -1):
        if predicate(sequence[index]):
            del sequence[index]


def as_list(value) -> list:
    return value if isinstance(value, list) else []


def merge(config, snippet, project: str):
    matcher = f'project="{project}"'
    alert_prefix = f'alertname="{project.capitalize()}'

    if config.get("route") is None:
        config["route"] = {}
    routes = items(config["route"], "routes")
    drop_where(routes, lambda route: matcher in as_list(route.get("matchers")))
    routes.insert(0, snippet["route"])

    inhibitions = items(config, "inhibit_rules")
    drop_where(inhibitions, lambda rule: any(alert_prefix in m for m in as_list(rule.get("source_matchers"))))
    inhibitions.extend(snippet["inhibit_rules"])

    receivers = items(config, "receivers")
    drop_where(receivers, lambda receiver: str(receiver.get("name", "")).startswith(f"{project}-"))
    receivers.extend(snippet["receivers"])
    return config


def merged_text_keeping_comments(current_text: str, snippet_text: str, project: str) -> str:
    yml = YAML()
    yml.preserve_quotes = True
    yml.width = 1000
    yml.indent(mapping=2, sequence=4, offset=2)
    merged = merge(yml.load(current_text), yml.load(snippet_text), project)
    out = io.StringIO()
    yml.dump(merged, out)
    return out.getvalue()


def merged_text(current_text: str, snippet_text: str, project: str) -> str:
    expected = merge(yaml.safe_load(current_text) or {}, yaml.safe_load(snippet_text), project)

    if YAML is not None:
        text = merged_text_keeping_comments(current_text, snippet_text, project)
    elif os.environ.get("ALERTMANAGER_ALLOW_COMMENT_LOSS") == "1":
        sys.stderr.write("merge_alertmanager: sem ruamel.yaml, os comentários do alertmanager.yml serão perdidos\n")
        text = yaml.safe_dump(expected, allow_unicode=True, sort_keys=False, width=1000)
    else:
        raise SystemExit(
            "merge_alertmanager: falta o ruamel.yaml, que mantém os comentários do alertmanager.yml "
            "compartilhado (sudo apt install python3-ruamel.yaml). Para aceitar perdê-los: "
            "ALERTMANAGER_ALLOW_COMMENT_LOSS=1"
        )

    # O texto que sai tem de ser o mesmo arquivo, só com o trecho do projeto.
    if yaml.safe_load(text) != expected:
        raise SystemExit("merge_alertmanager: o resultado difere do esperado; confira o alertmanager.yml à mão")
    return text


def main() -> None:
    project = sys.argv[3] if len(sys.argv) > 3 else "datane"
    with open(sys.argv[1], encoding="utf-8") as current, open(sys.argv[2], encoding="utf-8") as snippet:
        sys.stdout.write(merged_text(current.read(), snippet.read(), project))


if __name__ == "__main__":
    main()
