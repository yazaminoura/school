# NR School - Thème Graphique (`eacta_theme`)

Module de personnalisation visuelle et d'habillage backend pour Odoo 18.0, offrant une interface moderne, élégante et adaptée à l'identité visuelle de l'établissement scolaire.

## Fonctionnalités Principales

1. **Styles Prêts à l'Emploi (Presets)**
   - NR School (bleu institutionnel et or)
   - Indigo
   - Émeraude
   - Océan
   - Violet
   - Minimal clair
   - Terracotta

2. **Personnalisation Complète**
   - Palette de couleurs : primaire, secondaire, arrière-plan, barre supérieure.
   - Typographies adaptées au web et à la lecture scolaire : *Inter*, *Poppins*, *Nunito*, *Cairo* (support multilingue arabe/français).
   - Barres de navigation : dégradée, pleine couleur ou claire minimale.
   - Cartes et panneaux : modernes avec ombre douce, encadrées ou plates.
   - Rayons de courbure (border-radius) et densité d'affichage (confortable ou compact).

3. **Aperçu en Direct & Page de Connexion**
   - Prévisualisation instantanée du style dans la fiche de configuration avant application.
   - Application globale en un seul clic sans redémarrage de serveur.
   - Page de connexion (login) entièrement personnalisée aux couleurs et avec le logo de l'établissement.
   - Zone CSS / SCSS personnalisé pour les ajustements avancés.

## Rôles & Accès

- **Administrateur Technique** (`base.group_system` ou `eacta_school.group_eacta_school_manager`) : Sélection et modification du style actif.

## Installation

```bash
odoo -d <database_name> -i eacta_theme --stop-after-init
```
