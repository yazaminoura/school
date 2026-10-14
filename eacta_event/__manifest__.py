{
    'name': 'NR School - Événements',
    'version': '18.0.2.0',
    'summary': "Sorties, voyages, cérémonies et réunions : inscriptions, autorisations parentales, présences",
    'description': """
Événements scolaires NR School
==============================
- Types d'événements, workflow Brouillon → Confirmé → Terminé, calendrier
- Classes concernées, inscription d'une classe entière en un clic, nombre de places
- Autorisations parentales, participation financière, pointage des présences
- Feuille de présence et lettres d'autorisation parentale imprimables
- Bouton « Événements » sur la fiche élève
    """,
    'category': 'Education',
    'author': 'NR School',
    'license': 'LGPL-3',
    'icon': '/eacta_event/static/description/icon.png',
    'depends': ['base', 'mail', 'web', 'eacta_school'],
    'data': [
        'security/event_security.xml',
        'security/ir.model.access.csv',
        'security/event_rules.xml',
        'reports/event_reports.xml',
        'views/eacta_school_event.xml',
    ],
    'demo': [
        'demo/event_demo.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'eacta_event/static/src/event.scss',
        ],
    },
    'installable': True,
    'application': True,
    'sequence': 3,
}
