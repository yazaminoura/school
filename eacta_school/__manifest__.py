{

    'name': 'E-ACTA School Management',
    'icon': '/eacta_school/static/src/img/logoE.png',

    'version': '1.0',

    'summary': 'Gérez votre école avec E-ACTA',

    'description': """ 

        Module de gestion d'école pour E-ACTA : 

        - Gestion des élèves 

        - Gestion des classes 

        - Gestion des cours 

    """,

    'category': 'Education',

    'author': 'E-ACTA',

    'website': 'https://www.e-acta.com',

    'depends': ['base','mail'],

'data': [
        'data/school_data_classes.xml',
        'data/school_data_courses_students.xml',
        'security/eacta_school_security.xml',
        'security/eacta_school_rules.xml',
        'security/ir.model.access.csv',
	    'views/eacta_menu.xml',
        'views/eacta_student_views.xml',
        'views/eacta_course_views.xml',
        'views/eacta_class_views.xml',
        'data/eacta_school_data.xml',
        'views/eacta_course_category_views.xml',
        'views/eacta_school_level_views.xml',
        'views/res_partner_views.xml',
        'views/res_users_views.xml',
        'data/eacta_school_config_data.xml',
        'reports/report_assets.xml',
        'reports/student_report.xml',
        'views/eacta_course_grade_views.xml',
        'views/eacta_exam_views.xml',
     ],

'assets': {
   'web.report_assets_common': [
           'eacta_school/static/src/css/eacta_school_report_assets.css',
            'eacta_school/static/src/css/class_kanban.css',

   ],
   },

    'demo': [],

    'installable': True,

    'application': True,

    'auto_install': False,

    'sequence': 1,
}
