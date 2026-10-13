# -*- coding: utf-8 -*-
{
    'name': 'E-ACTA School Theme & Design Studio',
    'version': '1.0',
    'category': 'Theme/Education',
    'summary': 'Design moderne & styles élégants pour la gestion scolaire E-ACTA',
    'description': """
        Thème et Design Studio pour E-ACTA School Management (Odoo 18) :
        ================================================================
        - Design moderne et raffiné pour les fiches Élèves, Classes et Cours
        - Cartes Kanban interactives avec jauges de progression, statuts et badges
        - Modèle de configuration de style (eacta.theme.config) avec palettes de couleurs
        - Mise en valeur des moyennes, GPA et jauges d'effectif
        - Styles SCSS responsives et modernes
    """,
    'author': 'E-ACTA / Noura',
    'website': 'https://www.e-acta.com',
    'license': 'LGPL-3',
    'depends': ['base', 'web', 'eacta_school'],
    'data': [
        'security/ir.model.access.csv',
        'data/theme_presets.xml',
        'views/theme_config_views.xml',
        'views/eacta_student_theme_views.xml',
        'views/eacta_class_theme_views.xml',
        'views/eacta_course_theme_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'eacta_theme/static/src/scss/eacta_theme.scss',
        ],
    },
    'images': [
        'static/description/icon.png',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'sequence': 2,
}
