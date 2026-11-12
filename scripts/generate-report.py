"""Generate the final Markdown report from actual, checked test evidence."""
import datetime
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
PROOFS = ROOT / 'docs/proofs'


def load(name):
    return json.loads((PROOFS / name).read_text(encoding='utf-8-sig'))


def paris(stamp):
    return datetime.datetime.fromisoformat(stamp.replace('Z', '+00:00')).astimezone(
        ZoneInfo('Europe/Paris')).strftime('%d/%m/%Y à %H:%M:%S CET')


audit = load('final-audit.json')
assert audit['status'] == 'PASS'
before = load('swarm-before-smoke.json')
down = load('swarm-worker1-down-smoke.json')
recovered = load('swarm-recovered-smoke.json')
persistence = load('swarm-persistence.json')
rows = [
    ('Dockerfile vote', 3, 'Construction réussie, utilisateur applicatif, route santé', '`vote/Dockerfile`, [build](proofs/final-build.txt)'),
    ('Dockerfile worker', 3, 'Multi-stage .NET 10, utilisateur applicatif, heartbeat', '`worker/Dockerfile`, [audit](proofs/final-audit.json)'),
    ('Dockerfile result', 3, 'Node 24, npm ci, utilisateur applicatif, route santé', '`result/Dockerfile`, [build](proofs/final-build.txt)'),
    ('Docker Compose', 7, 'Cinq services construits et exécutés', '`docker-compose.yml`, [audit](proofs/final-audit.json)'),
    ('Gestion des dépendances', 2, 'service_healthy pour les dépendances Compose ; retries/restart en Swarm', '`docker-compose.yml`, [tests](proofs/swarm-before-smoke.json)'),
    ('Vérifications de santé', 2, 'Healthchecks présents et tous les conteneurs actifs healthy', '[audit final](proofs/final-audit.json)'),
    ('Persistance des données', 4, 'PostgreSQL et Redis conservés après remplacement réel de leurs conteneurs', '[test de persistance](proofs/swarm-persistence.json)'),
    ('Configuration des réseaux', 4, 'Bridge en Compose, overlay en Swarm ; backend interne, bases non publiées', '[Compose](proofs/compose-networks.json), [Swarm](proofs/swarm-recovered-networks.txt)'),
    ('Déploiement Docker Swarm', 6, 'Un manager Leader et deux workers Ready dans trois VM distinctes', '[nœuds](proofs/swarm-recovered-nodes.txt), [VM](proofs/swarm-recovered-vms.json)'),
    ('Adaptation Compose pour Swarm', 2, 'Stack déployée, contraintes, réplicas, images préchargées et volumes', '`docker-compose.swarm.yml`, [services](proofs/swarm-recovered-services.txt)'),
    ("Accessibilité web malgré la panne d'un nœud", 2, 'Worker1 réellement éteint ; HTTP, votes et scores fonctionnent sur worker2', '[VM arrêtée](proofs/swarm-worker1-down-vms.json), [tests](proofs/swarm-worker1-down-smoke.json), [Windows](proofs/swarm-worker1-down-windows-http.json)'),
    ('Instructions et documentation', 2, 'Construction, lancement, cluster, panne, reprise, limites et packaging documentés', '`README.md`, [guide](DEPLOYMENT.md), ce rapport'),
]
assert sum(row[1] for row in rows) == 40
report = f'''# Rapport final — Mini-projet Docker SUPINFO

## Résultat

Les cinq services fonctionnent en Compose et dans un véritable cluster Swarm de trois VM Ubuntu Server 24.04 LTS, un manager et deux workers. Les interfaces ont deux réplicas, un sur chaque worker. Une extinction ACPI réelle de la VM worker1 a été exécutée ; le manager et worker2 ont continué à assurer le vote et les résultats. Worker1 a ensuite été redémarré avec ses disques conservés, et les deux réplicas de chaque interface sont revenus.

Audit final réussi : **{paris(audit['utc'])}**. Toutes les heures de ce rapport sont en Europe/Paris ; les preuves brutes utilisent UTC.

## Chronologie du dernier cycle contrôlé

| Étape exécutée | Heure Europe/Paris | Résultat |
|---|---|---|
| Avant panne : pages, santé, vote a puis b, scores WebSocket correspondants, refus d'un choix invalide | {paris(before['utc'])} | PASS |
| Worker1 éteint et Down : mêmes tests via le manager et worker2 | {paris(down['utc'])} | PASS |
| Après reprise : trois nœuds Ready, deux réplicas web chacun, mêmes tests | {paris(recovered['utc'])} | PASS |
| Recréation PostgreSQL et Redis avec conservation des valeurs témoins | {paris(persistence['utc'])} | PASS |

Les fichiers `*-smoke.json` détaillent chaque contrôle. Les tests comparent aussi les scores reçus par WebSocket aux agrégats SQL après chaque choix, et retirent uniquement leur vote de test. Chaque phase dispose d'un contrôle WebSocket supplémentaire. Dix requêtes HTTP depuis Windows (cinq par interface) ont été exécutées pendant la panne et dix après reprise : toutes ont répondu 200 avec le contenu attendu.

La panne est prouvée à deux niveaux : processus QEMU worker1 absent (`running: false`) et nœud Swarm worker1 Down. Les fichiers `*-live-web-tasks.json` montrent une tâche active par interface sur worker2 pendant la panne et deux après reprise. Le compteur brut de Swarm peut encore inclure d'anciennes tâches Running sur un nœud Down : il ne remplace pas cette vérification croisée. Les tâches Pending faute de worker éligible pendant la panne sont attendues avec la limite d'un réplica par nœud.

Une première collecte avait chevauché le redémarrage ; elle n'a pas été retenue comme preuve finale. Le cycle a été repris séquentiellement, un verrou a été ajouté à l'orchestrateur et l'audit final vérifie la cohérence de l'état arrêté, des nœuds, des tâches, des réponses HTTP et de la reprise.

## Correspondance avec le barème sur 40 points

Chaque ligne ci-dessous est couverte par une configuration et/ou une vérification exécutée. Les points indiqués sont ceux du barème, pas une note garantie : l'attribution appartient au correcteur.

| Critère | Points | Validation obtenue | Preuves |
|---|---:|---|---|
'''
for criterion, points, status, proof in rows:
    report += f'| {criterion} | {points} | Validé : {status} | {proof} |\n'
