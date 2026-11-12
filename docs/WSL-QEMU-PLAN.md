# Alternative sans modification d'Avast

## Vérifications exécutées le 8 novembre 2026

- Ubuntu WSL2 : noyau 6.18.54.1-microsoft-standard-WSL2.
- Mémoire visible par WSL : environ 15 Gio ; environ 13 Gio disponibles au moment du contrôle.
- `/dev/kvm` existe ; appel KVM_GET_API_VERSION exécuté en root : **12**, résultat attendu. L'accélération doit encore être confirmée au lancement effectif d'une VM.
- `/dev/net/tun` existe, mais la méthode proposée n'en a pas besoin.
- QEMU et cloud-localds ne sont pas installés.
- SSH, Python 3 et systemd sont présents. L'unité getty@tty1 est en échec ; aucun changement n'a été effectué sur celle-ci.

## Installation supplémentaire proposée, à autoriser

Installer dans Ubuntu WSL uniquement :

```bash
sudo apt-get update
sudo apt-get install --no-install-recommends qemu-system-x86 qemu-utils cloud-image-utils
```

Les dépendances nécessaires seront aussi installées par APT. Aucune mise à niveau générale de la distribution, modification antivirus, modification du BIOS, activation de fonctionnalité Windows ou redémarrage Windows n'est prévu.

## VM et réseau proposés

Trois véritables VM Ubuntu Server 24.04 LTS QEMU/KVM : manager 4 Gio, deux workers 2 Gio chacun, 2 vCPU par VM. Disques QCOW2 extensibles : 25/20/20 Go maximaux, sans préallocation complète.

Chaque VM possède son noyau et son moteur Docker. Docker sera installé uniquement dans les VM pour le laboratoire. Le moteur et les volumes Docker Desktop existants restent indépendants.

Un réseau QEMU partagé entre les trois VM transportera les communications Swarm ; une interface NAT par VM permettra les téléchargements et l'accès SSH. Les interfaces du laboratoire seront publiées sur des ports locaux distincts des ports Compose existants, par exemple 18080 et 18888. La connectivité et les ports libres devront être contrôlés avant le lancement.

Le test de panne consiste à arrêter la VM worker1, vérifier que Swarm la voit Down et que vote/result fonctionnent via le manager et worker2, puis redémarrer worker1. Un arrêt de VM n'est pas présenté comme une panne physique de l'ordinateur hôte.

## État

La faisabilité KVM a été contrôlée ; aucun paquet de cette méthode n'a encore été installé et aucune VM QEMU n'a été créée. Multipass Windows reste installé, sans utilisation et sans exclusion Avast. Sa désinstallation éventuelle exige une demande distincte.

Références :
- https://learn.microsoft.com/windows/wsl/wsl-config
- https://ubuntu.com/server/docs/virtualization-qemu/
- https://www.qemu.org/docs/master/system/invocation.html
