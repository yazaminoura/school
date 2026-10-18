from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

PARAM_DEFAULTS = {
    'enable_overdue_fines': False,
    'fine_per_day': 1.0,
    'send_overdue_reminder_email': True,
    'overdue_reminder_interval_days': 7,
    'max_loans_student': 3,
    'max_loans_teacher': 10,
    'max_renewals': 2,
}


class LibraryLoan(models.Model):
    _name = 'library.loan'
    _description = 'Emprunt'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'checkout_date desc, id desc'

    reference = fields.Char(string='Référence', readonly=True, copy=False, index=True, default='/')
    name = fields.Char(string='Libellé', compute='_compute_name', store=True)

    borrower_type = fields.Selection([
        ('student', 'Élève'),
        ('teacher', 'Enseignant'),
    ], string="Type de lecteur", required=True, default='student', tracking=True)
    student_id = fields.Many2one('eacta.student', string="Élève", tracking=True, index=True)
    teacher_id = fields.Many2one('res.users', string="Enseignant", tracking=True, domain="[('is_teacher', '=', True)]")
    borrower_id = fields.Many2one('library.borrower', string='Lecteur', ondelete='cascade', index=True, readonly=True)
    borrower_name = fields.Char(string='Emprunteur', compute='_compute_name', store=True)
    class_id = fields.Many2one(related='student_id.current_class_id', string='Classe', store=True)

    book_id = fields.Many2one('library.book', string="Livre", required=True, tracking=True, ondelete='cascade',
                              index=True)
    category_id = fields.Many2one(related='book_id.category_id', store=True, string='Catégorie')
    book_image = fields.Binary(related='book_id.image', string='Couverture')
    barcode_id = fields.Many2one(
        'library.book.barcode', string='Exemplaire', required=True, tracking=True,
        domain="[('book_id', '=', book_id), ('state', '=', 'available')]")
    returned_barcode_id = fields.Many2one('library.book.barcode', string='Exemplaire rendu')

    checkout_date = fields.Date(string="Date d'emprunt", required=True, default=fields.Date.context_today,
                                tracking=True)
    due_date = fields.Date(string="Retour prévu", required=True, tracking=True,
                           compute='_compute_due_date', store=True, readonly=False, precompute=True)
    return_date = fields.Date(string="Rendu le", tracking=True)
    returned = fields.Boolean(string="Rendu", default=False, tracking=True)
    is_lost = fields.Boolean(string="Perdu", default=False, tracking=True)
    state = fields.Selection([
        ('ongoing', 'En cours'),
        ('overdue', 'En retard'),
        ('returned', 'Rendu'),
        ('lost', 'Perdu'),
    ], string='État', compute='_compute_state', store=True, tracking=True, index=True)
    is_overdue = fields.Boolean(string="En retard", compute='_compute_state', store=True)
    was_overdue = fields.Boolean(string="Rendu en retard", compute='_compute_state', store=True)
    complete_return = fields.Boolean(string="Retour conforme", compute='_compute_state', store=True)
    days_late = fields.Integer(string='Jours de retard', compute='_compute_state', store=True)
    renew_count = fields.Integer(string='Prolongations', default=0, tracking=True)

    fine_amount = fields.Float(string='Amende', compute='_compute_state', store=True, digits=(10, 2))
    fine_paid = fields.Boolean(string='Amende réglée', tracking=True)
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    last_reminder_date = fields.Date(string="Dernière relance envoyée le", readonly=True, copy=False)
    reminder_count = fields.Integer(string="Nombre de relances", default=0, readonly=True, copy=False)

    responsible_id = fields.Many2one('res.users', string="Prêté par", default=lambda self: self.env.user,
                                     tracking=True, readonly=True)
    processed_date = fields.Datetime(string="Enregistré le", default=fields.Datetime.now, readonly=True)
    return_responsible_id = fields.Many2one('res.users', string="Retour enregistré par", readonly=True)
    return_notes = fields.Text(string="Observations au retour")
    color = fields.Integer(string='Couleur', compute='_compute_color')

    # ------------------------------------------------------------------
    @api.model
    def _param(self, key):
        value = self.env['ir.config_parameter'].sudo().get_param(f'library.{key}')
        default = PARAM_DEFAULTS[key]
        if isinstance(default, bool):
            return value in ('True', '1', True) if value not in (None, False, '') else default
        try:
            return type(default)(value) if value not in (None, False, '') else default
        except (ValueError, TypeError):
            return default

    @api.depends('book_id', 'checkout_date')
    def _compute_due_date(self):
        for loan in self:
            if loan.checkout_date and not loan.due_date:
                days = loan.book_id.loan_duration_days or 14
                loan.due_date = loan.checkout_date + timedelta(days=days)

    @api.depends('book_id.name', 'student_id.name', 'teacher_id.name', 'borrower_type')
    def _compute_name(self):
        for loan in self:
            borrower = loan.student_id if loan.borrower_type == 'student' else loan.teacher_id
            loan.borrower_name = borrower.name or ''
            loan.name = f"{loan.book_id.name or ''} - {loan.borrower_name}"

    @api.depends('returned', 'is_lost', 'due_date', 'return_date', 'returned_barcode_id', 'barcode_id')
    def _compute_state(self):
        today = fields.Date.context_today(self)
        enable_fines = self._param('enable_overdue_fines')
        fine_per_day = self._param('fine_per_day')
        for loan in self:
            end = loan.return_date if loan.returned else today
            late = (end - loan.due_date).days if loan.due_date and end else 0
            late = max(late, 0)
            if loan.is_lost:
                state = 'lost'
            elif loan.returned:
                state = 'returned'
            elif late:
                state = 'overdue'
            else:
                state = 'ongoing'
            loan.state = state
            loan.is_overdue = state == 'overdue'
            loan.was_overdue = state == 'returned' and late > 0
            loan.complete_return = state == 'returned' and loan.returned_barcode_id == loan.barcode_id
            loan.days_late = late if state != 'lost' else 0
            loan.fine_amount = round(late * fine_per_day, 2) if (enable_fines and state in ('overdue', 'returned')) else 0.0

    def _compute_color(self):
        colors = {'ongoing': 10, 'overdue': 1, 'returned': 0, 'lost': 9}
        for loan in self:
            loan.color = colors.get(loan.state, 0)

    @api.onchange('book_id')
    def _onchange_book_id(self):
        if self.book_id:
            days = self.book_id.loan_duration_days or 14
            self.due_date = (self.checkout_date or fields.Date.context_today(self)) + timedelta(days=days)
            if self.barcode_id.book_id != self.book_id:
                self.barcode_id = self.book_id.barcode_ids.filtered(lambda c: c.state == 'available')[:1]

    @api.onchange('borrower_type')
    def _onchange_borrower_type(self):
        if self.borrower_type == 'student':
            self.teacher_id = False
        else:
            self.student_id = False

    # ------------------------------------------------------------------
    @api.constrains('checkout_date', 'due_date')
    def _check_dates(self):
        for loan in self:
            if loan.checkout_date and loan.due_date and loan.checkout_date > loan.due_date:
                raise ValidationError("La date de retour prévue doit être postérieure à la date d'emprunt.")

    @api.constrains('barcode_id', 'book_id', 'returned', 'is_lost')
    def _check_copy(self):
        for loan in self:
            if loan.barcode_id.book_id != loan.book_id:
                raise ValidationError(
                    f"L'exemplaire « {loan.barcode_id.barcode} » n'appartient pas au livre « {loan.book_id.name} ».")
            if not loan.returned and not loan.is_lost:
                other = self.search([('barcode_id', '=', loan.barcode_id.id), ('id', '!=', loan.id),
                                     ('returned', '=', False), ('is_lost', '=', False)], limit=1)
                if other:
                    raise ValidationError(
                        f"L'exemplaire « {loan.barcode_id.barcode} » est déjà emprunté par {other.borrower_name}.")

    @api.constrains('borrower_type', 'student_id', 'teacher_id')
    def _check_borrower(self):
        for loan in self:
            if loan.borrower_type == 'student' and not loan.student_id:
                raise ValidationError("Sélectionnez l'élève emprunteur.")
            if loan.borrower_type == 'teacher' and not loan.teacher_id:
                raise ValidationError("Sélectionnez l'enseignant emprunteur.")

    @api.constrains('borrower_id', 'returned', 'is_lost')
    def _check_loan_limit(self):
        for loan in self.filtered(lambda l: not l.returned and not l.is_lost):
            key = 'max_loans_student' if loan.borrower_type == 'student' else 'max_loans_teacher'
            limit = self._param(key)
            active = self.search_count([('borrower_id', '=', loan.borrower_id.id), ('returned', '=', False),
                                        ('is_lost', '=', False)])
            if limit and active > limit:
                raise ValidationError(
                    f"{loan.borrower_name} a déjà atteint la limite de {limit} emprunt(s) simultané(s).")

    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        Borrower = self.env['library.borrower']
        sequence = self.env['ir.sequence']
        for vals in vals_list:
            if not vals.get('borrower_id'):
                btype = vals.get('borrower_type', 'student')
                vals['borrower_id'] = Borrower._get_or_create(
                    btype, vals.get('student_id'), vals.get('teacher_id')).id
            if not vals.get('reference') or vals['reference'] == '/':
                vals['reference'] = sequence.next_by_code('library.loan') or '/'
        return super().create(vals_list)

    @api.depends('reference', 'name')
    def _compute_display_name(self):
        for loan in self:
            loan.display_name = f"{loan.reference} · {loan.name}" if loan.reference and loan.reference != '/' else loan.name

    # ------------------------------------------------------------------
    def action_return_book(self):
        Fee = self.env['eacta.student.fee']
        fee_type = False
        today = fields.Date.context_today(self)
        enable_fines = self._param('enable_overdue_fines')
        for loan in self.filtered(lambda l: not l.returned and not l.is_lost):
            late = max((today - loan.due_date).days, 0) if loan.due_date else 0
            fine_amount = round(late * loan._param('fine_per_day'), 2) if enable_fines else 0.0
            loan.write({
                'returned': True,
                'return_date': today,
                'return_responsible_id': self.env.user.id,
                'returned_barcode_id': loan.barcode_id.id,
            })
            loan.activity_unlink(['mail.mail_activity_data_todo'])
            if enable_fines and not loan.fine_paid and fine_amount > 0 and loan.borrower_type == 'student' and loan.student_id:
                if not fee_type:
                    fee_type = self.env['eacta.fee.type'].search([('name', 'ilike', 'Biblioth')], limit=1)
                if not fee_type:
                    fee_type = self.env['eacta.fee.type'].create({
                        'name': 'Bibliothèque & Pénalités',
                        'sequence': 25,
                        'default_amount': fine_amount,
                    })
                Fee.create({
                    'student_id': loan.student_id.id,
                    'class_id': loan.student_id.current_class_id.id if loan.student_id.current_class_id else False,
                    'fee_type_id': fee_type.id,
                    'description': f"Amende de retard ({late}j) : {loan.book_id.name}",
                    'amount': fine_amount,
                    'due_date': today,
                })
        return True

    def action_renew(self):
        max_renewals = self._param('max_renewals')
        for loan in self:
            if loan.state not in ('ongoing', 'overdue'):
                raise UserError("Seul un emprunt en cours peut être prolongé.")
            if max_renewals and loan.renew_count >= max_renewals:
                raise UserError(f"Cet emprunt a déjà été prolongé {loan.renew_count} fois (maximum {max_renewals}).")
            start = max(loan.due_date, fields.Date.context_today(self))
            loan.write({
                'due_date': start + timedelta(days=loan.book_id.loan_duration_days or 14),
                'renew_count': loan.renew_count + 1,
            })
        return True

    def action_mark_lost(self):
        lost_loans = self.filtered(lambda l: not l.returned)
        lost_loans.write({'is_lost': True})
        # Facturation automatique des frais de remplacement pour les élèves
        Fee = self.env['eacta.student.fee']
        fee_type = self.env['eacta.fee.type'].search([('name', 'ilike', 'Biblioth')], limit=1)
        for loan in lost_loans.filtered(lambda l: l.borrower_type == 'student' and l.student_id):
            cost = loan.book_id.replacement_cost or 100.0
            if not fee_type:
                fee_type = self.env['eacta.fee.type'].create({
                    'name': 'Bibliothèque & Matériel',
                    'sequence': 20,
                    'default_amount': cost,
                })
            fee = Fee.create({
                'student_id': loan.student_id.id,
                'class_id': loan.student_id.current_class_id.id if loan.student_id.current_class_id else False,
                'fee_type_id': fee_type.id,
                'description': f"Livre perdu : {loan.book_id.name} ({loan.barcode_id.barcode})",
                'amount': cost,
                'due_date': fields.Date.context_today(self),
            })
            loan.message_post(body=f"Frais de remplacement de {cost:.2f} {loan.currency_id.symbol or ''} généré pour {loan.student_id.name} (Réf : {fee.name}).")
        return True

    def action_mark_fine_paid(self):
        self.write({'fine_paid': True})
        return True

    def action_reopen(self):
        self.write({'returned': False, 'is_lost': False, 'return_date': False, 'returned_barcode_id': False})
        return True

    def action_print_receipt(self):
        return self.env.ref('eacta_bibliotheque.action_report_loan_receipt').report_action(self)

    def action_view_details(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'res_model': 'library.loan', 'view_mode': 'form',
                'res_id': self.id, 'target': 'current'}

    # ------------------------------------------------------------------
    @api.model
    def _cron_check_overdue(self):
        """Met à jour les retards et envoie des rappels par email selon l'intervalle configuré."""
        today = fields.Date.context_today(self)
        active = self.search([('returned', '=', False), ('is_lost', '=', False)])
        self.env.add_to_compute(self._fields['state'], active)
        active.flush_recordset()

        send_reminder = self._param('send_overdue_reminder_email')
        min_interval_days = self._param('overdue_reminder_interval_days')
        template = self.env.ref('eacta_bibliotheque.email_template_library_loan_overdue', raise_if_not_found=False)
        todo = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)

        for loan in active.filtered(lambda l: l.state == 'overdue'):
            # 1. Planification d'activité pour le bibliothécaire
            if todo and not loan.activity_ids.filtered(lambda a: a.activity_type_id == todo):
                loan.activity_schedule(
                    'mail.mail_activity_data_todo',
                    summary="Relancer l'emprunteur (retard)",
                    note=f"« {loan.book_id.name} » devait être rendu le {loan.due_date.strftime('%d/%m/%Y')} "
                         f"par {loan.borrower_name}.",
                    user_id=loan.responsible_id.id or self.env.user.id,
                )

            # 2. Envoi email de relance avec intervalle minimum
            days_since_last = (today - loan.last_reminder_date).days if loan.last_reminder_date else 9999
            if send_reminder and days_since_last >= min_interval_days:
                recipient_email = False
                if loan.borrower_type == 'student' and loan.student_id:
                    recipient_email = (
                        (loan.student_id.parent_ids and loan.student_id.parent_ids[0].email)
                        or loan.student_id.email
                        or (loan.student_id.partner_id and loan.student_id.partner_id.email)
                    )
                elif loan.borrower_type == 'teacher' and loan.teacher_id:
                    recipient_email = loan.teacher_id.email

                if recipient_email and template:
                    try:
                        template.send_mail(loan.id, force_send=True)
                    except Exception as e:
                        loan.message_post(body=f"Échec de l'envoi du mail de relance : {str(e)}")
                    loan.last_reminder_date = today
                    loan.reminder_count += 1
                    loan.message_post(
                        body=f"Relance de retard #{loan.reminder_count} envoyée par email à {recipient_email} "
                             f"pour le livre « {loan.book_id.name} » ({loan.days_late}j de retard)."
                    )

    @api.model
    def _generate_demo_loans(self):
        """Emprunts de démonstration : en cours, en retard et rendus (déterministe)."""
        self = self.with_context(tracking_disable=True, mail_create_nolog=True, mail_notrack=True)
        students = self.env['eacta.student'].search([], limit=24, order='id')
        books = self.env['library.book'].search([], order='id')
        if not students or not books:
            return
        today = fields.Date.context_today(self)
        plans = [  # (jours depuis l'emprunt, rendu ?)
            (3, False), (9, False), (20, False), (26, False), (40, True), (35, True),
            (16, False), (1, False), (60, True), (28, False), (12, True), (5, False),
        ]
        for i, (age, returned) in enumerate(plans):
            book = books[i % len(books)]
            copy = book.barcode_ids.filtered(lambda c: c.state == 'available')[:1]
            student = students[(i * 5) % len(students)]
            if not copy:
                continue
            checkout = today - timedelta(days=age)
            loan = self.create({
                'borrower_type': 'student',
                'student_id': student.id,
                'book_id': book.id,
                'barcode_id': copy.id,
                'checkout_date': checkout,
                'due_date': checkout + timedelta(days=book.loan_duration_days),
            })
            if returned:
                late = 3 if i % 2 else 0
                loan.write({
                    'returned': True,
                    'return_date': checkout + timedelta(days=book.loan_duration_days + late),
                    'returned_barcode_id': copy.id,
                })

    @api.model
    def get_library_dashboard_data(self):
        Book = self.env['library.book']
        Copy = self.env['library.book.barcode']
        today = fields.Date.context_today(self)
        active = self.search([('state', 'in', ('ongoing', 'overdue'))])
        overdue = active.filtered(lambda l: l.state == 'overdue').sorted('due_date')
        month_start = today.replace(day=1)
        top_books = self._read_group([], ['book_id'], ['__count'], order='__count desc', limit=6)
        top_readers = self._read_group([('borrower_id', '!=', False)], ['borrower_id'], ['__count'],
                                       order='__count desc', limit=6)
        categories = self.env['library.book.category'].search([])
        return {
            'kpis': {
                'titles': Book.search_count([]),
                'copies': Copy.search_count([('state', '!=', 'lost')]),
                'available': Copy.search_count([('state', '=', 'available')]),
                'on_loan': len(active),
                'overdue': len(overdue),
                'month_loans': self.search_count([('checkout_date', '>=', month_start)]),
                'readers': self.env['library.borrower'].search_count([('active_loans_count', '>', 0)]),
                'fines_due': round(sum(self.search([('fine_paid', '=', False), ('fine_amount', '>', 0)])
                                       .mapped('fine_amount')), 2),
                'currency': self.env.company.currency_id.symbol or '',
            },
            'overdue': [{
                'id': l.id, 'book': l.book_id.name, 'borrower': l.borrower_name, 'class': l.class_id.name or '',
                'days': l.days_late, 'fine': l.fine_amount,
            } for l in overdue[:8]],
            'due_soon': [{
                'id': l.id, 'book': l.book_id.name, 'borrower': l.borrower_name,
                'date': fields.Date.to_string(l.due_date), 'days': (l.due_date - today).days,
            } for l in active.filtered(lambda l: l.state == 'ongoing').sorted('due_date')[:6]],
            'top_books': [{'id': b.id, 'name': b.name, 'author': b.author or '', 'count': c} for b, c in top_books],
            'top_readers': [{'id': r.id, 'name': r.name, 'type': dict(r._fields['borrower_type'].selection)
                             .get(r.borrower_type), 'count': c} for r, c in top_readers],
            'categories': [{'id': c.id, 'name': c.name, 'copies': c.copy_count, 'available': c.available_book_count}
                           for c in categories if c.copy_count],
        }
