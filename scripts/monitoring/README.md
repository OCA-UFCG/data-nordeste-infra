# Monitoramento do Data Nordeste

Configuração do Data Nordeste na VM de monitoramento `oca-monitor` (`34.200.5.32`), que
roda Prometheus, Alertmanager e Blackbox para o Data Nordeste, o SEDES, o Atlas e o OCA.
Os alertas vão para `datane.ufcg@gmail.com`.

| Arquivo | O que define |
|---|---|
| `prometheus-datane.yml` | O que coletar: o `/api/metrics` de prod e do failover, pelo IP, e a validade do certificado. |
| `datane-alerts.yml` | Quando é problema: site fora, serviço com problema, boletim que não abre, certificado vencendo, endereço fora. |
| `datane-alerts.test.yml` | Teste das regras com dados simulados. |
| `alertmanager-datane.yml` | Para quem vai o e-mail, com que frequência e o que é silenciado. |
| `deploy.sh` | Leva tudo para a VM. |

## Aplicar na VM

O merge **não** aplica nada: a VM só muda quando alguém roda o `deploy.sh`. Precisa de
acesso SSH à VM e do mesmo valor do secret `METRICS_TOKEN_PROD` do
`data-nordeste-frontend`.

```bash
read -rsp 'METRICS_TOKEN: ' METRICS_TOKEN && export METRICS_TOKEN
bash scripts/monitoring/deploy.sh ubuntu@34.200.5.32
```

Rodar de novo é seguro: cada arquivo é validado (`promtool`, `amtool`) antes de entrar na
VM, o arquivo anterior fica num `.bak-<data>` e, se nada mudou, nada é regravado. Se
alguém editar a configuração do Data Nordeste à mão na VM, rodar o `deploy.sh` volta ao
que está aqui.

## Testar antes

```bash
cd scripts/monitoring
docker run --rm --entrypoint promtool -v "$PWD":/w -w /w prom/prometheus:latest check rules datane-alerts.yml
docker run --rm --entrypoint promtool -v "$PWD":/w -w /w prom/prometheus:latest test rules datane-alerts.test.yml
```