report += '''| **Total du barème couvert** | **40** | **Tous les critères disposent de preuves** | |

## Analyse et corrections

- Vote : identifiant complet généré avec secrets, validation des choix a/b, cookie HttpOnly/SameSite et JavaScript natif dans le formulaire.
- Worker : message retiré de Redis après succès SQL, UPSERT idempotent, connexion Redis par nom de service. Le consommateur reste volontairement unique. Une indisponibilité SQL peut entraîner sa sortie ; les politiques de redémarrage le relancent et le message non acquitté reste en file.
- Result : pool PostgreSQL avec reprises, diffusion périodique par WebSocket et abonnement du navigateur initialisé une seule fois. Les middlewares obsolètes ont été corrigés.
- Images : .NET 10 et Node 24, dépendances .NET actualisées après les avertissements de la première construction, bibliothèque GSSAPI ajoutée, contextes limités par .dockerignore. Le dernier build .NET ne signale plus les vulnérabilités initiales ; aucun audit de sécurité exhaustif n'est revendiqué.
- Compose : dépendances conditionnées par les healthchecks, deux réseaux et deux volumes nommés. Les cinq services sont healthy dans l'audit final.
- Swarm : fichier version 3.8, réseaux overlay, deux réplicas par interface sur les workers et placement des données sur le manager labellisé. Les mises à jour stop-first respectent la limite d'un réplica par worker.
- Infrastructure : Multipass Windows a été installé mais sa connexion TLS locale est interceptée par Avast. Aucune exclusion ni modification antivirus n'a été appliquée. Le laboratoire final utilise QEMU/KVM dans WSL2 ; les essais Multipass sont exclus du ZIP.

## Persistance et conservation des données

Le test de persistance a créé des valeurs uniques, forcé le remplacement réel des conteneurs PostgreSQL et Redis, puis vérifié leurs valeurs. Les identifiants des anciens et nouveaux conteneurs ainsi que leur santé sont conservés dans `swarm-persistence.json`. Seules les valeurs de test ont été retirées. Les volumes Compose existants et les disques des VM n'ont pas été supprimés ; le laboratoire utilise des données distinctes.

## Accès et état livré

- Compose : http://localhost:8080 et http://localhost:8888.
- Swarm : http://localhost:18080 et http://localhost:18888, redirigés vers les ports ingress du manager.
- Trois VM et cinq services Swarm laissés en fonctionnement, worker1 rétabli.
- Sources, configurations, scripts et preuves dans le ZIP ; secrets, clés SSH, disques VM et images Docker exclus.
- Guide de reproduction complet : [DEPLOYMENT.md](DEPLOYMENT.md).

## Limites et vérifications facultatives restantes

Aucun critère fonctionnel du barème ne reste sans preuve dans ce laboratoire. Le rendu visuel dans Chrome n'a pas été validé automatiquement : l'outil de contrôle du navigateur a interrompu sa session faute de pouvoir déterminer l'URL courante. Les tests d'interfaces réalisés sont des contrôles HTTP, de contenu, de votes et de scores WebSocket ; aucune capture de navigateur n'est présentée comme réalisée.

Les trois VM partagent un PC et WSL2 : le test ne démontre pas une tolérance à la panne du PC physique. Le manager et les bases singleton restent des points de panne. Le résultat démontre l'accessibilité après la perte d'un worker ; il ne garantit pas zéro requête perdue pendant la détection de panne. Pour la production, prévoir réplication des données, plusieurs managers, sauvegardes, serveur WSGI et gestion des secrets adaptée.

Les preuves brutes sont dans [proofs/](proofs/) ; leurs empreintes figurent dans [MANIFEST.sha256](proofs/MANIFEST.sha256).
'''
(ROOT / 'docs/VALIDATION.md').write_text(report, encoding='utf-8')
manifest = []
for path in sorted(PROOFS.iterdir()):
    if path.is_file() and path.name not in {'MANIFEST.sha256', 'multipass-installation.md'}:
        manifest.append(hashlib.sha256(path.read_bytes()).hexdigest() + '  ' + path.name)
(PROOFS / 'MANIFEST.sha256').write_text('\n'.join(manifest) + '\n')
print(f'Final report generated: {len(rows)} rubric criteria, 40 points, {len(manifest)} evidence files')
