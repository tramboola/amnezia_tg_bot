#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
fail() { printf 'Ошибка: %s\n' "$*" >&2; exit 1; }
[[ $# -le 1 ]] || fail "использование: sudo bash install.sh [--prepare-only]"
case "${1:-}" in
    ''|--prepare-only) ;;
    *) fail "использование: sudo bash install.sh [--prepare-only]" ;;
esac
[[ "$EUID" -eq 0 ]] || fail "запустите: sudo bash install.sh"
[[ -r /etc/os-release ]] || fail "не удалось определить ОС"
# shellcheck disable=SC1091
source /etc/os-release
[[ "${ID:-}" == ubuntu ]] || fail "установщик поддерживает Ubuntu; см. README для ручного запуска"
[[ -c /dev/net/tun ]] || fail "нет /dev/net/tun; включите TUN у провайдера VPS"
cd "$project_dir"
[[ ! -e .env && ! -e secrets/bot_token ]] || fail "настройки уже существуют; обновляйте через README"

if ! command -v docker >/dev/null 2>&1; then
    apt-get update
    apt-get install -y ca-certificates curl
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    chmod a+r /etc/apt/keyrings/docker.asc
    cat > /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: ${UBUNTU_CODENAME:-${VERSION_CODENAME}}
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
    apt-get update
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi
docker compose version >/dev/null 2>&1 || fail "нужен Docker Compose plugin"
systemctl enable --now docker
docker info >/dev/null

printf 'Собираю VPN и бота; это может занять несколько минут…\n'
docker build -t amnezia-tg-awg:3.1 vpn
docker compose --env-file .env.example build manager
docker compose --env-file .env.example build bot

if [[ "${1:-}" == --prepare-only ]]; then
    printf '\nОбразы подготовлены. Для ввода токена и запуска бота выполните: sudo bash install.sh\n'
    exit 0
fi

read -r -s -p 'Токен бота от BotFather: ' task_bot_token
printf '\n'
[[ "$task_bot_token" =~ ^[0-9]+:[A-Za-z0-9_-]+$ ]] || fail "неверный формат токена"
read -r -p 'Числовые Telegram ID администраторов, через запятую: ' task_admin_ids
[[ "$task_admin_ids" =~ ^[1-9][0-9]*(,[1-9][0-9]*)*$ ]] || fail "нужны положительные числовые ID"
install -d -m 0700 secrets
printf '%s\n' "$task_bot_token" > secrets/bot_token
unset task_bot_token
chown 10001:10001 secrets/bot_token
chmod 0600 secrets/bot_token
printf 'ADMIN_IDS=%s\n' "$task_admin_ids" > .env
chmod 0600 .env

docker compose up -d
docker compose ps
printf '\nБот запущен. Откройте его в Telegram: /start, IPv4:UDP-порт, запуск VPN.\n'
printf 'Откройте выбранный UDP-порт в firewall VPS и панели провайдера.\n'
