# Déploiement Swarm reproductible sous Windows / WSL2

## Méthode retenue
Trois VM Ubuntu Server 24.04 LTS QEMU/KVM s’exécutent dans Ubuntu WSL2. Chaque VM possède son propre noyau, disque et moteur Docker. Elles constituent trois nœuds Swarm distincts, même si elles partagent le même PC physique. Aucun réglage Avast n’est nécessaire.

| VM | Rôle Swarm | IP privée | RAM | vCPU | Disque maximal |
|---|---|---|---:|---:|---:|
| supinfo-manager | manager | 10.77.0.11 | 4 Gio | 2 | 25 Go |
| supinfo-worker1 | worker | 10.77.0.12 | 2 Gio | 2 | 20 Go |
| supinfo-worker2 | worker | 10.77.0.13 | 2 Gio | 2 | 20 Go |

PostgreSQL, Redis et le worker applicatif sont fixés au manager par `node.labels.voting.data == true`. `vote` et `result` ont chacun deux réplicas : un sur chaque worker. Le service applicatif `worker` est un consommateur de votes .NET ; il ne faut pas le confondre avec les deux nœuds Swarm workers.

Les services PostgreSQL du sujet sont nommés `postgres` dans les fichiers : il s’agit bien du composant `db` attendu. Les noms DNS applicatifs correspondent à ce choix.

## Prérequis et préparation
Les commandes ci-dessous sont à lancer dans un terminal Ubuntu WSL, à la racine du projet. Toute installation doit être autorisée par le propriétaire du PC. Le script de création ne modifie pas le BIOS, les fonctionnalités Windows, le pare-feu Windows ou l’antivirus.

```bash
sudo apt-get update
sudo apt-get install -y --no-install-recommends qemu-system-x86 qemu-utils cloud-image-utils
sudo python3 scripts/check-kvm.py
sudo python3 scripts/qemu-lab.py prepare
sudo python3 scripts/qemu-lab.py start all
sudo python3 scripts/qemu-deploy.py wait
```

`prepare` télécharge l’image officielle Ubuntu et vérifie son SHA256. Il génère une clé SSH privée dédiée et trois disques QCOW2 extensibles dans `/var/tmp/supinfo-swarm-lab`. Les fichiers existants sont conservés. Garder aussi l’image de base : les disques des VM en dépendent. Ce dossier doit être conservé et ne doit pas être ajouté au ZIP Moodle. Le répertoire `/var/tmp` peut être soumis à une politique de nettoyage propre à la machine : pour un usage durable, sauvegarder ou déplacer le laboratoire à l’arrêt en adaptant les chemins et les backing files.

Cloud-init installe `docker.io`, Python et curl dans les VM. Le réseau privé QEMU partage un bus multicast limité à l’interface loopback WSL ; une seconde interface NAT par VM permet les téléchargements. Aucun bridge ou changement de routage de l’hôte n’est requis. SSH utilise les ports locaux 2201/2202/2203. La première connexion SSH enregistre la clé de la VM créée localement dans un fichier known_hosts dédié.

## Construction et distribution locale des images
Docker Desktop doit fonctionner et être intégré à Ubuntu WSL.

```bash
docker compose build
sudo python3 scripts/qemu-deploy.py images
```

Les images applicatives sont étiquetées `supinfo.local/voting-vote:1.0`, `supinfo.local/voting-worker:1.0`, `supinfo.local/voting-result:1.0`. L’archive des images inclut aussi Redis et PostgreSQL, puis `docker load` est exécuté sur les trois VM. `supinfo.local` est seulement un préfixe de tags dans ce laboratoire, aucun registre n’est contacté et aucune image n’est publiée.

Après modification du code, reconstruire et recharger les images ; utiliser de nouveaux tags pour une livraison avec registre et, pour une mise à jour du laboratoire avec les mêmes tags, forcer explicitement la mise à jour des services applicatifs. Le script ne remplace pas automatiquement une tâche Swarm déjà démarrée avec un tag inchangé.

## Création et déploiement
```bash
sudo python3 scripts/qemu-deploy.py init
sudo python3 scripts/qemu-deploy.py deploy
sudo python3 scripts/qemu-deploy.py ready
sudo python3 scripts/qemu-deploy.py before
```

`init` teste les communications, initialise le manager et joint les deux workers. Les jetons ne sont pas enregistrés dans les preuves. `deploy` transfère le fichier Swarm et les tests sur le manager, génère un mot de passe aléatoire dans `/home/ubuntu/.cluster.env` avec permissions privées, labellise le manager et exécute `docker stack deploy --resolve-image never` avec les images préchargées. Ce fichier de mot de passe est conservé pour les redéploiements et exclu du livrable.

Accès depuis Windows ou Ubuntu WSL :
- Vote Swarm : http://localhost:18080
- Résultats Swarm : http://localhost:18888
- Les accès Compose existants restent http://localhost:8080 et http://localhost:8888.

