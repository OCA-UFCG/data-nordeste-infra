#!/usr/bin/env bash
# Parte do deploy.sh que roda na VM de monitoramento, com sudo, a partir da
# cópia dos arquivos em /tmp/datane-monitoring. Lê o METRICS_TOKEN da entrada.
# Adaptado do scripts/monitoring/install-on-monitor.sh do OCA-UFCG/SAP-frontend.
#
# Os arquivos de configuração entram nos containers como bind mount de um
# arquivo só, que segue o inode: por isso eles são sobrescritos com `cat >`,
# e nunca trocados por `sed -i` ou `mv`, que criam um arquivo novo que o
# container não enxergaria.
#
# IMPORTANT: nada entra numa pasta ou arquivo que o container lê antes de passar
# pelo promtool/amtool. Uma regra quebrada na pasta datane/ faz o Prometheus
# recusar o próximo reload (inclusive o do SEDES) e não subir no próximo reboot,
# deixando todos os projetos da VM sem monitoramento.
set -euo pipefail
cd "$(dirname "$0")"

# Fora da VM, só para ensaiar o script contra containers locais.
MONITOR_HOME="${MONITOR_HOME:-/home/ubuntu}"
PROMETHEUS_YML="$MONITOR_HOME/prometheus/prometheus.yml"
DATANE_DIR="$MONITOR_HOME/prometheus/datane"
ALERTMANAGER_YML="$MONITOR_HOME/alertmanager/alertmanager.yml"
TOKEN_FILE="$DATANE_DIR/metrics-token"

# Os temporários podem ter o alertmanager.yml inteiro, com a senha do SMTP.
staging="$(mktemp -d)"
updated_prometheus_yml="$(mktemp)"
updated_alertmanager_yml="$(mktemp)"
trap 'rm -rf "$staging" "$updated_prometheus_yml" "$updated_alertmanager_yml"' EXIT

install -d -m 755 "$DATANE_DIR"
token="$(cat)"
if [ -n "$token" ]; then
  (umask 077 && printf '%s' "$token" > "$TOKEN_FILE")
fi
if [ ! -s "$TOKEN_FILE" ]; then
  echo "Falta o METRICS_TOKEN: rode o deploy.sh com METRICS_TOKEN=..." >&2
  exit 1
fi
# O umask só vale quando o arquivo é criado.
chmod 600 "$TOKEN_FILE"

# --- Alertmanager -----------------------------------------------------------
# Primeiro: se ele falhasse depois do Prometheus, os alertas Datane já
# disparariam e cairiam na rota padrão, para as caixas do OCA.

python3 merge_alertmanager.py "$ALERTMANAGER_YML" alertmanager-datane.yml > "$updated_alertmanager_yml"
docker run --rm --user root --entrypoint amtool -v "$updated_alertmanager_yml":/check.yml:ro \
  prom/alertmanager:latest check-config /check.yml

if ! cmp -s "$updated_alertmanager_yml" "$ALERTMANAGER_YML"; then
  cp "$ALERTMANAGER_YML" "$ALERTMANAGER_YML.bak-$(date +%Y%m%d%H%M%S)"
  cat "$updated_alertmanager_yml" > "$ALERTMANAGER_YML"
  curl -fsS -X POST http://localhost:9093/-/reload
fi

# --- Prometheus: arquivos ---------------------------------------------------

# O job `datane` antigo (blackbox em datanordeste-portal.com/health, editado à
# mão em 10–11/11/2026) dá lugar ao datane-certificado do prometheus-datane.yml.
python3 remove_scrape_job.py "$PROMETHEUS_YML" datane > "$updated_prometheus_yml"
if ! grep -q 'datane/datane-alerts.yml' "$updated_prometheus_yml"; then
  sed -i 's|^rule_files:$|&\n  - "datane/datane-alerts.yml"|' "$updated_prometheus_yml"
fi
if ! grep -q 'datane/prometheus-datane.yml' "$updated_prometheus_yml"; then
  if grep -q '^scrape_config_files:$' "$updated_prometheus_yml"; then
    sed -i 's|^scrape_config_files:$|&\n  - "datane/prometheus-datane.yml"|' "$updated_prometheus_yml"
  else
    printf '\nscrape_config_files:\n  - "datane/prometheus-datane.yml"\n' >> "$updated_prometheus_yml"
  fi
fi
# O sed acima não faz nada se o arquivo não tiver uma linha `rule_files:`
# sozinha; sem esta conferência, os alertas ficariam de fora em silêncio.
for entry in datane/datane-alerts.yml datane/prometheus-datane.yml; do
  if ! grep -q "$entry" "$updated_prometheus_yml"; then
    echo "Não consegui incluir $entry no prometheus.yml; confira o arquivo à mão." >&2
    exit 1
  fi
done

