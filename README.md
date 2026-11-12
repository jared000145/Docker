# Mini-projet Docker SUPINFO — application de vote distribuée

Cinq services : `vote` (Flask/Python), `worker` (.NET 10), `result` (Node.js 24), Redis 7 et PostgreSQL 15. Le service `postgres` correspond au composant `db` de l'énoncé.

## Lancement local

Installer Docker Engine avec Compose, ou Docker Desktop avec son intégration Ubuntu WSL2. Depuis la racine dans Ubuntu :

```bash
# Seulement sur une installation neuve :
test -f .env || cp .env.example .env
# Adapter les identifiants AVANT la première initialisation de PostgreSQL.
docker compose config --quiet
docker compose up --build -d --wait --wait-timeout 240
python3 scripts/smoke.py
docker compose exec -T result node < scripts/socket-smoke.js
```

Avec des volumes déjà initialisés, conserver les identifiants existants : changer POSTGRES_PASSWORD dans Compose ne change pas le mot de passe stocké par PostgreSQL. Sur le PC du projet, les services et volumes existants ont été conservés.

Vote : http://localhost:8080 — Résultats : http://localhost:8888.
Sous PowerShell, si Docker est absent du PATH, utiliser Ubuntu ou préfixer les commandes Docker par `wsl -d Ubuntu --` depuis le dossier du projet.

## Swarm à trois nœuds

Le laboratoire utilise trois VM Ubuntu Server 24.04 LTS QEMU/KVM dans WSL2 : un manager et deux workers, avec un moteur Docker par VM. Les deux interfaces ont chacune deux réplicas répartis sur les workers. Les images sont transférées localement, sans registre externe.

- Vote Swarm : http://localhost:18080
- Résultats Swarm : http://localhost:18888

Le 8 novembre 2026, worker1 a réellement été arrêté. Les pages, un vote, sa modification et WebSocket ont été testés pendant la panne, puis après reprise. La persistance PostgreSQL et Redis a été vérifiée après recréation des tâches de stockage sans suppression des volumes. Voir les résultats horodatés dans [le rapport final](docs/VALIDATION.md).

## Architecture

`Navigateur → vote → Redis → worker → PostgreSQL → result → WebSocket → navigateur`

Le worker unique réalise un UPSERT PostgreSQL avant de retirer le message Redis. Une reprise peut rejouer le même vote sans créer de doublon. Ne pas répliquer ce consommateur avec cet algorithme. Un message malformé injecté directement dans Redis nécessite une intervention.

Result utilise un pool PostgreSQL et diffuse les scores chaque seconde. Le proxy éventuel doit autoriser WebSocket. Le réseau `frontend` dessert les interfaces ; `backend` est interne. Redis et PostgreSQL ne publient aucun port. Les cinq services ont un healthcheck, celui du worker étant défini dans son Dockerfile.

Les images utilisent un utilisateur applicatif non privilégié ; le worker est construit en multi-stage. Le serveur Flask est celui du TP et n'est pas présenté comme une configuration de production.

## Documentation et preuves

- [Construction, déploiement, panne et reprise](docs/DEPLOYMENT.md)
- [Rapport final et correspondance avec les 40 points](docs/VALIDATION.md)
- [Preuves brutes horodatées](docs/proofs/)

Les preuves sont des sorties de commandes et des tests HTTP/WebSocket. Le contrôle visuel automatisé de Chrome n'a pas abouti ; aucune capture de navigateur ni panne physique du PC n'est revendiquée.

## Exploitation sans suppression

```bash
docker compose ps
docker compose logs --tail=100 vote worker result
docker compose down
# Arrêter uniquement les VM du laboratoire en conservant leurs disques :
sudo python3 scripts/qemu-lab.py stop all
# Les reprendre :
sudo python3 scripts/qemu-lab.py start all
sudo python3 scripts/qemu-deploy.py wait
sudo python3 scripts/qemu-deploy.py ready
```

`docker compose down` conserve les volumes ; ajouter `-v` les supprimerait. Cette suppression n'est pas nécessaire. Le cluster et Compose utilisent des données distinctes. Les bases singleton et le manager unique ne sont pas hautement disponibles ; le test porte sur la perte d'un worker.

## Recréer le livrable

```bash
python3 scripts/package.py
```

Le ZIP contient sources, configurations, documentation et preuves. Il exclut secrets, clés, disques VM, images Docker, dépendances générées et essais Multipass abandonnés. Son intégrité ZIP est vérifiée et un SHA256 est produit à côté. Les disques VM ne sont pas requis pour le dépôt Moodle : les images se reconstruisent depuis les sources.