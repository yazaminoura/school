from odoo import models, fields, api
from odoo.exceptions import ValidationError
import json
import logging
from datetime import datetime, date

_logger = logging.getLogger(__name__)


class LibraryLoan(models.Model):
    _name = 'library.loan'
    _description = 'Library Loan'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Nom', compute='_compute_name', store=True)
    checkout_date = fields.Date(string="Date d'emprunt", required=True, default=fields.Date.today, tracking=True)
    due_date = fields.Date(string="Date de retour prévue", required=True, tracking=True)
    book_id = fields.Many2one(
        'library.book',
        string="Livre",
        required=True,
        tracking=True,
        ondelete='cascade',
        domain="[('category_id', '=', category_id)]"
    )

    # SINGLE COPY: Replace Many2many with Many2one
    barcode_id = fields.Many2one(
        'library.book.barcode',
        string='Code-barres emprunté',
        domain="[('book_id', '=', book_id), ('is_available', '=', True)]",
        required=True
    )

    returned_barcode_id = fields.Many2one('library.book.barcode', string='Code-barres retourné')

    # REMOVED: Multi-copy fields
    # barcode_ids, returned_barcode_ids, copies_count, returned_copies_count, requested_copies

    returned = fields.Boolean(string="Retourné", default=False, tracking=True)
    is_overdue = fields.Boolean(string="En retard", compute="_compute_is_overdue", store=True)
    was_overdue = fields.Boolean(string="Était en retard", compute="_compute_was_overdue", store=True)
    responsible_id = fields.Many2one(
        'res.users', string="Responsable d'emprunt", default=lambda self: self.env.user, required=True, tracking=True,
        readonly=True
    )
    processed_date = fields.Datetime(
        string="Emprunté le", default=lambda self: fields.Datetime.now(), tracking=True, readonly=True
    )
    return_responsible_id = fields.Many2one('res.users', string="Responsable retour", tracking=True, readonly=True)
    return_date = fields.Date(string="Retourné le", tracking=True)
    return_notes = fields.Text(string="Notes de retour")

    category_id = fields.Many2one(
        'library.book.category',
        string='Catégorie',
        required=True,
        tracking=True
    )

    @api.onchange('category_id')
    def _onchange_category_id(self):
        if self.category_id and self.category_id != self._origin.category_id:
            self.book_id = False
            self.barcode_id = False

    @api.onchange('book_id')
    def _onchange_book_id(self):
        if self.book_id and self.checkout_date:
            self.due_date = fields.Date.add(self.checkout_date, days=self.book_id.loan_duration_days)
        if self.book_id and self._origin.book_id != self.book_id:
            self.barcode_id = False

    @api.onchange('returned')
    def _onchange_returned(self):
        if self.returned:
            self.returned_barcode_id = self.barcode_id
            self.return_responsible_id = self.env.user
            self.return_date = fields.Date.today()
        else:
            self.returned_barcode_id = False
            self.return_responsible_id = False
            self.return_date = False

    @api.constrains('checkout_date', 'due_date')
    def _check_dates(self):
        for loan in self:
            if loan.checkout_date and loan.due_date and loan.checkout_date > loan.due_date:
                raise ValidationError("La date d'emprunt doit être antérieure à la date de retour prévue.")

    @api.constrains('barcode_id')
    def _check_barcode(self):
        for loan in self:
            if not loan.barcode_id:
                raise ValidationError("Vous devez sélectionner un code-barres.")

            if loan.barcode_id.book_id != loan.book_id:
                raise ValidationError(
                    f"Le code-barres '{loan.barcode_id.barcode}' n'appartient pas au livre '{loan.book_id.name}'.")

            # Check if barcode is already borrowed
            if loan.checkout_date and loan.due_date:
                overlapping_loans = self.env['library.loan'].search([
                    ('barcode_id', '=', loan.barcode_id.id),
                    ('returned', '=', False),
                    ('id', '!=', loan.id)
                ])
                if overlapping_loans:
                    raise ValidationError(
                        f"Le code-barres '{loan.barcode_id.barcode}' est déjà emprunté.")

    @api.depends('due_date', 'returned')
    def _compute_is_overdue(self):
        for loan in self:
            loan.is_overdue = loan.due_date and not loan.returned and loan.due_date < fields.Date.today()

    @api.depends('due_date', 'return_date', 'returned')
    def _compute_was_overdue(self):
        for loan in self:
            loan.was_overdue = loan.returned and loan.return_date and loan.due_date and loan.return_date > loan.due_date

    complete_return = fields.Boolean(
        string="Retour complet",
        compute="_compute_complete_return",
        store=True
    )

    @api.depends('returned', 'returned_barcode_id')
    def _compute_complete_return(self):
        for loan in self:
            loan.complete_return = loan.returned and loan.returned_barcode_id.id == loan.barcode_id.id

    borrower_type = fields.Selection([
        ('student', 'Élève'),
        ('teacher', 'Professeur'),
    ], string="Type d'utilisateur", required=True, tracking=True)

    student_id = fields.Many2one('eacta.student', string="Élève")
    teacher_id = fields.Many2one('res.users', string="Professeur")
    borrower_id = fields.Many2one('library.borrower', string='Emprunteur', ondelete='cascade')

    @api.model
    def create(self, vals):
        # Create borrower record if needed
        if 'borrower_id' not in vals:
            borrower_vals = {
                'borrower_type': vals.get('borrower_type', 'student'),
            }

            if vals.get('borrower_type') == 'student' and vals.get('student_id'):
                borrower_vals['student_id'] = vals['student_id']
                student = self.env['eacta.student'].browse(vals['student_id'])
                borrower_vals['name'] = student.name
            elif vals.get('borrower_type') == 'teacher' and vals.get('teacher_id'):
                borrower_vals['teacher_id'] = vals['teacher_id']
                teacher = self.env['res.users'].browse(vals['teacher_id'])
                borrower_vals['name'] = teacher.name

            domain = []
            if borrower_vals.get('student_id'):
                domain = [('student_id', '=', borrower_vals['student_id'])]
            elif borrower_vals.get('teacher_id'):
                domain = [('teacher_id', '=', borrower_vals['teacher_id'])]

            existing_borrower = self.env['library.borrower'].search(domain, limit=1)

            if existing_borrower:
                vals['borrower_id'] = existing_borrower.id
            else:
                borrower = self.env['library.borrower'].create(borrower_vals)
                vals['borrower_id'] = borrower.id

        if 'responsible_id' not in vals:
            vals['responsible_id'] = self.env.user.id
        if 'processed_date' not in vals:
            vals['processed_date'] = fields.Datetime.now()
        return super(LibraryLoan, self).create(vals)

    @api.depends('book_id', 'borrower_type', 'student_id', 'teacher_id', 'barcode_id')
    def _compute_name(self):
        for loan in self:
            book_name = loan.book_id.name if loan.book_id else ''
            borrower_name = ''
            if loan.borrower_type == 'student' and loan.student_id:
                borrower_name = loan.student_id.name
            elif loan.borrower_type == 'teacher' and loan.teacher_id:
                borrower_name = loan.teacher_id.name

            barcode_info = f" - {loan.barcode_id.barcode}" if loan.barcode_id else ""
            loan.name = f"{book_name} - {borrower_name}{barcode_info}"

    def action_return_book(self):
        for loan in self:
            if not loan.returned:
                loan.write({
                    'returned': True,
                    'return_responsible_id': self.env.user.id,
                    'return_date': fields.Date.today(),
                    'returned_barcode_id': loan.barcode_id.id
                })
        return True

    def action_view_details(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'library.loan',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'current',
        }