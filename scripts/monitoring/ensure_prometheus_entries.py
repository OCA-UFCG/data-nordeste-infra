#!/usr/bin/env python3
"""Garante entradas nas listas `rule_files` e `scrape_config_files` do prometheus.yml.

Trabalha no texto, para não apagar os comentários do arquivo que o OCA, o Atlas e
o SEDES dividem. Uma entrada que já está na lista (e não só num comentário) deixa
o arquivo como está. A nova entrada usa o recuo dos itens que já existem, e a
chave é acrescentada ao fim se não existir. Para com erro quando a chave está
escrita em linha (`rule_files: [a, b]`), que o script não sabe estender.

    python3 ensure_prometheus_entries.py prometheus.yml \\
        rule_files=datane/datane-alerts.yml \\
        scrape_config_files=datane/prometheus-datane.yml > novo.yml
"""

import re
import sys

import yaml

DEFAULT_INDENT = 2
ITEM_START = re.compile(r"^(\s*)-(\s|$)")


def is_content(line: str) -> bool:
    stripped = line.strip()
    return bool(stripped) and not stripped.startswith("#")


def item_indent_after(lines: list[str], key_index: int) -> int:
    """O recuo dos itens que já estão sob a chave, ou o padrão se não há nenhum."""
    for line in lines[key_index + 1 :]:
        if not is_content(line):
            continue
        item = ITEM_START.match(line)
        return len(item.group(1)) if item else DEFAULT_INDENT
    return DEFAULT_INDENT


def parse(text: str) -> dict:
    return yaml.safe_load(text) or {}


def ensure_entry(text: str, key: str, entry: str) -> str:
    config = parse(text)
    current = config.get(key) or []
    if entry in current:
        return text

    lines = text.splitlines(keepends=True)
    block_key = re.compile(rf"^{re.escape(key)}:\s*(#.*)?$")
    key_index = next((i for i, line in enumerate(lines) if block_key.match(line)), None)

    if key_index is not None:
        indent = item_indent_after(lines, key_index)
        lines.insert(key_index + 1, f'{" " * indent}- "{entry}"\n')
        updated = "".join(lines)
    elif key in config:
        raise SystemExit(f"ensure_prometheus_entries: `{key}` está escrito em linha; acrescente {entry!r} à mão")
    else:
        separator = "" if text.endswith("\n") or not text else "\n"
        updated = f'{text}{separator}\n{key}:\n  - "{entry}"\n'

    # A entrada nova vem primeiro; o resto do arquivo não pode mudar.
    result = parse(updated)
    rest = lambda cfg: {k: v for k, v in cfg.items() if k != key}
    if result.get(key) != [entry, *current] or rest(result) != rest(config):
        raise SystemExit(f"ensure_prometheus_entries: acrescentar {entry!r} em `{key}` mudaria mais do que isso; confira à mão")
    return updated


def ensure_entries(text: str, wanted: list[tuple[str, str]]) -> str:
    for key, entry in wanted:
        text = ensure_entry(text, key, entry)
    return text


def main() -> None:
    wanted = [tuple(argument.split("=", 1)) for argument in sys.argv[2:]]
    with open(sys.argv[1], encoding="utf-8") as current:
        sys.stdout.write(ensure_entries(current.read(), wanted))


if __name__ == "__main__":
    main()
