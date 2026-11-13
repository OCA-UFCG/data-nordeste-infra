#!/usr/bin/env bash
# Leva as coletas, os alertas e os e-mails do Data Nordeste para a VM de
# monitoramento (oca-monitor), que vigia prod e o failover de fora. Roda de uma
# máquina com acesso SSH à VM; pode rodar de novo sempre que um destes arquivos
# mudar. Adaptado do scripts/monitoring/deploy.sh do OCA-UFCG/SAP-frontend.
#
#   read -rsp 'METRICS_TOKEN: ' METRICS_TOKEN && export METRICS_TOKEN
#   bash scripts/monitoring/deploy.sh ubuntu@34.200.5.32
#
# O `read -s` não mostra o token na tela nem o grava no histórico do shell.
#
# O METRICS_TOKEN é o mesmo do secret METRICS_TOKEN_PROD do
# data-nordeste-frontend, que vai para os containers. Sem ele, fica o token que
# já estiver na VM. Ele segue pela entrada do SSH, e não pela linha de comando,
# para não aparecer na lista de processos.
#
# A VM é compartilhada com o SEDES, o Atlas e o OCA. Isto só acrescenta: um
# diretório datane/ ao Prometheus e uma rota project="datane" ao Alertmanager.
# A única coisa que tira é o job `datane` antigo, que este substitui.
set -euo pipefail

TARGET="${1:?Informe o destino SSH, ex.: ubuntu@34.200.5.32}"
HERE="$(cd "$(dirname "$0")" && pwd)"

ssh "$TARGET" 'rm -rf /tmp/datane-monitoring && mkdir -m 700 /tmp/datane-monitoring'
scp -q "$HERE"/{prometheus-datane.yml,datane-alerts.yml,alertmanager-datane.yml,merge_alertmanager.py,remove_scrape_job.py,install-on-monitor.sh} \
  "$TARGET":/tmp/datane-monitoring/
printf '%s' "${METRICS_TOKEN:-}" |
  ssh "$TARGET" 'sudo bash /tmp/datane-monitoring/install-on-monitor.sh; status=$?; rm -rf /tmp/datane-monitoring; exit $status'
