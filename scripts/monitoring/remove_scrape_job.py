#!/usr/bin/env python3
"""Tira um job do scrape_configs do prometheus.yml, mantendo o resto do texto.

Trabalha linha a linha, e não com yaml.safe_dump, para não apagar os
comentários nem reformatar o arquivo que o OCA, o Atlas e o SEDES dividem.
Se o job não existe, devolve o arquivo igual. Se o job continuaria no arquivo
depois da remoção (um formato que o script não reconhece), para com erro.

    python3 remove_scrape_job.py prometheus.yml datane > novo.yml
"""

import re
import sys

import yaml

SECTION = re.compile(r"^scrape_configs:\s*(#.*)?$")
ITEM_START = re.compile(r"^\s*-(\s|$)")


def indent_of(line: str) -> int:
    return len(line) - len(line.lstrip())


def is_content(line: str) -> bool:
    # Comentário e linha em branco não dizem onde um bloco acaba: o nano comenta
    # na coluna 0 mesmo dentro dele.
    stripped = line.strip()
    return bool(stripped) and not stripped.startswith("#")


def find_items(lines: list[str], begin: int) -> list[tuple[int, int]]:
    """Os blocos `- ...` da lista que começa em `begin`, como (primeira, fim).

    O fim é a linha seguinte à última de conteúdo: os comentários e as linhas em
    branco depois dela ficam de fora, porque pertencem ao item seguinte.
    """
    item_indent, items = None, []
    for index in range(begin, len(lines)):
        line = lines[index]
        if not is_content(line):
            continue
        starts_item = bool(ITEM_START.match(line))
        if item_indent is None:
            if not starts_item:
                break
            item_indent = indent_of(line)
        elif indent_of(line) < item_indent or (indent_of(line) == item_indent and not starts_item):
            break
        if indent_of(line) == item_indent and starts_item:
            items.append([index, index + 1])
        else:
            items[-1][1] = index + 1
    return [(first, end) for first, end in items]


def job_name_of(block: str) -> str | None:
    try:
        parsed = yaml.safe_load(block)
    except yaml.YAMLError:
        return None
    if isinstance(parsed, list) and parsed and isinstance(parsed[0], dict):
        return parsed[0].get("job_name")
    return None


def remove_job(text: str, job: str) -> str:
    lines = text.splitlines(keepends=True)
    section = next((i for i, line in enumerate(lines) if SECTION.match(line)), None)
    if section is None:
        return text

    dropped = set()
    for first, end in find_items(lines, section + 1):
        if job_name_of("".join(lines[first:end])) == job:
            dropped.update(range(first, end))
    return "".join(line for i, line in enumerate(lines) if i not in dropped)


def jobs_except(config: dict, job: str) -> dict:
    # Uma lista que ficou vazia volta do YAML como None.
    jobs = [c for c in config.get("scrape_configs") or [] if c.get("job_name") != job]
    return {**config, "scrape_configs": jobs}


def remove_scrape_job(text: str, job: str) -> str:
    after = remove_job(text, job)
    before_config, after_config = yaml.safe_load(text) or {}, yaml.safe_load(after) or {}
    # Compara o arquivo inteiro, e não só os nomes dos jobs: um corte no lugar
    # errado pode passar linhas do job removido para o vizinho sem mudar nomes.
    if jobs_except(after_config, job) != jobs_except(before_config, job):
        raise SystemExit(f"remove_scrape_job: tirar o job {job!r} mudaria mais do que ele; confira o arquivo à mão")
    if any(c.get("job_name") == job for c in after_config.get("scrape_configs") or []):
        raise SystemExit(
            f"remove_scrape_job: o job {job!r} continua no arquivo depois da remoção "
            "(formato que o script não reconhece); remova à mão"
        )
    return after


def main() -> None:
    with open(sys.argv[1], encoding="utf-8") as current:
        sys.stdout.write(remove_scrape_job(current.read(), sys.argv[2]))


if __name__ == "__main__":
    main()
