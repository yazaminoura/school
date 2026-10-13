{
    'name': 'NR School - Événements',
    'icon': '/eacta_event/static/desciption/icon.png',
    'version': '18.0.1.1',
    'license': 'LGPL-3',
    'depends': ['base', 'mail', 'eacta_school'],
    'author': 'NR School',
    'category': 'Education',
    'summary': 'Gestion des événements scolaires NR School',
    'description': """
        Ce module ajoute la gestion des événements scolaires à NR School.
    """,
    'data': [
        'security/event_security.xml',
        'security/ir.model.access.csv',
        'security/event_rules.xml',
        'views/eacta_school_event.xml',
    ],
    'installable': True,
    'application': False,
}
