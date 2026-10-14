from odoo import api, fields, models


class LibraryBorrower(models.Model):
    _name = 'library.borrower'
    _description = 'Lecteur'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(string='Nom', required=True, tracking=True)
    email = fields.Char(string='E-mail', tracking=True)
    phone = fields.Char(string='Téléphone')
    borrower_type = fields.Selection([
        ('student', 'Élève'),
        ('teacher', 'Enseignant'),
    ], string="Type de lecteur", required=True, default='student', tracking=True)
    student_id = fields.Many2one('eacta.student', string="Élève", index=True)
    teacher_id = fields.Many2one('res.users', string="Enseignant", index=True)
    class_id = fields.Many2one(related='student_id.current_class_id', string='Classe')
    image_128 = fields.Image(compute='_compute_image_128', string='Photo')
    active = fields.Boolean(default=True)
    loan_ids = fields.One2many('library.loan', 'borrower_id', string='Emprunts')

    active_loans_count = fields.Integer(string='Emprunts en cours', compute='_compute_loan_counts', store=True)
    total_loans_count = fields.Integer(string='Total des emprunts', compute='_compute_loan_counts', store=True)
    overdue_loans_count = fields.Integer(string='En retard', compute='_compute_loan_counts', store=True)
    fine_due = fields.Float(string='Amendes dues', compute='_compute_loan_counts', store=True)

    _sql_constraints = [
        ('student_unique', 'UNIQUE(student_id)', "Cet élève a déjà une fiche lecteur."),
        ('teacher_unique', 'UNIQUE(teacher_id)', "Cet enseignant a déjà une fiche lecteur."),
    ]

    @api.depends('loan_ids.state', 'loan_ids.fine_amount', 'loan_ids.fine_paid')
    def _compute_loan_counts(self):
        for borrower in self:
            loans = borrower.loan_ids
            borrower.total_loans_count = len(loans)
            borrower.active_loans_count = len(loans.filtered(lambda l: l.state in ('ongoing', 'overdue')))
            borrower.overdue_loans_count = len(loans.filtered(lambda l: l.state == 'overdue'))
            borrower.fine_due = sum(loans.filtered(lambda l: not l.fine_paid).mapped('fine_amount'))

    @api.depends('student_id.image_128', 'teacher_id.image_128')
    def _compute_image_128(self):
        for borrower in self:
            borrower.image_128 = borrower.student_id.image_128 or borrower.teacher_id.image_128

    @api.model
    def _prepare_vals(self, vals):
        if vals.get('borrower_type', 'student') == 'student' and vals.get('student_id'):
            student = self.env['eacta.student'].browse(vals['student_id'])
            vals.setdefault('name', student.name)
            vals.setdefault('email', student.email)
            vals.setdefault('phone', student.phone)
        elif vals.get('teacher_id'):
            teacher = self.env['res.users'].browse(vals['teacher_id'])
            vals.setdefault('name', teacher.name)
            vals.setdefault('email', teacher.email)
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        return super().create([self._prepare_vals(dict(vals)) for vals in vals_list])

    @api.model
    def _get_or_create(self, borrower_type, student_id=False, teacher_id=False):
        domain = [('student_id', '=', student_id)] if borrower_type == 'student' else [('teacher_id', '=', teacher_id)]
        borrower = self.with_context(active_test=False).search(domain, limit=1)
        if not borrower:
            borrower = self.create({
                'borrower_type': borrower_type,
                'student_id': student_id if borrower_type == 'student' else False,
                'teacher_id': teacher_id if borrower_type == 'teacher' else False,
            })
        return borrower

    def open_loans(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Emprunts de {self.name}',
            'res_model': 'library.loan',
            'view_mode': 'list,kanban,form',
            'domain': [('borrower_id', '=', self.id)],
            'context': {
                'default_borrower_type': self.borrower_type,
                'default_student_id': self.student_id.id,
                'default_teacher_id': self.teacher_id.id,
            },
        }

    action_view_loans = open_loans
