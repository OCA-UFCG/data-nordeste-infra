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
# pelo promtool/amtool/blackbox_exporter. Uma regra quebrada na pasta datane/ faz o
# Prometheus recusar o próximo reload (inclusive o do SEDES) e não subir no próximo
# reboot, deixando todos os projetos da VM sem monitoramento.
set -euo pipefail
cd "$(dirname "$0")"

# Fora da VM, só para ensaiar o script contra containers locais.
MONITOR_HOME="${MONITOR_HOME:-/home/ubuntu}"
PROMETHEUS_YML="$MONITOR_HOME/prometheus/prometheus.yml"
DATANE_DIR="$MONITOR_HOME/prometheus/datane"
ALERTMANAGER_YML="$MONITOR_HOME/alertmanager/alertmanager.yml"
BLACKBOX_YML="${BLACKBOX_YML:-$MONITOR_HOME/blackbox/blackbox-config.yml}"
COMPOSE_YML="$MONITOR_HOME/docker-compose.yml"
TOKEN_FILE="$DATANE_DIR/metrics-token"
DATANE_MOUNT="/etc/prometheus/datane"
READY_WAIT_STEPS=150 # de 2 s: 5 min, para o replay do WAL de uma VM com semanas de dados

# Os temporários podem ter o alertmanager.yml inteiro, com a senha do SMTP.
staging="$(mktemp -d)"
removed_job_yml="$(mktemp)"
updated_prometheus_yml="$(mktemp)"
updated_alertmanager_yml="$(mktemp)"
updated_blackbox_yml="$(mktemp)"
updated_compose_yml="$(mktemp)"

# IMPORTANT: ligado da regravação do prometheus.yml até o Prometheus novo estar
# pronto. O trap de EXIT devolve a configuração de antes em qualquer saída nesse
# intervalo (erro, Ctrl-C, SSH que cai); sem isso, OCA, SEDES, Atlas e Data
# Nordeste ficam sem monitoramento. `swap_mode` diz como desfazer.
swapping_prometheus=false
swap_mode=""
prometheus_yml_backup=""
compose_backup=""

compose_with() {
  local file="$1"
  shift
  docker compose --project-directory "$MONITOR_HOME" -f "$file" "$@"
}

restore_old_prometheus() {
  echo "A troca do Prometheus não terminou; voltando a configuração de antes." \
    "O Data Nordeste fica sem a nova coleta até o próximo deploy." >&2
  # O antigo não monta datane/: com o arquivo novo, o próximo reload largaria o
  # job antigo e os globs datane/* não casariam com nada, sem erro.
  if [ -n "$prometheus_yml_backup" ]; then cat "$prometheus_yml_backup" > "$PROMETHEUS_YML"; fi
  if [ "$swap_mode" = compose ]; then
    if [ -n "$compose_backup" ]; then cat "$compose_backup" > "$COMPOSE_YML"; fi
    compose_with "$COMPOSE_YML" up -d prometheus
  else
    if docker inspect prometheus-antes-do-datane >/dev/null 2>&1; then
      docker rm -f prometheus >/dev/null 2>&1
      docker rename prometheus-antes-do-datane prometheus
    fi
    docker start prometheus
  fi
}

cleanup() {
  set +e
  rm -rf "$staging" "$removed_job_yml" "$updated_prometheus_yml" "$updated_alertmanager_yml" \
    "$updated_blackbox_yml" "$updated_compose_yml"
  if $swapping_prometheus; then restore_old_prometheus; fi
}
trap cleanup EXIT
# O bash só roda o trap de EXIT num sinal se ele virar um `exit`.
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM

inspect() { docker inspect prometheus --format "$1" | sed '/^$/d'; }

# Os servidores que o Prometheus coleta, como "IP nome-do-certificado caminho".
metrics_targets() {
  python3 - prometheus-datane.yml <<'PY'
import sys
import yaml

config = yaml.safe_load(open(sys.argv[1], encoding="utf-8"))
job = next(j for j in config["scrape_configs"] if j["job_name"] == "datane-site")
for group in job["static_configs"]:
    for target in group["targets"]:
        print(target, job["tls_config"]["server_name"], job["metrics_path"])
PY
}

