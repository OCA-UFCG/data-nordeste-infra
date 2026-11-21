#!/usr/bin/env python3
"""Acrescenta os módulos do Data Nordeste ao blackbox-config.yml compartilhado.

Trabalha no texto, e não com yaml.safe_dump, para não apagar os comentários do
arquivo que o OCA e o SEDES também usam. Se os módulos já estão lá, iguais,
devolve o arquivo como está. Se algum existe com definição diferente, ou só uma
parte deles existe, para com erro: alguém pode ter ajustado à mão.

    python3 merge_blackbox_module.py blackbox-config.yml blackbox-datane.yml > novo.yml
"""

import sys

import yaml


def snippet_body(snippet_text: str) -> str:
    """As linhas depois de `modules:`, que é onde os módulos são acrescentados."""
    lines = snippet_text.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if line.rstrip() == "modules:":
            return "".join(lines[index + 1 :])
    raise SystemExit("merge_blackbox_module: o arquivo de módulos não tem a chave `modules:`")


def parse(text: str, origin: str) -> dict:
    try:
        return yaml.safe_load(text) or {}
    except yaml.YAMLError as error:
        raise SystemExit(f"merge_blackbox_module: {origin} não é um YAML válido: {error}")


def merge(current_text: str, snippet_text: str) -> str:
    current = parse(current_text, "o blackbox-config.yml")
    wanted = parse(snippet_text, "o arquivo de módulos")["modules"]
    existing = current.get("modules") or {}

    present = [name for name in wanted if name in existing]
    if present and any(existing[name] != wanted[name] for name in present):
        raise SystemExit(
            f"merge_blackbox_module: o módulo {present} já existe com outra definição; "
            "confira o blackbox-config.yml à mão"
        )
    if len(present) == len(wanted):
        return current_text
    if present:
        raise SystemExit(f"merge_blackbox_module: só parte dos módulos existe ({present}); confira à mão")

    merged = current_text if current_text.endswith("\n") or not current_text else current_text + "\n"
    if "modules" not in current:
        merged += "modules:\n"
    merged += snippet_body(snippet_text)
    if not merged.endswith("\n"):
        merged += "\n"

    # Se `modules:` não for a última chave do arquivo, as linhas acrescentadas
    # caem noutra chave: a conferência pega isso, e qualquer outra mudança.
    result = parse(merged, "o resultado")
    expected_modules = {**existing, **wanted}
    rest = lambda config: {key: value for key, value in config.items() if key != "modules"}
    if result.get("modules") != expected_modules or rest(result) != rest(current):
        raise SystemExit(
            "merge_blackbox_module: acrescentar os módulos mudaria mais do que eles; "
            "confira o blackbox-config.yml à mão"
        )
    return merged


def main() -> None:
    with open(sys.argv[1], encoding="utf-8") as current, open(sys.argv[2], encoding="utf-8") as snippet:
        sys.stdout.write(merge(current.read(), snippet.read()))


if __name__ == "__main__":
    main()
