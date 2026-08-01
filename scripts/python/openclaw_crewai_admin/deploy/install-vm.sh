#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Exécutez ce script avec sudo sur une VM Ubuntu/Debian dédiée." >&2
  exit 1
fi

apt-get update
apt-get install -y --no-install-recommends ca-certificates curl gnupg
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg
. /etc/os-release
architecture="$(dpkg --print-architecture)"
echo "deb [arch=$architecture signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $VERSION_CODENAME stable" \
  > /etc/apt/sources.list.d/docker.list
apt-get update
apt-get install -y --no-install-recommends docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable --now docker

install -d -m 0700 /opt/openclaw-crewai /srv/crewai /var/lib/openclaw-crewai
echo "Docker est prêt. Copiez le kit dans /opt/openclaw-crewai, le projet dans /srv/crewai,"
echo "puis exécutez install-secure-container.sh avec les quatre paramètres documentés."