# Testa o token contra o /api/metrics de cada servidor, como o Prometheus fará. Um
# erro de digitação trocaria o token que funciona e, na coleta seguinte, os dois
# alvos dariam 401 e o DataneForaDoAr dispararia para prod e failover.
check_metrics_token() {
  local token="$1" accepted=0 ip name path code
  local -a targets
  mapfile -t targets < <(metrics_targets)
  [ "${#targets[@]}" -gt 0 ] || { echo "Não achei os servidores no prometheus-datane.yml." >&2; return 1; }

  for target in "${targets[@]}"; do
    read -r ip name path <<<"$target"
    # O token vai pela entrada do curl, e não pela linha de comando, para não
    # aparecer na lista de processos.
    code="$(printf 'header = "Authorization: Bearer %s"\n' "$token" |
      curl -sS -K - -o /dev/null -w '%{http_code}' -m 20 --resolve "$name:443:$ip" "https://$name$path" 2>/dev/null || true)"
    case "$code" in
      200) accepted=$((accepted + 1)) ;;
      401 | 403)
        echo "O servidor $ip recusou o METRICS_TOKEN (HTTP $code). Nada foi alterado: confira o valor." >&2
        return 1 ;;
      *) echo "AVISO: $ip respondeu HTTP ${code:-sem resposta} em $path." >&2 ;;
    esac
  done
  [ "$accepted" -gt 0 ] || {
    echo "Nenhum servidor aceitou o token. O site novo (com /api/metrics) precisa estar no ar antes." >&2
    return 1
  }
}

# Os alvos de bind mount que o compose declara para o serviço prometheus.
compose_bind_targets() {
  local resolved
  resolved="$(compose_with "$1" config --format json)" || {
    echo "O docker compose não aceitou o arquivo $1." >&2
    return 1
  }
  python3 -c '
import json
import sys

service = json.load(sys.stdin)["services"]["prometheus"]
for volume in service.get("volumes", []):
    if volume.get("type") == "bind":
        print(volume["target"])
' <<<"$resolved"
}

# O compose com o mount de datane/, logo depois do mount das regras do OCA.
write_compose_with_datane() {
  sed 's|^\(\s*\)- ./prometheus/prometheus-alerts.yml:/etc/prometheus/prometheus-alerts.yml$|&\n\1- ./prometheus/datane:/etc/prometheus/datane:ro|' \
    "$COMPOSE_YML" > "$updated_compose_yml"
}

wait_until_ready() {
  for _ in $(seq "$READY_WAIT_STEPS"); do
    curl -fsS http://localhost:9090/-/ready >/dev/null 2>&1 && return 0
    sleep 2
  done
  return 1
}

# O /-/ready só responde depois do replay do WAL, que numa VM com semanas de dados
# pode passar do prazo. Desfazer no meio do replay só o refaria duas vezes: só se
# desfaz quando o container de fato não está rodando.
ensure_prometheus_running() {
  wait_until_ready && return 0
  if [ "$(docker inspect -f '{{.State.Running}}' prometheus)" = true ]; then
    echo "AVISO: o Prometheus ainda não respondeu /-/ready depois de 5 min (replay do WAL?)." \
      "Ele está rodando e não foi desfeito; confira com: docker logs prometheus" >&2
    return 0
  fi
  return 1
}

# --- Checagens antes de gravar qualquer coisa --------------------------------
# IMPORTANT: tudo o que pode abortar vem antes do primeiro arquivo compartilhado
# gravado. O container atual só monta arquivos soltos e não enxerga datane/: se o
# prometheus.yml já apontasse para ela quando o script saísse, o próximo reload
# (um deploy do SEDES, por exemplo) largaria o job antigo sem erro nenhum.

docker inspect prometheus >/dev/null 2>&1 || {
  echo "Não achei o container prometheus." >&2
  exit 1
}
# Numa variável, e não direto num `| grep -q`: com pipefail, o grep que sai cedo
# pode dar SIGPIPE no inspect e fazer um container que já monta datane/ parecer
# um que não monta.
mounted_destinations="$(inspect '{{range .Mounts}}{{.Destination}}{{println}}{{end}}')"

recreate_prometheus=true
if grep -q "^$DATANE_MOUNT\$" <<<"$mounted_destinations"; then
  recreate_prometheus=false
fi

# Só o container criado por este docker-compose.yml pode ser recriado por ele: sem
# as labels do Compose, o `docker compose up` falha com "nome já em uso".
compose_managed=false
if [ "$(inspect '{{index .Config.Labels "com.docker.compose.project.working_dir"}}')" = "$MONITOR_HOME" ] &&
  [ "$(inspect '{{index .Config.Labels "com.docker.compose.service"}}')" = prometheus ]; then
  compose_managed=true
