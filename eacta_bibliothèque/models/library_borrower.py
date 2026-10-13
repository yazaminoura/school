from odoo import models, fields, api


class LibraryBorrower(models.Model):
    _name = 'library.borrower'
    _description = 'Library Borrower'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Name', required=True, tracking=True)
    email = fields.Char(string='Email', tracking=True)
    borrower_type = fields.Selection([
        ('student', 'Élève'),
        ('teacher', 'Professeur'),
    ], string="Type d'emprunteur", required=True, default='student', tracking=True)

    student_id = fields.Many2one('eacta.student', string="Élève")
    teacher_id = fields.Many2one('res.users', string="Professeur")
    loan_ids = fields.One2many('library.loan', 'borrower_id', string='Emprunts')

    # FIX: Update compute methods for single-copy loans
    active_loans_count = fields.Integer(string='Emprunts actifs', compute='_compute_loan_counts', store=True)
    total_loans_count = fields.Integer(string='Total des emprunts', compute='_compute_loan_counts', store=True)
    overdue_loans_count = fields.Integer(string='Emprunts en retard', compute='_compute_loan_counts', store=True)

    @api.depends('loan_ids', 'loan_ids.returned', 'loan_ids.is_overdue')
    def _compute_loan_counts(self):
        for borrower in self:
            loans = borrower.loan_ids
            borrower.total_loans_count = len(loans)
            borrower.active_loans_count = len(loans.filtered(lambda l: not l.returned))
            borrower.overdue_loans_count = len(loans.filtered(lambda l: l.is_overdue and not l.returned))

    def open_loans(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Emprunts de {self.name}',
            'res_model': 'library.loan',
            'view_mode': 'kanban,tree,form',
            'domain': [('borrower_id', '=', self.id)],
            'context': {'default_borrower_id': self.id}
        }

    def action_view_loans(self):
        return self.open_loans()

    @api.model
    def create(self, vals):
        if vals.get('borrower_type') == 'student' and vals.get('student_id'):
            student = self.env['eacta.student'].browse(vals['student_id'])
            vals['name'] = student.name
        elif vals.get('borrower_type') == 'teacher' and vals.get('teacher_id'):
            teacher = self.env['res.users'].browse(vals['teacher_id'])
            vals['name'] = teacher.name
        return super(LibraryBorrower, self).create(vals)