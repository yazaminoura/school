from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Initialise les cours sur les classes existantes si besoin."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    all_courses = env['eacta.course'].search([])
    classes = env['eacta.class'].search([])
    for klass in classes:
        if not klass.course_ids and all_courses:
            klass.course_ids = all_courses
    env.flush_all()