fi

if $recreate_prometheus && $compose_managed; then
  swap_mode=compose
  [ -f "$COMPOSE_YML" ] || { echo "Não achei $COMPOSE_YML." >&2; exit 1; }

  # O compose recria o container só com o que ele declara: um mount que o
  # container tem e o compose não conhece (de outro projeto, por exemplo) se perderia.
  write_compose_with_datane
  if cmp -s "$updated_compose_yml" "$COMPOSE_YML"; then
    echo "Não achei a linha do prometheus-alerts.yml no $COMPOSE_YML para pôr o mount de datane/ depois dela." \
      "Acrescente ./prometheus/datane:$DATANE_MOUNT:ro à mão no serviço prometheus e rode de novo." >&2
    exit 1
  fi
  compose_targets="$(compose_bind_targets "$updated_compose_yml")"
  grep -q "^$DATANE_MOUNT\$" <<<"$compose_targets" || {
    echo "O compose novo não declara o mount de datane/ no serviço prometheus; confira o $COMPOSE_YML." >&2
    exit 1
  }
  running_binds="$(inspect '{{range .Mounts}}{{if eq .Type "bind"}}{{.Destination}}{{println}}{{end}}{{end}}')"
  unknown_to_compose="$(comm -23 <(sort <<<"$running_binds") <(sort <<<"$compose_targets"))"
  if [ -n "$unknown_to_compose" ]; then
    echo "O container prometheus tem mounts que o $COMPOSE_YML não declara, e o compose os perderia:" >&2
    echo "$unknown_to_compose" >&2
    echo "Acrescente-os ao compose e rode de novo." >&2
    exit 1
  fi
elif $recreate_prometheus; then
  swap_mode=run
  # Sobra de uma troca interrompida: o rename falharia com o antigo já parado.
  if docker inspect prometheus-antes-do-datane >/dev/null 2>&1; then
    echo "Já existe o container prometheus-antes-do-datane, de uma troca" \
      "interrompida. Veja qual dos dois tem os dados, apague o outro e rode de novo." >&2
    exit 1
  fi

  # Lido do próprio container, para não perder o sedes/ nem o que outro projeto
  # tiver acrescentado.
  mapfile -t mounts < <(inspect '{{range .Mounts}}{{if eq .Type "volume"}}{{.Name}}{{else}}{{.Source}}{{end}}:{{.Destination}}{{if not .RW}}:ro{{end}}{{println}}{{end}}')
  mapfile -t args < <(inspect '{{range .Args}}{{println .}}{{end}}')
  mapfile -t envs < <(inspect '{{range .Config.Env}}{{println .}}{{end}}')
  mapfile -t networks < <(inspect '{{range $name, $_ := .NetworkSettings.Networks}}{{$name}}{{println}}{{end}}')
  mapfile -t aliases < <(inspect '{{range $name, $net := .NetworkSettings.Networks}}{{range $net.Aliases}}{{println .}}{{end}}{{end}}')
  mapfile -t ports < <(inspect '{{range $port, $bindings := .HostConfig.PortBindings}}{{with index $bindings 0}}{{if .HostIp}}{{.HostIp}}:{{end}}{{.HostPort}}{{end}}:{{$port}}{{println}}{{end}}')
  mapfile -t log_opts < <(inspect '{{range $key, $value := .HostConfig.LogConfig.Config}}{{$key}}={{$value}}{{println}}{{end}}')
  log_driver="$(inspect '{{.HostConfig.LogConfig.Type}}')"
  restart="$(inspect '{{.HostConfig.RestartPolicy.Name}}{{if gt .HostConfig.RestartPolicy.MaximumRetryCount 0}}:{{.HostConfig.RestartPolicy.MaximumRetryCount}}{{end}}')"
  user="$(inspect '{{.Config.User}}')"
  image="$(inspect '{{.Config.Image}}')"

  # O `docker run` só aceita uma rede; com mais, o container novo perderia as
  # outras.
  if [ "${#networks[@]}" -ne 1 ]; then
    echo "O Prometheus está em ${#networks[@]} redes (${networks[*]}); recrie à mão." >&2
    exit 1
  fi
fi

