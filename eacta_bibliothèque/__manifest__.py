{
    'name': 'Eacta Bibliothèque',
    'icon': 'eacta_bibliothèque/static/description/icon.png',
    'version': '1.0',
    'summary': 'Manage library books, borrowers, and loans for E-ACTA School',
    'depends': ['base', 'eacta_school', 'mail', 'web'],
    'data': [
        'data/library_demo.xml',
        'security/library_security.xml',
        'security/ir.model.access.csv',
        'views/library_views.xml',
        'views/library_category_views.xml',
        'security/library_rules.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}