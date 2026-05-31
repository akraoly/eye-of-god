# Système d'agents

## Architecture

Chaque agent hérite de `BaseAgent` et implémente :
- `name` : identifiant unique
- `description` : description lisible
- `can_handle(task)` : détecte si l'agent peut traiter la tâche
- `run(task, context)` : exécute la tâche

## Agents disponibles

### CyberAgent (`cyber`)
**Statut :** Phase 1 (commandes whitelistées)
**Futur :** Analyse réseau, scan vulnérabilités, support CTF

Mots-clés déclencheurs : scan, nmap, vulnérabilité, port, réseau, ctf, exploit

### LifeAgent (`life`)
**Statut :** Skeleton (à implémenter)
**Futur :** Rappels, tâches, organisation, projets personnels

Mots-clés déclencheurs : rappel, tâche, agenda, note, projet, objectif

### SystemAgent (`system`)
**Statut :** Opérationnel (whitelist terminal)
**Actuel :** Exécution de commandes Linux autorisées

Mots-clés déclencheurs : terminal, commande, bash, linux, système, cpu

## Whitelist commandes terminal

```
ls, pwd, whoami, id, uname, df, du, free, ps,
netstat, ss, ip, ping, nslookup, dig,
cat, grep, find, echo, date, uptime, hostname,
nmap, whois, traceroute, curl, wget
```

## Ajouter un agent

1. Créer `core/agents/mon_agent.py` en héritant de `BaseAgent`
2. Implémenter `can_handle()` et `run()`
3. Importer et ajouter dans `services/agent_service.py::AGENTS`