# O módulo do job datane-certificado. Só gera e valida aqui; grava mais abaixo.
if [ ! -f "$BLACKBOX_YML" ]; then
  echo "Não achei $BLACKBOX_YML; se o blackbox da VM usa outro caminho, rode com BLACKBOX_YML=..." >&2
  exit 1
fi
python3 merge_blackbox_module.py "$BLACKBOX_YML" blackbox-datane.yml > "$updated_blackbox_yml"
docker run --rm --user root --entrypoint /bin/blackbox_exporter -v "$updated_blackbox_yml":/check.yml:ro \
  prom/blackbox-exporter:latest --config.check --config.file=/check.yml

# O token novo fica no staging até passar no teste; só então substitui o que funciona.
token="$(cat)"
if [ -n "$token" ]; then
  (umask 077 && printf '%s' "$token" > "$staging/metrics-token")
  if [ "${SKIP_METRICS_TOKEN_CHECK:-}" = 1 ]; then
    echo "AVISO: teste do token pulado (SKIP_METRICS_TOKEN_CHECK=1)." >&2
  else
    check_metrics_token "$token"
  fi
elif [ -s "$TOKEN_FILE" ]; then
  install -m 600 "$TOKEN_FILE" "$staging/metrics-token"
else
  echo "Falta o METRICS_TOKEN: rode o deploy.sh com METRICS_TOKEN=..." >&2
  exit 1
fi

# --- Alertmanager -----------------------------------------------------------
# Primeiro: se ele falhasse depois do Prometheus, os alertas Datane já
# disparariam e cairiam na rota padrão, para as caixas do OCA.

python3 merge_alertmanager.py "$ALERTMANAGER_YML" alertmanager-datane.yml datane > "$updated_alertmanager_yml"
docker run --rm --user root --entrypoint amtool -v "$updated_alertmanager_yml":/check.yml:ro \
  prom/alertmanager:latest check-config /check.yml

if ! cmp -s "$updated_alertmanager_yml" "$ALERTMANAGER_YML"; then
  cp "$ALERTMANAGER_YML" "$ALERTMANAGER_YML.bak-$(date +%Y%m%d%H%M%S)"
  cat "$updated_alertmanager_yml" > "$ALERTMANAGER_YML"
  curl -fsS -X POST http://localhost:9093/-/reload
fi

# --- Blackbox ---------------------------------------------------------------
# Antes do Prometheus: o job datane-certificado usa o módulo datane_certificado, e
# sem ele a sonda falharia com módulo desconhecido.

if ! cmp -s "$updated_blackbox_yml" "$BLACKBOX_YML"; then
  cp "$BLACKBOX_YML" "$BLACKBOX_YML.bak-$(date +%Y%m%d%H%M%S)"
  cat "$updated_blackbox_yml" > "$BLACKBOX_YML"
fi
# Sempre: se um deploy anterior gravou e o reload falhou, o arquivo já está igual
# e o blackbox seguiria com a configuração antiga.
curl -fsS -X POST http://localhost:9115/-/reload

# --- Prometheus: arquivos ---------------------------------------------------

# O job `datane` antigo (blackbox em datanordeste-portal.com/health, editado à
# mão em 10–11/11/2026) dá lugar ao datane-certificado do prometheus-datane.yml.
python3 remove_scrape_job.py "$PROMETHEUS_YML" datane > "$removed_job_yml"
python3 ensure_prometheus_entries.py "$removed_job_yml" \
  rule_files=datane/datane-alerts.yml scrape_config_files=datane/prometheus-datane.yml > "$updated_prometheus_yml"

# Valida a pasta inteira como o Prometheus a verá: o prometheus.yml novo e a
# pasta datane/ nova por cima da atual. Como root, para ler os tokens. Sem o
# lint de regras duplicadas: o prometheus-alerts.yml do OCA já repete o
# InstanceDown.
install -m 644 prometheus-datane.yml datane-alerts.yml "$staging"/
docker run --rm --user root --entrypoint promtool \
  -v "$MONITOR_HOME/prometheus":/etc/prometheus:ro \
  -v "$staging":"$DATANE_MOUNT":ro \
  -v "$updated_prometheus_yml":/etc/prometheus/prometheus.yml:ro \
  prom/prometheus:latest check config --lint=none /etc/prometheus/prometheus.yml

