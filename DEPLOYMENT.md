# Guide de Déploiement en Production - NR School (Odoo 18.0)

Ce document décrit la procédure recommandée pour déployer la suite logicielle **NR School** dans un environnement de production pour un établissement scolaire.

---

## 1. Prérequis Système

- **Système d'exploitation** : Ubuntu 22.04 LTS / 24.04 LTS (ou Windows Server 2022)
- **Odoo** : Odoo 18.0 Community ou Enterprise
- **Base de données** : PostgreSQL 14 ou supérieur
- **Python** : Python 3.10, 3.11 ou 3.12
- **Moteur PDF** : Wkhtmltopdf 0.12.6 avec support QT patché (requis pour les bulletins et reçus)
- **Comptabilité marocaine (exigence recommandée / soft requirement)** : Module officiel `l10n_ma` pour initialiser le plan comptable marocain et le journal des ventes nécessaire à la facturation des frais scolaires (`account.move`).

---

## 2. Structure des Modules

| Module | Version | Rôle |
|---|---|---|
| `eacta_school` | 18.0.5.0 | Module cœur : élèves, années académiques, trimestres, notes, assiduité, finances, facturation, portail parents/élèves, badges QR et transport |
| `eacta_bibliotheque` | 18.0.3.0 | Catalogue, gestion des prêts/retours, retards et amendes |
| `eacta_event` | 18.0.3.0 | Sorties scolaires, événements, autorisations parentales |
| `eacta_theme` | 18.0.2.6 | Charte graphique backend et page de connexion institutionnelle |
| `l10n_ma` *(officiel)* | 18.0 | *(Exigence recommandée)* Plan comptable général marocain, journal des ventes et taxes |

---

## 3. Procédure d'Installation Initiale (Nouvelle École)

### 3.1. Récupération du Code Source
1. Cloner le dépôt dans votre répertoire d'addons personnalisés :
   - **Linux** :
     ```bash
     git clone https://github.com/yazaminoura/school.git /opt/odoo/custom-addons/school
     sudo chown -R odoo:odoo /opt/odoo/custom-addons/school
     ```
   - **Windows** :
     ```powershell
     git clone https://github.com/yazaminoura/school.git C:\Users\pc\Documents\school
     ```

### 3.2. Configuration du paramètre `addons_path`
Ajoutez le chemin absolu du dossier contenant les 4 modules dans le fichier `odoo.conf` (séparé par une virgule des addons officiels) :

- **Configuration sous Linux (`/etc/odoo/odoo.conf`)** :
  ```ini
  [options]
  addons_path = /opt/odoo/odoo-server/addons,/opt/odoo/custom-addons/school
  ```

- **Configuration sous Windows (`odoo.conf`)** :
  ```ini
  [options]
  addons_path = c:\project\odoo_project\server\odoo\addons,C:\Users\pc\Documents\school
  ```

> [!TIP]
> En ligne de commande, vous pouvez également spécifier le paramètre avec le flag `--addons-path` :
> `odoo-bin --addons-path="/opt/odoo/odoo-server/addons,/opt/odoo/custom-addons/school"`

### 3.3. Initialisation de la Base de Données

#### Mode Production (Vierge de données d'exemple)
Pour déployer une école en production sans données fictives, activez le drapeau `--without-demo=all` :
```bash
odoo -c /etc/odoo/odoo.conf -d nrschool_prod -i l10n_ma,eacta_school,eacta_bibliotheque,eacta_event,eacta_theme --without-demo=all --stop-after-init
```

#### Mode Évaluation / Démonstration (Avec données d'exemple)
Pour déployer un environnement de test pré-rempli (élèves, classes 2026-2027, enseignants, parents, emplois du temps et bibliothèque) :
```bash
odoo -c /etc/odoo/odoo.conf -d nrschool_demo -i l10n_ma,eacta_school,eacta_bibliotheque,eacta_event,eacta_theme --stop-after-init
```

### 3.4. Validation par les Tests Automatisés
Avant l'ouverture aux utilisateurs finaux, exécutez la suite de tests pour valider l'intégrité de l'installation :
```bash
odoo -c /etc/odoo/odoo.conf -d nrschool_prod -u eacta_school,eacta_bibliotheque,eacta_event,eacta_theme --test-enable --test-tags=eacta_school,eacta_bibliotheque,eacta_event,eacta_theme --stop-after-init
```

