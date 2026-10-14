{
    'name': 'NR School - Bibliothèque',
    'version': '18.0.2.0',
    'summary': "Catalogue, exemplaires, emprunts, retards et amendes de la bibliothèque scolaire",
    'description': """
Bibliothèque NR School
======================
- Catalogue : auteur, ISBN, éditeur, langue, cote ; exemplaires avec codes-barres générés automatiquement
- Emprunts élèves et enseignants : référence, prolongation, retour, livre perdu
- Retards : contrôle quotidien, relance planifiée, amende par jour de retard
- Limites d'emprunts simultanés et de prolongations (Réglages)
- Tableau de bord, analyse des emprunts, bon d'emprunt et étiquettes code-barres
- Onglet Bibliothèque sur la fiche élève
    """,
    'category': 'Education',
    'author': 'NR School',
    'license': 'LGPL-3',
    'icon': '/eacta_bibliothèque/static/description/icon.png',
    'depends': ['base', 'mail', 'web', 'eacta_school'],
    'data': [
        'security/library_security.xml',
        'security/ir.model.access.csv',
        'data/library_data.xml',
        'reports/library_reports.xml',
        'views/library_views.xml',
        'views/library_loan_views.xml',
        'views/library_borrower_views.xml',
        'views/eacta_student_library_views.xml',
        'views/library_menu.xml',
    ],
    'demo': [
        'demo/library_demo.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'eacta_bibliothèque/static/src/library.scss',
            'eacta_bibliothèque/static/src/dashboard/library_dashboard.js',
            'eacta_bibliothèque/static/src/dashboard/library_dashboard.xml',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
    'sequence': 2,
}
