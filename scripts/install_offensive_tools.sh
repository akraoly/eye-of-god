#!/bin/bash
# Installation des outils offensifs L'Œil de Dieu
# Lancer avec : sudo bash scripts/install_offensive_tools.sh

set -e
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
ok()  { echo -e "${GREEN}[✅] $1${NC}"; }
warn(){ echo -e "${YELLOW}[⚠️] $1${NC}"; }
err() { echo -e "${RED}[❌] $1${NC}"; }

echo "═══════════════════════════════════════════════════"
echo " L'Œil de Dieu — Installation outils offensifs"
echo "═══════════════════════════════════════════════════"

# 1. Outils apt
APT_TOOLS="ghidra sliver netexec mimikatz gophish bloodhound bloodhound-python pwntools python3-pwntools"
echo -e "\n[1/5] Installation paquets apt..."
apt-get update -qq
for pkg in $APT_TOOLS; do
  if apt-get install -y "$pkg" 2>/dev/null; then
    ok "$pkg installé"
  else
    warn "$pkg non disponible via apt"
  fi
done

# 2. Mettre à jour rockyou.txt décompressé
echo -e "\n[2/5] Décompression rockyou.txt..."
if [ ! -f /tmp/rockyou.txt ]; then
  gunzip -c /usr/share/wordlists/rockyou.txt.gz > /tmp/rockyou.txt && ok "rockyou.txt → /tmp/rockyou.txt"
else
  ok "rockyou.txt déjà présent"
fi

# 3. Havoc C2 (via kali-menu helper)
echo -e "\n[3/5] Vérification Havoc C2..."
if command -v havoc &>/dev/null; then
  ok "havoc installé"
elif apt-get install -y havoc 2>/dev/null; then
  ok "havoc installé via apt"
else
  warn "Havoc: installer manuellement depuis https://github.com/HavocFramework/Havoc"
fi

# 4. Evilginx (via Go)
echo -e "\n[4/5] Vérification Evilginx..."
if command -v evilginx &>/dev/null; then
  ok "evilginx installé"
elif command -v go &>/dev/null; then
  echo "Installation evilginx via Go..."
  go install github.com/kgretzky/evilginx2@latest 2>/dev/null && \
    cp ~/go/bin/evilginx2 /usr/local/bin/evilginx && ok "evilginx installé" || \
    warn "Evilginx: installer depuis https://github.com/kgretzky/evilginx2"
else
  warn "Evilginx: Go requis. apt install golang puis relancer ce script"
fi

# 5. Python tools
echo -e "\n[5/5] Outils Python..."
pip3 install --quiet shodan impacket bloodhound 2>/dev/null && ok "shodan, impacket, bloodhound (pip)"

# Résumé
echo ""
echo "═══════════════════════════════════════════════════"
echo " Outils nécessitant une installation manuelle :"
echo "   • Cobalt Strike  : licence commerciale requise"
echo "   • Mythic C2      : docker pull mythicmeta/mythic_server"
echo "   • Rubeus         : outil Windows (utiliser via Wine ou VM)"
echo "   • PowerView      : PowerShell Windows"
echo "═══════════════════════════════════════════════════"
echo " Pour relancer L'Œil de Dieu après installation :"
echo "   cd /home/kali/eye-of-god && source .venv/bin/activate"
echo "   export PYTHONPATH=\$(pwd)/backend"
echo "   python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8001"
echo "═══════════════════════════════════════════════════"