Ces redirections locales ciblent les ports ingress 8080/8888 du manager. Swarm transmet les requêtes aux interfaces exécutées sur les workers. Le navigateur doit autoriser WebSocket ; aucun besoin d’affinité de session polling.

## Persistance et véritable arrêt d’un worker
Ces commandes modifient uniquement le laboratoire ; le test doit être autorisé avant exécution.

```bash
sudo python3 scripts/qemu-deploy.py persistence
sudo python3 scripts/qemu-deploy.py down
# Le worker1 est réellement arrêté. Contrôler les deux URL dans le navigateur.
sudo python3 scripts/qemu-deploy.py recover
```

`persistence` inscrit des valeurs de test uniques dans PostgreSQL et Redis, force la recréation des deux tâches de stockage, vérifie leur conservation et retire uniquement ses propres valeurs.

`down` demande l’arrêt ACPI de la VM worker1 et attend son extinction ainsi que son état Swarm Down. Il enregistre alors les états QEMU, les nœuds et tâches, puis teste les deux pages, leur santé, un vote, sa modification et WebSocket via le manager. Les deux services web conservent un réplica actif sur worker2. L’autre réplica reste en attente de capacité à cause de `max_replicas_per_node: 1`. Une connexion existante peut subir une interruption et se reconnecter : le test ne revendique pas zéro requête perdue pendant la détection de panne.

`recover` redémarre la même VM avec ses disques, attend le retour à 2/2 et répète les tests. Les preuves horodatées sont écrites dans `docs/proofs/`.

## Diagnostic et arrêt sans suppression
```bash
sudo python3 scripts/qemu-lab.py status all
sudo python3 scripts/qemu-lab.py ssh manager sudo docker node ls
sudo python3 scripts/qemu-lab.py ssh manager sudo docker stack services voting
sudo python3 scripts/qemu-lab.py ssh manager sudo docker service logs --tail=50 voting_worker
sudo python3 scripts/qemu-lab.py stop all
# Pour reprendre plus tard :
sudo python3 scripts/qemu-lab.py start all
sudo python3 scripts/qemu-deploy.py wait
sudo python3 scripts/qemu-deploy.py ready
```

L’arrêt conserve les disques et volumes. Aucune suppression de VM, de volume ou de données n’est nécessaire pour le rendu. Une mise en veille/fermeture de WSL arrête naturellement l’accès au laboratoire ; relancer les VM si nécessaire.

## Déploiement sur trois machines séparées avec registre
Le même `docker-compose.swarm.yml` peut être utilisé sur trois machines Linux réelles. Ouvrir entre elles TCP 2377, TCP/UDP 7946 et UDP 4789. Publier les trois images sur un registre accessible à toutes les machines :

```bash
export REGISTRY=docker.io/VOTRE_COMPTE
docker login
for service in vote worker result; do
  docker build -t "$REGISTRY/voting-$service:1.0" "./$service"
  docker push "$REGISTRY/voting-$service:1.0"
done
# Sur le manager :
docker swarm init --advertise-addr IP_MANAGER
docker swarm join-token worker
# Exécuter la commande affichée sur les deux workers, puis :
docker node update --label-add voting.data=true NOM_MANAGER
export POSTGRES_USER=postgres POSTGRES_DB=postgres
read -rs -p 'Mot de passe PostgreSQL alphanumérique long : ' POSTGRES_PASSWORD; echo
export POSTGRES_PASSWORD
docker stack config -c docker-compose.swarm.yml >/dev/null
docker stack deploy --with-registry-auth -c docker-compose.swarm.yml voting
```

Swarm ne charge pas automatiquement `.env` : exporter les variables. Les identifiants contenant des caractères spéciaux demandent un encodage adapté à l’URL PostgreSQL et à la chaîne Npgsql.

## Lecture des compteurs pendant une panne

Le compteur brut de services peut encore inclure d'anciennes tâches signalées Running sur le nœud Down. Les fichiers `*-live-web-tasks.json` dénombrent explicitement les tâches sur les seuls nœuds Ready : une par interface pendant la panne et deux après reprise. Les tâches Pending pendant la panne sont attendues avec la limite d'un réplica par worker.

Le script d'orchestration utilise un verrou pour éviter les collectes concurrentes. Ne pas lancer `qemu-lab.py start/stop` manuellement pendant une collecte.

## Limites
La panne testée est celle d’une VM worker, pas celle du PC physique. Le PC et WSL restent des points de panne communs. Le manager unique et les bases singleton ne sont pas hautement disponibles ; perdre le manager rend les votes et les résultats indisponibles. Les volumes locaux ne migrent pas entre nœuds. Ne pas déplacer le label de données sans migrer les volumes. Les deux réplicas web satisfont l’objectif pédagogique de résistance à la perte d’un worker.
