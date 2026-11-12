# Plan de finalisation Swarm — à autoriser

Inventaire du 8 novembre 2026 : Windows 11 Professionnel, 34 098 995 200 octets de mémoire physique utilisable (environ 31,8 Gio), hyperviseur présent, 198 453 706 752 octets libres sur C:. Ubuntu, Debian et docker-desktop fonctionnent sous WSL2. Docker Desktop est accessible depuis Ubuntu ; son Swarm est inactif. Aucun Multipass, VirtualBox, VMware ou QEMU détecté dans le PATH ou les emplacements usuels vérifiés. Le statut des fonctionnalités facultatives Windows exige un terminal administrateur et n'a pas été confirmé.

## Proposition

Installer Multipass stable depuis Canonical sous Windows, avec son pilote Windows pris en charge. La documentation actuelle recommande la fonctionnalité Virtual Machine Platform ; ne pas activer Hyper-V ou désactiver WSL sans nécessité vérifiée et sans accord. Un redémarrage éventuel doit être convenu séparément.

| VM Ubuntu 24.04 LTS | Rôle | CPU virtuels | RAM | Disque virtuel maximal |
|---|---|---:|---:|---:|
| supinfo-manager | Manager, Redis, PostgreSQL, worker applicatif | 2 | 4 Go | 25 Go |
| supinfo-worker1 | Vote et result | 2 | 2 Go | 20 Go |
| supinfo-worker2 | Vote et result | 2 | 2 Go | 20 Go |

Les trois VM auront chacune leur moteur Docker indépendant. Le moteur Docker Desktop et ses volumes existants sont conservés. Les données du cluster de démonstration sont distinctes des données Compose ; aucun transfert ou remplacement implicite.

## Actions après accord

1. Installer Multipass et vérifier son pilote, les adresses et la connectivité des trois VM.
2. Créer les VM avec les ressources ci-dessus et installer Docker Engine dans chacune.
3. Construire les images ; privilégier leur transfert local par docker save/load pour éviter la publication sur un compte externe. Déployer avec les mêmes images chargées sur les trois nœuds et sans résolution de registre si cette méthode est retenue.
4. Initialiser le manager, joindre les deux workers et attribuer uniquement au manager le label voting.data=true.
5. Déployer la stack, vérifier les cinq services et la répartition des deux interfaces sur les workers.
6. Tester un vote et sa modification, puis redémarrer les services de stockage du laboratoire pour contrôler leur persistance sans supprimer les volumes.
7. Après autorisation explicite du test de panne, arrêter uniquement supinfo-worker1. Attendre sa détection comme Down et contrôler HTTP, WebSocket et votes via le manager avec worker2 restant actif. Redémarrer la VM et vérifier le retour à deux réplicas.
8. Enregistrer sorties horodatées et captures, finaliser le tableau du barème, puis créer un ZIP excluant secrets, sauvegardes privées, dépendances générées et archives imbriquées.

Un drain n'est pas une preuve d'arrêt réel de VM. Aucun cluster ni test de panne réel n'est actuellement revendiqué.

## Critères et preuves actuelles

| Critère | Points | État avant déploiement des VM | Preuve |
|---|---:|---|---|
| Dockerfile vote | 3 | Construit et exécuté | vote/Dockerfile, services Compose |
| Dockerfile worker | 3 | Construit et exécuté | worker/Dockerfile, test de vote |
| Dockerfile result | 3 | Construit et exécuté | result/Dockerfile, test WebSocket précédent |
| Docker Compose | 7 | Fonctionnel | proofs/compose-status.json |
| Dépendances | 2 | Configurées | depends_on service_healthy |
| Healthchecks | 2 | Présents pour les cinq services | Compose et Dockerfile worker |
| Persistance | 4 | Volumes configurés ; test après recréation à compléter | postgres_data et redis_data |
| Réseaux | 4 | Configurés ; inspection détaillée à compléter | frontend, backend interne |
| Déploiement Swarm | 6 | À réaliser | Pas encore de preuve réelle |
| Adaptation Compose Swarm | 2 | Validation syntaxique antérieure réussie | docker-compose.swarm.yml |
| Accessibilité après panne | 2 | À réaliser | Pas encore de preuve réelle |
| Documentation | 2 | Présente ; résultats réels à ajouter | README.md, DEPLOYMENT.md, VALIDATION.md |

Ce tableau ne constitue pas une attribution de note.
