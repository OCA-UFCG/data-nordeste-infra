#!/usr/bin/env python3
"""Tira um job do scrape_configs do prometheus.yml, mantendo o resto do texto.

Trabalha linha a linha, e não com yaml.safe_dump, para não apagar os
comentários nem reformatar o arquivo que o OCA, o Atlas e o SEDES dividem.
Se o job não existe, devolve o arquivo igual.

    python3 remove_scrape_job.py prometheus.yml datane > novo.yml
"""

import re
import sys

import yaml


def remove_job(text: str, job: str) -> str:
    start = re.compile(rf"^(\s*)- job_name:\s*[\"']?{re.escape(job)}[\"']?\s*$")
    kept, indent = [], None
    for line in text.splitlines(keepends=True):
        match = start.match(line)
        if match:
            indent = len(match.group(1))
            continue
        content = line.strip()
        # Um comentário pode estar na coluna 0 mesmo dentro do bloco (o nano
        # comenta assim): ele não diz onde o bloco acaba.
        if indent is not None and content and not content.startswith("#"):
            # O bloco acaba na primeira linha que não está mais funda que o
            # "- job_name": o próximo item da lista ou a chave seguinte.
            if len(line) - len(line.lstrip()) <= indent:
                indent = None
        if indent is None:
            kept.append(line)
    return "".join(kept)


def jobs_except(config: dict, job: str) -> dict:
    # Uma lista que ficou vazia volta do YAML como None.
    jobs = [c for c in config.get("scrape_configs") or [] if c["job_name"] != job]
    return {**config, "scrape_configs": jobs}


def main() -> None:
    path, job = sys.argv[1], sys.argv[2]
    with open(path, encoding="utf-8") as current:
        before = current.read()
    after = remove_job(before, job)
    # Compara o arquivo inteiro, e não só os nomes dos jobs: um corte no lugar
    # errado pode passar linhas do job removido para o vizinho sem mudar nomes.
    if jobs_except(yaml.safe_load(after), job) != jobs_except(yaml.safe_load(before), job):
        sys.exit(f"remove_scrape_job: tirar o job {job!r} mudaria mais do que ele; confira o arquivo à mão")
    sys.stdout.write(after)


if __name__ == "__main__":
    main()
