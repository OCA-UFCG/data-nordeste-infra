# Monitoramento do Data Nordeste

Configuração do Data Nordeste na VM de monitoramento `oca-monitor` (`34.200.5.32`), que
roda Prometheus, Alertmanager e Blackbox para o Data Nordeste, o SEDES, o Atlas e o OCA.
Os alertas vão para `datane.ufcg@gmail.com`.

| Arquivo | O que define |
|---|---|
| `prometheus-datane.yml` | O que coletar: o `/api/metrics` de prod e do failover, pelo IP, e a validade do certificado. |
| `datane-alerts.yml` | Quando é problema: site fora, serviço com problema, boletim que não abre, certificado vencendo, endereço fora, prod sem dados dos serviços. |
| `datane-alerts.test.yml` | Teste das regras com dados simulados. |
| `alertmanager-datane.yml` | Para quem vai o e-mail, com que frequência e o que é silenciado. |
| `blackbox-datane.yml` | O módulo `datane_certificado` do blackbox, que mede a validade do certificado mesmo vencido e não segue redirect. O `deploy.sh` o acrescenta ao `blackbox-config.yml` da VM (`$MONITOR_HOME/blackbox/`, ou o caminho em `BLACKBOX_YML`). |
| `deploy.sh` | Leva tudo para a VM. |
| `install-on-monitor.sh` | A parte que roda na VM: valida, grava e recarrega. |
| `merge_alertmanager.py`, `merge_blackbox_module.py`, `remove_scrape_job.py`, `ensure_prometheus_entries.py` | Mexem nos arquivos compartilhados da VM no texto, sem apagar os comentários dos outros times. Têm testes (`test_*.py`). |

## Aplicar na VM

O merge **não** aplica nada: a VM só muda quando alguém roda o `deploy.sh`. Precisa de
acesso SSH à VM e do mesmo valor do secret `METRICS_TOKEN_PROD` do
`data-nordeste-frontend`. **O site novo (com `/api/metrics`) precisa estar no ar antes**:
o instalador testa o token contra os servidores e não troca o que funciona se ele for
recusado.

```bash
read -rsp 'METRICS_TOKEN: ' METRICS_TOKEN && export METRICS_TOKEN
bash scripts/monitoring/deploy.sh ubuntu@34.200.5.32
```

Na VM, uma vez: `sudo apt install python3-ruamel.yaml`. Sem ele o instalador se recusa a
reescrever o `alertmanager.yml` compartilhado, porque perderia os comentários dos outros
times. Para aceitar a perda: `ALERTMANAGER_ALLOW_COMMENT_LOSS=1 bash scripts/monitoring/deploy.sh ...`.

Rodar de novo é seguro: cada arquivo é validado (`promtool`, `amtool`, `blackbox_exporter
--config.check`) antes de entrar na VM, o arquivo anterior fica num `.bak-<data>` (o token
também) e, se nada mudou, nada é regravado. Se alguém editar a configuração do Data
Nordeste à mão na VM, rodar o `deploy.sh` volta ao que está aqui.

### Como o Prometheus é recriado (só na primeira vez)

O container precisa montar a pasta `datane/`. O instalador olha as labels do container:

- **Criado pelo `docker-compose.yml` da VM:** edita o compose e roda `docker compose up -d
  prometheus`. Antes de tocar em qualquer coisa, confere que o container não tem mounts
  que o compose desconhece (de outro projeto, por exemplo) e para se tiver.
- **Criado de outro jeito (`docker run`):** recria com `docker run`, copiando do container
  as variáveis, os aliases de rede, as opções de log, o IP das portas e a política de
  restart.

Se algo falhar ou o script for interrompido (erro, Ctrl-C, SSH que cai) no meio da troca,
o `prometheus.yml` e o compose voltam ao que eram e o Prometheus antigo é religado. Se o
container está rodando mas ainda não respondeu `/-/ready` em 5 min (replay do WAL de uma
VM com muitos dados), o instalador avisa e **não desfaz**.

## Testar antes

```bash
cd scripts/monitoring
python3 -m unittest test_merge_blackbox_module.py test_remove_scrape_job.py test_ensure_prometheus_entries.py test_merge_alertmanager.py
docker run --rm --entrypoint promtool -v "$PWD":/w -w /w prom/prometheus:latest check rules datane-alerts.yml
docker run --rm --entrypoint promtool -v "$PWD":/w -w /w prom/prometheus:latest test rules datane-alerts.test.yml
```

Os casos do `ruamel.yaml` em `test_merge_alertmanager.py` só rodam onde ele está
instalado (`sudo apt install python3-ruamel.yaml`).

## O role Ansible `monitor`

O role (`ansible/roles/monitor`, `make ansible-monitor`) monta a base de uma VM de
monitoramento **nova** e termina rodando o mesmo `install-on-monitor.sh` do `deploy.sh`,
então rodar o role de novo não desfaz o Data Nordeste. Para ele, defina `metrics_token`
(com `-e` ou `ansible-vault`) e, onde os servidores de prod não respondem (Vagrant),
`datane_skip_token_check: true`.

**Não rode o role na `oca-monitor`.** Ela é compartilhada com o SEDES e o Atlas, e o role
reescreve `prometheus.yml`, `alertmanager.yml` e o compose com o conteúdo do OCA, que não
conhece o que eles puseram lá. Para a `oca-monitor`, é o `deploy.sh`.
