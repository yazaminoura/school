# NR School - Gestion Scolaire (`eacta_school`)

Module central de gestion scolaire pour Odoo 18.0, adapté au système éducatif marocain (notation sur 20, 3 trimestres, coefficients par matière, mentions d'honneur et décisions de fin d'année).

## Fonctionnalités Principales

1. **Années Académiques & Trimestres**
   - Modèle `eacta.academic.year` avec contrôle d'intégrité (une seule année ouverte à la fois).
   - Modèle `eacta.term` avec contrôle de dates sans chevauchement et incluses dans l'année.
   - Périodisation stricte des classes, examens, notes et emplois du temps.

2. **Calcul des Notes et Bulletins Scolaires**
   - Moyenne de matière : moyenne pondérée des types d'examens (contrôles continus, devoirs surveillés, oraux, examens trimestriels configurables).
   - Moyenne trimestrielle : somme pondérée par les coefficients des matières actives.
   - Moyenne annuelle : moyenne pondérée des trimestres.
   - Gestion des absences aux examens : exclusion ou zéro si absence non justifiée.
   - Classement dense avec ex aequo sans saut de rang.
   - Distinctions du conseil (Félicitations, Tableau d'honneur, Compliments, Encouragements).
   - Bulletin de notes imprimable (QWeb) par trimestre et annuel.

3. **Assiduité & Alertes Automatiques**
   - Pointage des absences et retards par créneau (matin, après-midi, créneau horaire).
   - Contrainte stricte d'unicité (élève, date, créneau, type) et interdiction des dates futures.
   - Motif obligatoire en cas d'absence justifiée.
   - Alerte automatique configurable (ex. dès 3 absences non justifiées par mois) avec création d'une activité pour le professeur principal et publication dans le chatter.
   - Vues d'analyse graphique et tableau croisé dynamique (pivot).

4. **Finances & Frais de Scolarité**
   - Échéancier en mensualités ou trimestres avec répartition exacte des centimes.
   - Règle de remise fratrie configurable (%).
   - Paiements sécurisés et immuables avec audit trail.
   - Gestion des remboursements liés aux paiements originaux.
   - Pénalités de retard configurables avec action planifiée (cron) quotidienne.
   - Reçu de paiement et relevé de compte élève imprimables.
   - Intégration transparente avec la comptabilité standard Odoo (`account.move` et `account.payment`) si le module `account` est installé.

5. **Emplois du Temps & Classes**
   - Détection en temps réel des conflits de créneaux (enseignant, salle, classe).
   - Prise en compte des dates d'ouverture/fermeture des classes et des créneaux inactifs.
   - Vérification de l'attribution enseignant-matière.
   - Assistant de promotion annuelle (passage en classe supérieure, redoublement ou diplôme avec report du solde financier).

## Rôles & Sécurité

| Rôle | Groupe | Droits & Restrictions |
|---|---|---|
| **Direction / Manager** | `group_eacta_school_manager` | Accès complet, réouverture des examens/années, annulation financière, configuration globale. |
| **Professeur** | `group_eacta_school_teacher` | Accès limité à ses propres classes et matières. Saisie des notes de ses cours. **Aucun accès** aux données médicales, ni aux finances/frais. |
| **Secrétaire** | `group_eacta_school_secretary` | Gestion des inscriptions, fiches élèves, assiduité, données médicales d'urgence. Aucun droit de modification des notes. |
| **Finance** | `group_eacta_school_finance` | Gestion exclusive des frais de scolarité, encaissements, reçus et remises. Pas d'accès aux notes académiques. |
| **Parent / Élève (Portail)** | `base.group_portal` | Consultation sécurisée limitée aux enfants du parent connecté (bulletins, assiduité, calendrier, solde). |

## Installation & Mise à Niveau

```bash
# Installation sur une base existante
odoo -d <database_name> -i eacta_school --stop-after-init

# Mise à niveau (migration automatique sans perte de données)
odoo -d <database_name> -u eacta_school --stop-after-init

# Exécution des tests unitaires
odoo -d <database_name> -u eacta_school --test-enable --test-tags=eacta_school --stop-after-init
```

## Configuration

Rendez-vous dans **Configuration > Paramètres > NR School** :
- **Pondérations des examens** : Contrôle continu (1.0), Devoir (1.0), Oral (1.0), Examen final (3.0), etc.
- **Politique d'absence aux examens** : Exclure du calcul ou compter 0 si non justifiée.
- **Note seuil d'admission** : 10.0 / 20 par défaut.
- **Seuil d'alerte assiduité** : 3 absences non justifiées par mois.
- **Remise fratrie** : Activer et définir le pourcentage (ex: 10%).
- **Pénalité de retard** : Forfaitaire ou en pourcentage du solde en retard.