# Valida a pasta inteira como o Prometheus a verá: o prometheus.yml novo e a
# pasta datane/ nova por cima da atual. Como root, para ler os tokens. Sem o
# lint de regras duplicadas: o prometheus-alerts.yml do OCA já repete o
# InstanceDown.
install -m 644 prometheus-datane.yml datane-alerts.yml "$staging"/
install -m 600 "$TOKEN_FILE" "$staging"/metrics-token
docker run --rm --user root --entrypoint promtool \
  -v "$MONITOR_HOME/prometheus":/etc/prometheus:ro \
  -v "$staging":/etc/prometheus/datane:ro \
  -v "$updated_prometheus_yml":/etc/prometheus/prometheus.yml:ro \
  prom/prometheus:latest check config --lint=none /etc/prometheus/prometheus.yml

install -m 644 "$staging"/prometheus-datane.yml "$staging"/datane-alerts.yml "$DATANE_DIR"/
if ! cmp -s "$updated_prometheus_yml" "$PROMETHEUS_YML"; then
  # Quem roda vê exatamente o que mudou no arquivo que todos dividem.
  diff -u "$PROMETHEUS_YML" "$updated_prometheus_yml" || true
  cp "$PROMETHEUS_YML" "$PROMETHEUS_YML.bak-$(date +%Y%m%d%H%M%S)"
  cat "$updated_prometheus_yml" > "$PROMETHEUS_YML"
fi

# --- Prometheus: container --------------------------------------------------

inspect() { docker inspect prometheus --format "$1" | sed '/^$/d'; }

restore_old_prometheus() {
  echo "O Prometheus novo não subiu; voltando o antigo. Ele não enxerga a pasta" \
    "datane/, então o Data Nordeste fica sem monitoramento até o próximo deploy." >&2
  docker rm -f prometheus >/dev/null 2>&1 || true
  docker rename prometheus-antes-do-datane prometheus
  docker start prometheus
  exit 1
}

if inspect '{{range .Mounts}}{{.Destination}}{{println}}{{end}}' | grep -q '^/etc/prometheus/datane$'; then
  curl -fsS -X POST http://localhost:9090/-/reload
else
  # Primeira vez: o container não monta o diretório datane/. Ele é recriado com
  # tudo o que o atual tem (lido do próprio container, para não perder o sedes/
  # nem o que outro projeto tiver acrescentado) e mais esse. Os dados ficam no
  # volume. O antigo só é apagado depois que o novo sobe.
  mapfile -t mounts < <(inspect '{{range .Mounts}}{{if eq .Type "volume"}}{{.Name}}{{else}}{{.Source}}{{end}}:{{.Destination}}{{if not .RW}}:ro{{end}}{{println}}{{end}}')
  mapfile -t args < <(inspect '{{range .Args}}{{println .}}{{end}}')
  mapfile -t networks < <(inspect '{{range $name, $_ := .NetworkSettings.Networks}}{{$name}}{{println}}{{end}}')
  mapfile -t ports < <(inspect '{{range $port, $bindings := .HostConfig.PortBindings}}{{(index $bindings 0).HostPort}}:{{$port}}{{println}}{{end}}')
  user="$(inspect '{{.Config.User}}')"
  image="$(inspect '{{.Config.Image}}')"

  # O `docker run` só aceita uma rede; com mais, o container novo perderia as
  # outras. Melhor parar antes de mexer no que está rodando.
  if [ "${#networks[@]}" -ne 1 ]; then
    echo "O Prometheus está em ${#networks[@]} redes (${networks[*]}); recrie à mão." >&2
    exit 1
  fi

  run_flags=(--user "$user" --network "${networks[0]}" --network-alias prometheus)
  for port in "${ports[@]}"; do run_flags+=(-p "$port"); done
  for mount in "${mounts[@]}" "$DATANE_DIR:/etc/prometheus/datane:ro"; do
    run_flags+=(-v "$mount")
  done

  docker stop prometheus
  docker rename prometheus prometheus-antes-do-datane
  if ! docker run -d --name prometheus --restart unless-stopped "${run_flags[@]}" "$image" "${args[@]}"; then
    restore_old_prometheus
  fi
  for _ in $(seq 60); do
    curl -fsS http://localhost:9090/-/ready >/dev/null 2>&1 && break
    sleep 2
  done
  curl -fsS http://localhost:9090/-/ready >/dev/null || restore_old_prometheus
  docker rm prometheus-antes-do-datane

  # Para um `docker compose up` futuro não recriar o container sem o datane/.
  compose="$MONITOR_HOME/docker-compose.yml"
  if ! grep -q '/etc/prometheus/datane' "$compose"; then
    updated_compose="$(sed 's|^\(\s*\)- ./prometheus/prometheus-alerts.yml:/etc/prometheus/prometheus-alerts.yml$|&\n\1- ./prometheus/datane:/etc/prometheus/datane:ro|' "$compose")"
    printf '%s\n' "$updated_compose" > "$compose"
    grep -q '/etc/prometheus/datane' "$compose" ||
      echo "AVISO: não achei a linha do prometheus-alerts.yml no $compose; acrescente ./prometheus/datane:/etc/prometheus/datane:ro à mão." >&2
  fi
fi

echo "Data Nordeste configurado na VM de monitoramento."
