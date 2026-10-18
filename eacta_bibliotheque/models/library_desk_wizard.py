from datetime import timedelta
from odoo import api, fields, models
from odoo.exceptions import UserError


class LibraryDeskWizard(models.TransientModel):
    _name = 'library.desk.wizard'
    _description = "Guichet Express - Prêt & Retour"

    mode = fields.Selection([
        ('checkout', 'Nouveau prêt'),
        ('return', 'Retour de livre'),
    ], string='Opération', default='checkout', required=True)

    # ------------------------------------------------------------------
    # Prêt
    # ------------------------------------------------------------------
    borrower_type = fields.Selection([
        ('student', 'Élève'),
        ('teacher', 'Enseignant / Personnel'),
    ], string='Type d\'emprunteur', default='student', required=True)
    student_id = fields.Many2one('eacta.student', string='Élève')
    teacher_id = fields.Many2one('res.users', string='Enseignant / Personnel')
    barcode_scan = fields.Char(string='Code-barres exemplaire')
    barcode_id = fields.Many2one('library.book.barcode', string='Exemplaire',
                                domain="[('state', '=', 'available')]")
    book_id = fields.Many2one('library.book', string='Livre', compute='_compute_book_info', store=True, readonly=False)
    checkout_date = fields.Date(string="Date d'emprunt", default=fields.Date.context_today, required=True)
    due_date = fields.Date(string="À rendre avant le", compute='_compute_due_date', store=True, readonly=False)
    active_loan_ids = fields.Many2many('library.loan', string='Emprunts en cours', compute='_compute_active_loans')

    # ------------------------------------------------------------------
    # Retour
    # ------------------------------------------------------------------
    return_scan = fields.Char(string='Code-barres rendu')
    return_barcode_id = fields.Many2one('library.book.barcode', string='Exemplaire à rendre',
                                       domain="[('state', '=', 'on_loan')]")
    return_loan_id = fields.Many2one('library.loan', string='Emprunt correspondant',
                                     compute='_compute_return_loan', store=True, readonly=False)
    return_borrower = fields.Char(string='Emprunteur', related='return_loan_id.borrower_name', readonly=True)
    return_book = fields.Char(string='Livre retourné', related='return_loan_id.book_id.name', readonly=True)
    return_due_date = fields.Date(string='Échéance', related='return_loan_id.due_date', readonly=True)
    return_days_late = fields.Integer(string='Jours de retard', compute='_compute_return_fine')
    return_fine = fields.Float(string='Amende due', compute='_compute_return_fine', digits=(10, 2))
    fine_paid = fields.Boolean(string='Amende réglée au guichet', default=False)
    return_notes = fields.Text(string='Remarque au retour')

    # ------------------------------------------------------------------
    @api.onchange('barcode_scan')
    def _onchange_barcode_scan(self):
        if self.barcode_scan:
            code = self.barcode_scan.strip()
            # 1. Check if it matches a copy barcode
            copy = self.env['library.book.barcode'].search([('barcode', '=', code)], limit=1)
            if copy:
                if copy.state == 'available':
                    self.barcode_id = copy
                    self.book_id = copy.book_id
                else:
                    # If on loan, maybe the user wants to return it?
                    self.mode = 'return'
                    self.return_barcode_id = copy
            else:
                # 2. Check if it matches a student matricule
                student = self.env['eacta.student'].search([('code', '=', code)], limit=1)
                if student:
                    self.borrower_type = 'student'
                    self.student_id = student
            self.barcode_scan = False

    @api.onchange('return_scan')
    def _onchange_return_scan(self):
        if self.return_scan:
            code = self.return_scan.strip()
            copy = self.env['library.book.barcode'].search([('barcode', '=', code)], limit=1)
            if copy:
                self.return_barcode_id = copy
            self.return_scan = False

    @api.depends('barcode_id')
    def _compute_book_info(self):
        for wiz in self:
            if wiz.barcode_id:
                wiz.book_id = wiz.barcode_id.book_id

    @api.depends('book_id', 'checkout_date')
    def _compute_due_date(self):
        for wiz in self:
            if wiz.book_id and wiz.checkout_date:
                days = wiz.book_id.loan_duration_days or 14
                wiz.due_date = wiz.checkout_date + timedelta(days=days)

    @api.depends('student_id', 'teacher_id', 'borrower_type')
    def _compute_active_loans(self):
        for wiz in self:
            Loan = self.env['library.loan']
            domain = [('returned', '=', False), ('is_lost', '=', False)]
            if wiz.borrower_type == 'student' and wiz.student_id:
                domain.append(('student_id', '=', wiz.student_id.id))
                wiz.active_loan_ids = Loan.search(domain)
            elif wiz.borrower_type == 'teacher' and wiz.teacher_id:
                domain.append(('teacher_id', '=', wiz.teacher_id.id))
                wiz.active_loan_ids = Loan.search(domain)
            else:
                wiz.active_loan_ids = [(5, 0, 0)]

    @api.depends('return_barcode_id')
    def _compute_return_loan(self):
        for wiz in self:
            if wiz.return_barcode_id:
                loan = self.env['library.loan'].search([
                    ('barcode_id', '=', wiz.return_barcode_id.id),
                    ('returned', '=', False),
                    ('is_lost', '=', False),
                ], limit=1)
                wiz.return_loan_id = loan
            else:
                wiz.return_loan_id = False

    @api.depends('return_loan_id', 'return_loan_id.due_date')
    def _compute_return_fine(self):
        today = fields.Date.context_today(self)
        fine_param = self.env['ir.config_parameter'].sudo().get_param('library.fine_per_day', '1.0')
        fine_per_day = float(fine_param or 1.0)
        for wiz in self:
            if wiz.return_loan_id and wiz.return_loan_id.due_date:
                late = max((today - wiz.return_loan_id.due_date).days, 0)
                wiz.return_days_late = late
                wiz.return_fine = round(late * fine_per_day, 2)
            else:
                wiz.return_days_late = 0
                wiz.return_fine = 0.0

    # ------------------------------------------------------------------
    def action_checkout(self):
        self.ensure_one()
        if not self.barcode_id:
            raise UserError("Veuillez sélectionner ou scanner un exemplaire.")
        if self.borrower_type == 'student' and not self.student_id:
            raise UserError("Veuillez sélectionner l'élève emprunteur.")
        if self.borrower_type == 'teacher' and not self.teacher_id:
            raise UserError("Veuillez sélectionner l'enseignant emprunteur.")

        Loan = self.env['library.loan']
        loan = Loan.create({
            'borrower_type': self.borrower_type,
            'student_id': self.student_id.id if self.borrower_type == 'student' else False,
            'teacher_id': self.teacher_id.id if self.borrower_type == 'teacher' else False,
            'book_id': self.barcode_id.book_id.id,
            'barcode_id': self.barcode_id.id,
            'checkout_date': self.checkout_date,
            'due_date': self.due_date,
        })

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': "Prêt enregistré",
                'message': f"Livre « {loan.book_id.name} » prêté à {loan.borrower_name} jusqu'au {self.due_date}.",
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get('default_mode'):
            res['mode'] = self.env.context['default_mode']
        if self.env.context.get('default_student_id'):
            res['student_id'] = self.env.context['default_student_id']
            res['borrower_type'] = 'student'
        if self.env.context.get('default_barcode_id'):
            copy = self.env['library.book.barcode'].browse(self.env.context['default_barcode_id'])
            if copy.exists():
                res['barcode_id'] = copy.id
                res['book_id'] = copy.book_id.id
                days = copy.book_id.loan_duration_days or 14
                res['due_date'] = fields.Date.context_today(self) + timedelta(days=days)
        elif self.env.context.get('default_book_id'):
            book = self.env['library.book'].browse(self.env.context['default_book_id'])
            if book.exists():
                avail = book.barcode_ids.filtered(lambda c: c.state == 'available')[:1]
                if avail:
                    res['barcode_id'] = avail.id
                res['book_id'] = book.id
                days = book.loan_duration_days or 14
                res['due_date'] = fields.Date.context_today(self) + timedelta(days=days)
        if self.env.context.get('default_return_barcode_id'):
            copy = self.env['library.book.barcode'].browse(self.env.context['default_return_barcode_id'])
            if copy.exists():
                res['return_barcode_id'] = copy.id
                res['mode'] = 'return'
        return res

    def action_return(self):
        self.ensure_one()
        if not self.return_loan_id:
            raise UserError("Aucun emprunt en cours trouvé pour cet exemplaire.")

        loan = self.return_loan_id
        loan.write({
            'returned': True,
            'return_date': fields.Date.context_today(self),
            'return_responsible_id': self.env.user.id,
            'returned_barcode_id': loan.barcode_id.id,
            'return_notes': self.return_notes,
            'fine_paid': self.fine_paid,
        })

        msg = f"Livre « {loan.book_id.name} » rendu par {loan.borrower_name}."
        if self.return_fine:
            msg += f" (Amende de {self.return_fine:.2f} : {'Réglée' if self.fine_paid else 'À régler'})."
            if not self.fine_paid and loan.borrower_type == 'student' and loan.student_id:
                fee_type = self.env['eacta.fee.type'].search([('name', 'ilike', 'Biblioth')], limit=1)
                if not fee_type:
                    fee_type = self.env['eacta.fee.type'].create({
                        'name': 'Bibliothèque & Pénalités',
                        'sequence': 25,
                        'default_amount': self.return_fine,
                    })
                self.env['eacta.student.fee'].create({
                    'student_id': loan.student_id.id,
                    'class_id': loan.student_id.current_class_id.id if loan.student_id.current_class_id else False,
                    'fee_type_id': fee_type.id,
                    'description': f"Amende de retard ({self.return_days_late}j) : {loan.book_id.name}",
                    'amount': self.return_fine,
                    'due_date': fields.Date.context_today(self),
                })
                msg += " Facturé sur les frais scolaires de l'élève."

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': "Retour enregistré",
                'message': msg,
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }
