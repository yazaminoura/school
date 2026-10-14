from odoo import api, fields, models


class EactaStudent(models.Model):
    _inherit = 'eacta.student'

    library_loan_ids = fields.One2many('library.loan', 'student_id', string="Emprunts")
    borrowed_book_count = fields.Integer(string="Livres empruntés", compute='_compute_borrowed_book_count')

    library_overdue_count = fields.Integer(string="Livres en retard", compute='_compute_borrowed_book_count')

    @api.depends('library_loan_ids.state')
    def _compute_borrowed_book_count(self):
        for student in self:
            active = student.library_loan_ids.filtered(lambda l: l.state in ('ongoing', 'overdue'))
            student.borrowed_book_count = len(active)
            student.library_overdue_count = len(active.filtered(lambda l: l.state == 'overdue'))

    def action_new_library_loan(self):
        self.ensure_one()
        return {
            'name': f"Guichet Express - {self.name}",
            'type': 'ir.actions.act_window',
            'res_model': 'library.desk.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_student_id': self.id, 'default_borrower_type': 'student', 'default_mode': 'checkout'},
        }

    def action_view_borrowed_books(self):
        self.ensure_one()
        return {
            'name': f"Emprunts de {self.name}",
            'type': 'ir.actions.act_window',
            'res_model': 'library.loan',
            'view_mode': 'list,form',
            'domain': [('student_id', '=', self.id)],
            'context': {'default_student_id': self.id, 'default_borrower_type': 'student'},
        }
