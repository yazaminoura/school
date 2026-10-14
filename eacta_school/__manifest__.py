{
    'name': 'NR School',
    'version': '18.0.2.2',
    'summary': 'Gestion scolaire : élèves, classes, cours, examens, notes, assiduité et attestations',
    'description': """
NR School - Gestion scolaire
============================
- Tableau de bord : effectifs, remplissage des classes, examens à venir, répartition des notes
- Élèves : matricule automatique, parents/tuteurs, parcours, moyenne pondérée, rang, assiduité, santé
- Assiduité & Absences : suivi des absences justifiées/non justifiées, retards, créneaux
- Classes : capacité et remplissage, contrôle « une classe par année », résultats de la classe
- Cours & examens : coefficients, crédits, types d'examen, feuille de notes générée en un clic
- Notes : statuts (à noter, noté, absent, dispensé), analyse pivot / graphique
- Rapports officiels : bulletin scolaire et attestation de scolarité en un clic
    """,
    'category': 'Education',
    'author': 'NR School',
    'website': 'https://www.e-acta.com',
    'license': 'LGPL-3',
    'icon': '/eacta_school/static/src/img/nr_school_icon.png',
    'depends': ['base', 'mail', 'web'],
    'data': [
        'security/eacta_school_security.xml',
        'security/ir.model.access.csv',
        'security/eacta_school_rules.xml',
        'data/eacta_school_config_data.xml',
        'data/eacta_school_finance_data.xml',
        'reports/report_assets.xml',
        'reports/student_report.xml',
        'reports/student_certificate_report.xml',
        'reports/school_admin_reports.xml',
        'views/eacta_student_views.xml',
        'views/eacta_attendance_views.xml',
        'views/eacta_class_views.xml',
        'views/eacta_course_views.xml',
        'views/eacta_exam_views.xml',
        'views/eacta_course_grade_views.xml',
        'views/eacta_school_level_views.xml',
        'views/eacta_course_category_views.xml',
        'views/res_partner_views.xml',
        'views/res_users_views.xml',
        'views/eacta_timetable_views.xml',
        'views/eacta_fee_views.xml',
        'wizard/eacta_promotion_wizard_views.xml',
        'views/eacta_menu.xml',
    ],
    'demo': [
        'demo/school_demo_classes.xml',
        'demo/school_demo_courses_students.xml',
        'demo/school_demo_results.xml',
        'demo/school_demo_admin.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'eacta_school/static/src/scss/school.scss',
            'eacta_school/static/src/dashboard/school_dashboard.js',
            'eacta_school/static/src/dashboard/school_dashboard.xml',
            'eacta_school/static/src/timetable/timetable.scss',
            'eacta_school/static/src/timetable/timetable.js',
            'eacta_school/static/src/timetable/timetable.xml',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
    'sequence': 1,
}
