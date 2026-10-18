# NR School - Bibliothèque Scolaire (`eacta_bibliotheque`)

Module de gestion de bibliothèque scolaire intégré pour Odoo 18.0.

## Fonctionnalités Principales

1. **Catalogue des Ouvrages**
   - Fiches livres détaillées : titre, auteurs, éditeur, ISBN, langue, cote CDU, thématiques.
   - Gestion des exemplaires physiques avec code-barres généré automatiquement.
   - Suivi en temps réel de la disponibilité (en rayon, emprunté, réservé, perdu, déclassé).

2. **Gestion des Emprunts & Retours**
   - Emprunts pour élèves et professeurs avec dates limites configurables.
   - Prolongations autorisées selon les règles de l'établissement.
   - Gestion des déclarations de perte et dédommagement.
   - Guichet rapide de prêt et retour par lecture code-barres (`library.desk.wizard`).

3. **Retards & Amendes**
   - Contrôle quotidien des emprunts échus via action planifiée.
   - Notification et relance automatique par e-mail.
   - Calcul optionnel d'une indemnité de retard par jour de dépassement.

4. **Intégration Élève & Statistiques**
   - Onglet « Bibliothèque » direct sur la fiche élève de `eacta_school`.
   - Historique complet des lectures et emprunts en cours.
   - Tableau de bord interactif avec indicateurs clés (taux d'occupation, livres les plus demandés, emprunts par classe).
   - Impression des étiquettes code-barres pour les rayonnages et les livres.

## Rôles & Sécurité

- **Responsable Bibliothèque** (`eacta_bibliotheque.group_library_manager`) : Gestion complète du fonds, modification des exemplaires, annulation et gestion des amendes.
- **Opérateur de Guichet** (`eacta_bibliotheque.group_library_user`) : Saisie des prêts et retours, consultation du catalogue.

## Installation

```bash
odoo -d <database_name> -i eacta_bibliothque --stop-after-init
```