install -d -m 755 "$DATANE_DIR"
install -m 644 "$staging"/prometheus-datane.yml "$staging"/datane-alerts.yml "$DATANE_DIR"/
if [ -f "$TOKEN_FILE" ] && ! cmp -s "$staging/metrics-token" "$TOKEN_FILE"; then
  # O anterior fica guardado: um token errado não deixa o operador sem o que funcionava.
  (umask 077 && cp "$TOKEN_FILE" "$TOKEN_FILE.bak-$(date +%Y%m%d%H%M%S)")
fi
install -m 600 "$staging/metrics-token" "$TOKEN_FILE"

if ! cmp -s "$updated_prometheus_yml" "$PROMETHEUS_YML"; then
  # Quem roda vê exatamente o que mudou no arquivo que todos dividem.
  diff -u "$PROMETHEUS_YML" "$updated_prometheus_yml" || true
  prometheus_yml_backup="$PROMETHEUS_YML.bak-$(date +%Y%m%d%H%M%S)"
  cp "$PROMETHEUS_YML" "$prometheus_yml_backup"
  # Antes de gravar: o container antigo não enxerga datane/ com o arquivo novo.
  if $recreate_prometheus; then swapping_prometheus=true; fi
  cat "$updated_prometheus_yml" > "$PROMETHEUS_YML"
fi

# --- Prometheus: container --------------------------------------------------

if ! $recreate_prometheus; then
  curl -fsS -X POST http://localhost:9090/-/reload
elif [ "$swap_mode" = compose ]; then
  # O container nasceu deste compose: editar o arquivo e subir de novo mantém
  # labels, variáveis, aliases, log e portas, e o `docker compose up` seguinte não
  # estranha o container. Os dados ficam no volume.
  compose_backup="$COMPOSE_YML.bak-$(date +%Y%m%d%H%M%S)"
  cp "$COMPOSE_YML" "$compose_backup"
  swapping_prometheus=true
  cat "$updated_compose_yml" > "$COMPOSE_YML"
  compose_with "$COMPOSE_YML" up -d prometheus
  ensure_prometheus_running
  swapping_prometheus=false
else
  # O container não é do compose (sem labels): ele é recriado com tudo o que o
  # atual tem (lido antes, nas checagens) e mais o datane/. O antigo só é apagado
  # depois que o novo sobe.
  run_flags=(--user "$user" --network "${networks[0]}")
  # O alias não vale na rede bridge padrão; o próprio id do container também não.
  if [ "${networks[0]}" != bridge ]; then
    for alias in "${aliases[@]}"; do
      [[ "$alias" =~ ^[0-9a-f]{12}$ ]] || run_flags+=(--network-alias "$alias")
    done
  fi
  [ -z "$restart" ] || run_flags+=(--restart "$restart")
  [ -z "$log_driver" ] || run_flags+=(--log-driver "$log_driver")
  for option in "${log_opts[@]}"; do run_flags+=(--log-opt "$option"); done
  for variable in "${envs[@]}"; do run_flags+=(-e "$variable"); done
  for port in "${ports[@]}"; do run_flags+=(-p "$port"); done
  for mount in "${mounts[@]}" "$DATANE_DIR:$DATANE_MOUNT:ro"; do
    run_flags+=(-v "$mount")
  done

  swapping_prometheus=true
  docker stop prometheus
  docker rename prometheus prometheus-antes-do-datane
  docker run -d --name prometheus "${run_flags[@]}" "$image" "${args[@]}"
  ensure_prometheus_running
  swapping_prometheus=false
  docker rm prometheus-antes-do-datane

  # Para um `docker compose up` futuro não recriar o container sem o datane/.
  # O container já subiu: um problema aqui é aviso, e não falha do deploy.
  if [ ! -f "$COMPOSE_YML" ]; then
    echo "AVISO: não achei $COMPOSE_YML; acrescente ./prometheus/datane:$DATANE_MOUNT:ro ao serviço prometheus à mão." >&2
  elif ! grep -q "$DATANE_MOUNT" "$COMPOSE_YML"; then
    write_compose_with_datane
    if cmp -s "$updated_compose_yml" "$COMPOSE_YML" || ! compose_with "$updated_compose_yml" config -q; then
      echo "AVISO: não consegui acrescentar o mount de datane/ ao $COMPOSE_YML; acrescente ./prometheus/datane:$DATANE_MOUNT:ro à mão." >&2
    else
      cat "$updated_compose_yml" > "$COMPOSE_YML"
    fi
  fi
fi

echo "Data Nordeste configurado na VM de monitoramento."
