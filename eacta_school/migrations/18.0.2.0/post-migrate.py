from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Attribue un matricule aux élèves existants et recalcule les champs stockés ajoutés."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    students = env['eacta.student'].with_context(active_test=False).search([('code', '=', False)], order='id')
    sequence = env['ir.sequence']
    for student in students:
        student.code = sequence.next_by_code('eacta.student.code')
    all_students = env['eacta.student'].with_context(active_test=False).search([])
    env.add_to_compute(all_students._fields['current_class_id'], all_students)
    env.add_to_compute(all_students._fields['average'], all_students)
    classes = env['eacta.class'].with_context(active_test=False).search([])
    env.add_to_compute(classes._fields['student_count'], classes)
    all_students.flush_recordset()
    classes.flush_recordset()
