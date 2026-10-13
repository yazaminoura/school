{
    'name': 'EACTA Event',
    'icon': 'eacta_event\static\desciption\icon.png',
    'version': '1.0',
    'license': 'LGPL-3',
    'depends': ['base', 'mail', 'eacta_school'],
    'author': 'Votre Nom',
    'category': 'Education',
    'summary': 'Gestion des événements scolaires EACTA',
    'description': """
        Ce module ajoute la gestion des événements scolaires à EACTA.
    """,
    'data': [
        'security/event_security.xml',
        'security/ir.model.access.csv',
        'security/event_rules.xml',
        'views/eacta_school_event.xml',
    ],
    'installable': True,
    'application': True,
}
