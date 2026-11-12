# État de l'installation Multipass

Date : 8 novembre 2026, après accord de l'utilisateur.

- Installateur officiel : Multipass 1.17.0 Windows x64, dépôt canonical/multipass.
- SHA256 vérifié : `0efd5c9accb876a7dfbaf01669ab40ed0d95435e6cbea8f78cc5bde351d481e5`.
- Signature Authenticode : valide, CANONICAL GROUP LIMITED.
- Installation administrateur : code MSI 0 ; service Multipass en cours d'exécution.
- Pilote choisi par l'installateur : hcs. Aucun redémarrage Windows effectué.
- Connexion client au service : échec de validation TLS.
- Certificat du service sur disque : CN=localhost, émis par CN=Multipass Root CA, O=Canonical.
- Certificat réellement présenté au client local : CN=localhost, émis par Avast Web/Mail Shield Untrusted Root.
- Le diagnostic établit une interception TLS locale par Avast.
- Aucun bouclier ou paramètre antivirus n'a été modifié par l'agent.
- Les VM et le cluster ne sont pas encore créés ; aucun test de panne réel n'est revendiqué.

Les fichiers de diagnostic administrateur et journaux d'installation restent hors du livrable dans `.local` ou le dossier temporaire Windows. Aucun certificat privé n'est inclus.
