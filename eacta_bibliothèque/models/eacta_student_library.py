from odoo import api, fields, models


class EactaStudent(models.Model):
    _inherit = 'eacta.student'

    library_loan_ids = fields.One2many('library.loan', 'student_id', string="Emprunts")
    borrowed_book_count = fields.Integer(string="Livres empruntés", compute='_compute_borrowed_book_count')

    @api.depends('library_loan_ids.returned')
    def _compute_borrowed_book_count(self):
        for student in self:
            student.borrowed_book_count = len(student.library_loan_ids.filtered(lambda l: not l.returned))

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
