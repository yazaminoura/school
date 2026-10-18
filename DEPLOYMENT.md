# Guide de Déploiement en Production - NR School (Odoo 18.0)

Ce document décrit la procédure recommandée pour déployer la suite logicielle **NR School** dans un environnement de production pour un établissement scolaire.

---

## 1. Prérequis Système

- **Système d'exploitation** : Ubuntu 22.04 LTS / 24.04 LTS (ou Windows Server 2022)
- **Odoo** : Odoo 18.0 Community ou Enterprise
- **Base de données** : PostgreSQL 14 ou supérieur
- **Python** : Python 3.10, 3.11 ou 3.12
- **Moteur PDF** : Wkhtmltopdf 0.12.6 avec support QT patché (requis pour les bulletins et reçus)

---

## 2. Structure des Modules

| Module | Version | Rôle |
|---|---|---|
| `eacta_school` | 18.0.3.0 | Module cœur : élèves, années académiques, trimestres, notes, assiduité, finances, emplois du temps |
| `eacta_bibliotheque` | 18.0.2.0 | Catalogue, gestion des prêts/retours, retards et amendes |
| `eacta_event` | 18.0.2.0 | Sorties scolaires, événements, autorisations parentales |
| `eacta_theme` | 18.0.2.4 | Charte graphique backend et page de connexion institutionnelle |

---

## 3. Procédure d'Installation Initiale (Nouvelle École)

1. Cloner le dépôt dans votre répertoire d'addons :
   ```bash
   git clone https://github.com/yazaminoura/school.git /opt/odoo/custom-addons/school
   ```

2. Assurer les permissions utilisateur :
   ```bash
   sudo chown -R odoo:odoo /opt/odoo/custom-addons/school
   ```

3. Ajouter le chemin aux `addons_path` de votre fichier `odoo.conf` :
   ```ini
   addons_path = /opt/odoo/odoo-server/addons,/opt/odoo/custom-addons/school
   ```

4. Installer les modules sur la base de données de production :
   ```bash
   odoo -c /etc/odoo/odoo.conf -d nrschool_prod -i eacta_school,eacta_bibliotheque,eacta_event,eacta_theme --stop-after-init
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
