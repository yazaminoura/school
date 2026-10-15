# NR School - Événements Scolaires (`eacta_event`)

Module de gestion des activités périscolaires, sorties pédagogiques, voyages scolaires et réunions pour Odoo 18.0.

## Fonctionnalités Principales

1. **Planification & Calendrier**
   - Types d'événements personnalisables (sortie musée, excursion, fête de fin d'année, réunion pédagogique).
   - Workflow d'approbation : Brouillon → Confirmé → En cours → Terminé / Annulé.
   - Vue Calendrier et Gantt pour visualiser la programmation sur l'année scolaire.

2. **Inscriptions & Classes**
   - Association des classes participantes.
   - Inscription d'une classe complète en un clic avec respect du nombre de places disponibles.
   - Désistements et liste d'attente.

3. **Autorisations Parentales & Présences**
   - Suivi nominatif du retour des autorisations parentales signées.
   - Fiche d'autorisation parentale personnalisée prête à imprimer par élève.
   - Pointage des présences sur le terrain (feuille d'émargement imprimable).

4. **Participation Financière & Intégration Élève**
   - Gestion des frais de participation par événement.
   - Statut de règlement par participant.
   - Bouton intelligent « Événements » sur la fiche de l'élève (`eacta.student`).

## Rôles & Sécurité

- **Responsable des Événements** (`eacta_event.group_event_manager`) : Création, modification du budget, validation finale et annulation.
- **Enseignant / Accompagnateur** (`eacta_event.group_event_user`) : Consultation, validation des inscriptions de ses classes, pointage des présences.

## Installation

```bash
odoo -d <database_name> -i eacta_event --stop-after-init
```