---

## 4. Procédure de Migration d'une Base Existante

Grâce au script de post-migration automatique inclus (`eacta_school/migrations/18.0.3.0/post-migrate.py`), la montée de version s'effectue sans aucune perte de données :

1. **Sauvegarde préalable impérative** :
   ```bash
   pg_dump -U odoo -Fc -f /var/backups/nrschool_before_upgrade_$(date +%Y%m%d).dump nrschool_prod
   ```

2. **Mettre à jour le code source** :
   ```bash
   cd /opt/odoo/custom-addons/school
   git pull origin main
   ```

3. **Lancer la mise à niveau Odoo** :
   ```bash
   odoo -c /etc/odoo/odoo.conf -d nrschool_prod -u eacta_school,eacta_bibliotheque,eacta_event,eacta_theme --stop-after-init
   ```

4. **Ce que le script de migration exécute automatiquement** :
   - Découverte de toutes les années sous forme textuelle historique (`"2023"`, `"2024"`, `"2026"`).
   - Création normalisée des enregistrements `eacta.academic.year` (`"2023-2024"`, `"2024-2025"`, `"2026-2027"`).
   - Génération des 3 trimestres marocains par année scolaire (`1er Trimestre`, `2ème Trimestre`, `3ème Trimestre`).
   - Rapprochement et mise à jour des clés étrangères `academic_year_id` sur les tables :
     - `eacta_class`
     - `eacta_student_fee`
     - `eacta_course_grade`
     - `eacta_timetable_slot`
     - `eacta_exam`
   - Détection et liaison automatique des examens aux trimestres correspondants selon leur date.

---

## 5. Configuration Recommandée pour la Production

### Fichier `odoo.conf` optimisé
```ini
[options]
admin_passwd = VOTRE_MOT_DE_PASSE_MAITRE_TRES_FORT
db_host = 127.0.0.1
db_port = 5432
db_user = odoo
db_password = VOTRE_MOT_DE_PASSE_POSTGRES
db_name = nrschool_prod
dbfilter = ^nrschool_prod$

addons_path = /opt/odoo/odoo-server/addons,/opt/odoo/custom-addons/school

# Multiprocessing (workers = 2 * CPU_CORES + 1)
workers = 5
max_cron_threads = 2

# Limitations mémoire (pour 8 Go RAM)
limit_memory_hard = 2684354560
limit_memory_soft = 2147483648
limit_request = 8192
limit_time_cpu = 120
limit_time_real = 240

# Sécurité & Logs
proxy_mode = True
logfile = /var/log/odoo/odoo-server.log
log_level = info
```

### Configuration Nginx (Reverse Proxy SSL)
```nginx
upstream odoo {
    server 127.0.0.1:8069;
}
upstream odoochat {
    server 127.0.0.1:8072;
}

server {
    listen 80;
    server_name ecole.mondomaine.ma;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name ecole.mondomaine.ma;

    ssl_certificate /etc/letsencrypt/live/ecole.mondomaine.ma/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/ecole.mondomaine.ma/privkey.pem;

    client_max_body_size 64M;

    # Longpolling
    location /websocket {
        proxy_pass http://odoochat;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
    }

    # Application principale
    location / {
        proxy_pass http://odoo;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_read_timeout 300s;
    }

    # Mise en cache des assets statiques
    location ~* /web/static/ {
        proxy_cache_valid 200 90m;
        proxy_buffering on;
        expires 864000;
        proxy_pass http://odoo;
    }

    gzip_types text/css text/scss text/plain text/xml application/xml application/json application/javascript;
    gzip on;
}
```

---

## 6. Sécurité & Bonnes Pratiques

1. **Aucun secret dans le code** : les mots de passe et clés API doivent être gérés via des paramètres de configuration Odoo chiffrés (`ir.config_parameter`) ou des variables d'environnement.
2. **Cloisonnement des rôles** :
   - Les professeurs n'ont aucun accès aux dossiers médicaux ni à la facturation.
   - Les parents sur le portail ne visualisent que leurs propres enfants.
   - Les notes sont verrouillées dès la clôture de l'examen ou du trimestre.
3. **Sauvegardes automatiques** :
   Configurer un script de sauvegarde quotidien sous `cron` chiffré et déporté (ex. AWS S3, Google Cloud Storage ou NAS sécurisé).
