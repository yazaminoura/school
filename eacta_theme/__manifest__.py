# -*- coding: utf-8 -*-
{
    'name': 'NR School - Thème',
    'version': '18.0.3.0',
    'category': 'Theme/Backend',
    'summary': "Charte graphique de l'établissement pour l'interface Odoo",
    'description': """
Thème NR School
===============
- Styles prêts à l'emploi (NR School, Indigo, Émeraude, Océan, Violet, Minimal clair, Terracotta)
- Couleurs, police (Inter, Poppins, Nunito, Cairo), barre de navigation dégradée / pleine / claire
- Cartes modernes / encadrées / plates, arrondis, badges, densité confortable ou compacte
- Aperçu en direct dans la fiche du style, application en un clic
- Page de connexion aux couleurs de l'établissement
- CSS personnalisé
    """,
    'author': 'NR School',
    'website': 'https://www.e-acta.com',
    'license': 'LGPL-3',
    'depends': ['base', 'web', 'eacta_school'],
    'data': [
        'security/ir.model.access.csv',
        'data/theme_presets.xml',
        'views/theme_config_views.xml',
        'views/dynamic_styles.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'eacta_theme/static/src/scss/eacta_theme.scss',
            'eacta_theme/static/src/apps_menu/apps_menu.scss',
            'eacta_theme/static/src/apps_menu/apps_menu.js',
            'eacta_theme/static/src/apps_menu/apps_menu.xml',
        ],
    },
    'images': ['static/description/icon.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
