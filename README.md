# NR School - Suite de Gestion Scolaire pour Odoo 18.0

**NR School** est une suite modulaire et intégrée de gestion scolaire conçue pour **Odoo 18.0 (Community et Enterprise)**, adaptée aux spécificités des établissements scolaires marocains et internationaux (maternelle, primaire, collège, lycée).

---

## 1. Modules de la Suite

| Module | Version | Rôle & Description |
|---|---|---|
| [`eacta_school`](file:///c:/Users/pc/Documents/school/eacta_school) | **18.0.5.0** | **Cœur académique & administratif** : années scolaires, trimestres, élèves, classes, cours, coefficients, examens, workflow de notes (Brouillon &rarr; Soumis &rarr; Validé &rarr; Publié), bulletins scolaires PDF (format officiel marocain), PV de délibération du conseil de classe, assiduité, facturation (`account.move`, devises MAD), remises fratrie, rappels d'impayés, portail parents/élèves (`/my/school`), badges QR code et pointage mobile (`/school/attendance/scan`), et transport scolaire. |
| [`eacta_bibliotheque`](file:///c:/Users/pc/Documents/school/eacta_bibliotheque) | **18.0.3.0** | **Bibliothèque scolaire (CDI)** : catalogue d'ouvrages, exemplaires avec codes-barres, gestion des prêts et retours pour élèves et enseignants, prolongation, déclaration de perte, amendes de retard opt-in et relances planifiées. |
| [`eacta_event`](file:///c:/Users/pc/Documents/school/eacta_event) | **18.0.3.0** | **Événements & Activités périscolaires** : sorties pédagogiques, voyages, cérémonies, inscriptions collectives par classe, contrôle des capacités, autorisations parentales et feuilles de présence. |
| [`eacta_theme`](file:///c:/Users/pc/Documents/school/eacta_theme) | **18.0.2.6** | **Charte graphique & Expérience utilisateur** : interface backend modernisée aux couleurs de l'école, page de connexion institutionnelle personnalisable, palettes de couleurs prédéfinies et styles adaptatifs. |

---

## 2. Fonctionnalités Clés par Domaine

### 📚 Gestion Pédagogique & Vie Scolaire
- **Workflow rigoureux des notes** : Cycle d'approbation à 4 états (*Brouillon &rarr; Soumis &rarr; Validé &rarr; Publié*) garantissant qu'aucune note non validée par la Direction ne parvient aux parents.
- **Bulletins de notes officiels (QWeb PDF)** : Format marocain complet avec coefficients par matière, totaux pondérés, moyennes d'examen et de contrôle continu, moyenne générale de la classe, rang de l'élève, et mentions officielles (*Félicitations, Encouragements, Tableau d'honneur, Avertissement*).
- **Conseil de classe & Délibérations** : Assistant interactif générant en un clic le PV de délibération de classe avec décisions de promotion, avertissements et statistiques académiques.
- **Suivi de l'assiduité** : Enregistrement des absences et retards par créneau ou cours, justificatifs dématérialisés (pièces jointes), et statistiques automatisées d'absentéisme par classe et par élève.

### 💰 Facturation & Gestion Financière
- **Intégration native Odoo Accounting (`account.move`)** : Création automatique de véritables factures clients (`out_invoice`) en Dirhams Marocains (**MAD**), imputées sur le parent/tuteur légal, compatibles avec le plan comptable marocain (`l10n_ma`).
- **Échéanciers & Paiements fractionnés** : Génération de frais en plusieurs tranches configurables (mensuelles, trimestrielles) avec dates d'échéance automatisées.
- **Remises de fratrie dégressives** : Calcul automatique basé sur l'âge réel (date de naissance) des enfants d'un même foyer (1er aîné : 0%, 2e enfant : 10%, 3e enfant et plus : 20%).
- **Relances & Pénalités automatiques** : Action planifiée (`ir.cron`) de relance par email des impayés avec délai d'intervalle minimum anti-spam, et pénalités de retard activables en mode opt-in dans la configuration de l'école.

### 🌐 Portail Parents & Élèves & Notifications
- **Espace dédié `/my/school`** : Portail web responsive sécurisé permettant aux familles de consulter l'emploi du temps, l'assiduité, les notes publiées, télécharger les bulletins PDF officiels et régler leurs factures en ligne.
- **Alertes automatiques d'absence/retard** : Notification immédiate par email aux parents dès qu'un retard ou une absence est constaté, avec option d'opt-out dans le profil parent et architecture extensible pour canaux SMS et WhatsApp.
- **Sécurité stricte sans contournement `sudo()`** : Isolation étanche basée sur les règles d'enregistrement Odoo (`ir.rule`). Un parent ne peut accéder qu'à ses propres enfants ; un élève ne peut voir que ses propres données.

### 🚌 Opérations Quotidiennes & Logistique
- **Détection des conflits d'emploi du temps** : Vérification en temps réel des chevauchements d'horaires pour les enseignants, les salles et les classes, avec export des plannings au standard universel **iCalendar (.ics)** (compatible Google Calendar, Apple Calendar, Outlook).
- **Badges scolaires avec QR Code sécurisé** : Carte d'élève imprimable avec photo, logo et jeton cryptographique signé non-devinable (`secrets.token_urlsafe(32)`).
- **Pointage mobile instantané (`/school/attendance/scan`)** : Interface web légère pour surveillants et enseignants permettant d'enregistrer la présence d'un élève en un scan caméra ou clic.
- **Transport scolaire** : Gestion des lignes de bus, arrêts avec horaires matin/soir, affectation des chauffeurs, véhicules et contrôle automatique de la capacité des bus.
- **Bibliothèque scolaire intégrée** : Emprunts et retours avec dates limites, prolongation, amende journalière paramétrable et relances automatiques par courriel des livres non rendus.

---

## 3. Prérequis Techniques

- **Odoo** : Version **18.0** Community ou Enterprise
- **Python** : Python **3.10**, **3.11** ou **3.12**
- **Base de données** : PostgreSQL **14** ou supérieur
- **Générateur PDF** : `wkhtmltopdf` 0.12.6 avec support QT patché
- **Comptabilité marocaine** : Module officiel Odoo `l10n_ma` *(recommandé pour initialiser le plan comptable général marocain et le journal des ventes)*

---

## 4. Guide d'Installation & Configuration de l'Addons Path

### Étape 1 : Récupération du Code Source
Clonez le dépôt dans votre répertoire d'addons personnalisés :

```bash
# Exemple sous Linux
git clone https://github.com/yazaminoura/school.git /opt/odoo/custom-addons/school

# Exemple sous Windows
git clone https://github.com/yazaminoura/school.git C:\Users\pc\Documents\school
```

### Étape 2 : Configuration du paramètre `addons_path`

Ouvrez votre fichier de configuration `odoo.conf` et ajoutez le chemin absolu du dossier contenant les 4 modules dans `addons_path` (séparé par une virgule) :

#### Sous Linux / Ubuntu :
```ini
[options]
addons_path = /opt/odoo/odoo-server/addons,/opt/odoo/custom-addons/school
```

#### Sous Windows :
```ini
[options]
addons_path = c:\project\odoo_project\server\odoo\addons,C:\Users\pc\Documents\school
```

> [!IMPORTANT]
> Veillez à ce que le chemin spécifié pointe directement vers le dossier parent qui contient les répertoires `eacta_school`, `eacta_bibliotheque`, `eacta_event` et `eacta_theme`.

---

### Étape 3 : Installation des Modules

#### Option A : Installation en Mode Démonstration (Évaluation & Formation)
Pour tester immédiatement avec un jeu de données réaliste (classes 2026-2027, enseignants, élèves, parents, emplois du temps et bibliothèque) :

```bash
python odoo-bin -c odoo.conf -d school_demo -i eacta_school,eacta_bibliotheque,eacta_event,eacta_theme --stop-after-init
```

#### Option B : Installation en Mode Production (Sans Données de Démo)
Pour une mise en service réelle dans une école avec base vierge :

```bash
python odoo-bin -c odoo.conf -d school_prod -i eacta_school,eacta_bibliotheque,eacta_event,eacta_theme --without-demo=all --stop-after-init
```

---

### Étape 4 : Mise à Niveau / Mise à Jour du Code
Pour appliquer de nouvelles mises à jour sans perte de données :

```bash
python odoo-bin -c odoo.conf -d school_prod -u eacta_school,eacta_bibliotheque,eacta_event,eacta_theme --stop-after-init
```

---

## 5. Exécution de la Suite de Tests Automatisés

Tous les modules intègrent des tests unitaires et d'intégration validant le cycle des notes, le calcul des remises fratrie, la génération des factures, le contrôle des conflits d'horaires et les règles d'isolement de sécurité :

```bash
python odoo-bin -c odoo.conf -d school_test -u eacta_school,eacta_bibliotheque,eacta_event,eacta_theme --test-enable --test-tags=eacta_school,eacta_bibliotheque,eacta_event,eacta_theme --stop-after-init
```

*Résultat attendu : `0 failed, 0 error(s)` sur l'ensemble des cas de test.*

---

## 6. Matrice des Rôles & Droits d'Accès

| Rôle | Groupe Odoo | Périmètre de Visibilité |
|---|---|---|
| **Direction** | `eacta_school.group_eacta_school_direction` | Accès complet : validation des notes, délibérations, gestion des classes, audits, statistiques d'assiduité globales. |
| **Enseignant** | `eacta_school.group_eacta_school_teacher` | Accès restreint à ses propres classes et cours : saisie et soumission des notes, pointage de ses créneaux, consultation de son planning. Aucun accès aux finances. |
| **Comptable** | `eacta_school.group_eacta_school_finance` | Gestion des frais de scolarité, génération des échéanciers, factures clients Odoo, encaissements et relances. |
| **Parent** | `base.group_portal` + `is_school_parent=True` | Portail `/my/school` : consultation stricte de ses propres enfants (notes publiées, bulletins PDF, assiduité, factures). |
| **Élève** | `base.group_portal` + `eacta_school.group_eacta_school_student` | Consultation de son propre emploi du temps, notes publiées et historique d'assiduité. |

---

## 7. Comptes de Démonstration (Quickstart)

| Identifiant | Rôle | Description |
|---|---|---|
| `admin` | Administrateur Système | Configuration complète et paramétrage général |
| `amina.benali@demo.nrschool.com` | Enseignante (Mathématiques) | Saisie de notes et consultation d'emploi du temps |
| `parent.alami@demo.nrschool.com` | Parent d'élève | Accès portail pour consulter les dossiers de ses enfants |
| `david.moreau@demo.nrschool.com` | Élève | Accès portail étudiant (planning, bulletins, badge QR) |

---

## 8. Licence

Cette suite logicielle est distribuée sous licence **LGPL-3** (GNU Lesser General Public License v3.0).
Copyright &copy; 2026 NR School. Tous droits réservés.
