from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

PAYMENT_METHODS = [
    ('cash', 'Espèces'),
    ('check', 'Chèque'),
    ('transfer', 'Virement'),
    ('card', 'Carte bancaire'),
    ('other', 'Autre'),
]


class EactaFeeType(models.Model):
    _name = 'eacta.fee.type'
    _description = 'Type de frais'
    _order = 'sequence, name'

    name = fields.Char(string='Nom', required=True, translate=True)
    sequence = fields.Integer(default=10)
    default_amount = fields.Monetary(string='Montant par défaut', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    description = fields.Text(string='Description')
    active = fields.Boolean(default=True)


class EactaStudentFee(models.Model):
    _name = 'eacta.student.fee'
    _description = 'Frais de scolarité'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'due_date desc, id desc'

    name = fields.Char(string='Référence', readonly=True, copy=False, default='/', index=True)
    student_id = fields.Many2one('eacta.student', string='Élève', required=True, ondelete='cascade', index=True,
                                 tracking=True)
    student_code = fields.Char(related='student_id.code', string='Matricule')
    class_id = fields.Many2one('eacta.class', string='Classe', compute='_compute_class_id', store=True,
                               readonly=False)
    year = fields.Char(string='Année', compute='_compute_class_id', store=True, readonly=False)
    parent_id = fields.Many2one('res.partner', string='Payeur', compute='_compute_parent_id', store=True,
                                readonly=False)
    fee_type_id = fields.Many2one('eacta.fee.type', string='Type de frais', required=True, tracking=True)
    description = fields.Char(string='Libellé')
    amount = fields.Monetary(string='Montant', required=True, tracking=True, currency_field='currency_id')
    discount = fields.Monetary(string='Remise', currency_field='currency_id', tracking=True)
    amount_total = fields.Monetary(string='Total', compute='_compute_amounts', store=True,
                                   currency_field='currency_id')
    amount_paid = fields.Monetary(string='Payé', compute='_compute_amounts', store=True, currency_field='currency_id')
    amount_due = fields.Monetary(string='Reste à payer', compute='_compute_amounts', store=True,
                                 currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id, required=True)
    date = fields.Date(string="Date d'émission", default=fields.Date.context_today, required=True)
    due_date = fields.Date(string="Échéance", required=True, default=fields.Date.context_today, tracking=True)
    payment_ids = fields.One2many('eacta.fee.payment', 'fee_id', string='Paiements')
    is_cancelled = fields.Boolean(string='Annulé', tracking=True)
    state = fields.Selection([
        ('unpaid', 'À payer'),
        ('partial', 'Partiellement payé'),
        ('paid', 'Payé'),
        ('cancelled', 'Annulé'),
    ], string='État', compute='_compute_amounts', store=True, tracking=True, index=True)
    is_overdue = fields.Boolean(string='En retard', compute='_compute_is_overdue', search='_search_is_overdue')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)

    @api.depends('student_id')
    def _compute_class_id(self):
        for fee in self:
            if not fee.class_id:
                fee.class_id = fee.student_id.current_class_id
            if not fee.year:
                fee.year = fee.class_id.year or str(fields.Date.today().year)

    @api.depends('student_id')
    def _compute_parent_id(self):
        for fee in self:
            if not fee.parent_id:
                fee.parent_id = fee.student_id.parent_ids[:1]

    @api.depends('amount', 'discount', 'payment_ids.amount', 'is_cancelled')
    def _compute_amounts(self):
        for fee in self:
            total = max(fee.amount - fee.discount, 0.0)
            paid = sum(fee.payment_ids.mapped('amount'))
            fee.amount_total = total
            fee.amount_paid = paid
            fee.amount_due = max(total - paid, 0.0)
            if fee.is_cancelled:
                fee.state = 'cancelled'
            elif total and paid >= total:
                fee.state = 'paid'
            elif paid:
                fee.state = 'partial'
            else:
                fee.state = 'unpaid' if total else 'paid'

    def _compute_is_overdue(self):
        today = fields.Date.context_today(self)
        for fee in self:
            fee.is_overdue = fee.state in ('unpaid', 'partial') and fee.due_date and fee.due_date < today

    def _search_is_overdue(self, operator, value):
        today = fields.Date.context_today(self)
        positive = (operator == '=' and value) or (operator == '!=' and not value)
        if positive:
            return [('state', 'in', ('unpaid', 'partial')), ('due_date', '<', today)]
        return ['|', ('state', 'not in', ('unpaid', 'partial')), ('due_date', '>=', today)]

    @api.onchange('fee_type_id')
    def _onchange_fee_type_id(self):
        if self.fee_type_id and not self.amount:
            self.amount = self.fee_type_id.default_amount

    @api.constrains('amount', 'discount')
    def _check_amounts(self):
        for fee in self:
            if fee.amount < 0 or fee.discount < 0:
                raise ValidationError("Les montants doivent être positifs.")
            if fee.discount > fee.amount:
                raise ValidationError("La remise ne peut pas dépasser le montant.")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code('eacta.student.fee') or '/'
        return super().create(vals_list)

    @api.depends('name', 'fee_type_id', 'description')
    def _compute_display_name(self):
        for fee in self:
            label = fee.description or fee.fee_type_id.name or ''
            fee.display_name = f"{fee.name} · {label}" if label else fee.name

    def unlink(self):
        if self.payment_ids:
            raise UserError("Impossible de supprimer des frais ayant des paiements : annulez-les plutôt.")
        return super().unlink()

    def action_register_payment(self):
        self.ensure_one()
        if self.state in ('paid', 'cancelled'):
            raise UserError("Ces frais sont déjà réglés ou annulés.")
        return {
            'name': f"Paiement - {self.display_name}",
            'type': 'ir.actions.act_window',
            'res_model': 'eacta.fee.payment',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_fee_id': self.id, 'default_amount': self.amount_due},
        }

    def action_cancel(self):
        if self.payment_ids:
            raise UserError("Des paiements sont enregistrés : remboursez-les avant d'annuler.")
        self.write({'is_cancelled': True})

    def action_reset(self):
        self.write({'is_cancelled': False})


class EactaFeePayment(models.Model):
    _name = 'eacta.fee.payment'
    _description = 'Paiement de frais'
    _inherit = ['mail.thread']
    _order = 'date desc, id desc'

    name = fields.Char(string='N° de reçu', readonly=True, copy=False, default='/', index=True)
    fee_id = fields.Many2one('eacta.student.fee', string='Frais', required=True, ondelete='cascade', index=True,
                             domain="[('state', 'in', ('unpaid', 'partial'))]")
    student_id = fields.Many2one(related='fee_id.student_id', store=True, string='Élève')
    class_id = fields.Many2one(related='fee_id.class_id', store=True, string='Classe')
    fee_type_id = fields.Many2one(related='fee_id.fee_type_id', store=True, string='Type de frais')
    date = fields.Date(string='Date', required=True, default=fields.Date.context_today, tracking=True)
    amount = fields.Monetary(string='Montant', required=True, currency_field='currency_id', tracking=True)
    currency_id = fields.Many2one(related='fee_id.currency_id')
    method = fields.Selection(PAYMENT_METHODS, string='Moyen de paiement', default='cash', required=True)
    reference = fields.Char(string='Référence (chèque, virement…)')
    received_by = fields.Many2one('res.users', string='Encaissé par', default=lambda self: self.env.user,
                                  readonly=True)
    note = fields.Char(string='Remarque')

    @api.constrains('amount', 'fee_id')
    def _check_amount(self):
        for payment in self:
            if payment.amount <= 0:
                raise ValidationError("Le montant du paiement doit être positif.")
            fee = payment.fee_id
            if sum(fee.payment_ids.mapped('amount')) - fee.amount_total > 0.001:
                raise ValidationError(
                    f"Le total des paiements dépasse le montant dû pour {fee.display_name} "
                    f"({fee.amount_total:.2f} {fee.currency_id.symbol or ''}).")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code('eacta.fee.payment') or '/'
        payments = super().create(vals_list)
        for payment in payments:
            payment.fee_id.message_post(
                body=f"Paiement {payment.name} de {payment.amount:.2f} {payment.currency_id.symbol or ''} enregistré.")
        return payments

    def action_print_receipt(self):
        return self.env.ref('eacta_school.action_report_fee_receipt').report_action(self)

    def action_save_and_print(self):
        return self.action_print_receipt()


class EactaFeeGenerateWizard(models.TransientModel):
    _name = 'eacta.fee.generate.wizard'
    _description = 'Génération des frais de scolarité'

    fee_type_id = fields.Many2one('eacta.fee.type', string='Type de frais', required=True)
    class_ids = fields.Many2many('eacta.class', string='Classes', required=True)
    description = fields.Char(string='Libellé', help="ex : Scolarité 2026-2027")
    amount = fields.Monetary(string='Montant par élève', required=True, currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    installments = fields.Integer(string="Nombre d'échéances", default=1,
                                  help="Divise le montant en échéances mensuelles")
    first_due_date = fields.Date(string='Première échéance', required=True, default=fields.Date.context_today)
    skip_existing = fields.Boolean(string='Ignorer les élèves déjà facturés pour ce type et cette année',
                                   default=True)
    student_count = fields.Integer(string='Élèves concernés', compute='_compute_student_count')
    student_ids = fields.Many2many('eacta.student', string='Élèves spécifiques (optionnel)',
                                  help="Laisser vide pour facturer toute la classe")

    @api.depends('class_ids', 'student_ids')
    def _compute_student_count(self):
        for wizard in self:
            if wizard.student_ids:
                wizard.student_count = len(wizard.student_ids)
            else:
                wizard.student_count = len(wizard.class_ids.student_ids.filtered(lambda s: s.state in ('draft', 'enrolled')))

    @api.onchange('fee_type_id')
    def _onchange_fee_type_id(self):
        if self.fee_type_id:
            self.amount = self.fee_type_id.default_amount
            if not self.description:
                self.description = self.fee_type_id.name

    def action_generate(self):
        self.ensure_one()
        if self.installments < 1:
            raise UserError("Le nombre d'échéances doit être au moins 1.")
        Fee = self.env['eacta.student.fee']
        per = round(self.amount / self.installments, 2)
        vals_list = []
        for klass in self.class_ids:
            students = self.student_ids if self.student_ids else klass.student_ids.filtered(lambda s: s.state in ('draft', 'enrolled'))
            for student in students:
                if self.skip_existing and Fee.search_count([
                        ('student_id', '=', student.id), ('fee_type_id', '=', self.fee_type_id.id),
                        ('year', '=', klass.year), ('is_cancelled', '=', False)]):
                    continue
                for i in range(self.installments):
                    amount = per if i < self.installments - 1 else round(self.amount - per * (self.installments - 1), 2)
                    label = self.description or self.fee_type_id.name
                    if self.installments > 1:
                        label = f"{label} ({i + 1}/{self.installments})"
                    vals_list.append({
                        'student_id': student.id,
                        'class_id': klass.id,
                        'year': klass.year,
                        'fee_type_id': self.fee_type_id.id,
                        'description': label,
                        'amount': amount,
                        'due_date': self.first_due_date + relativedelta(months=i),
                    })
        fees = Fee.create(vals_list)
        return {
            'name': 'Frais générés',
            'type': 'ir.actions.act_window',
            'res_model': 'eacta.student.fee',
            'view_mode': 'list,form',
            'domain': [('id', 'in', fees.ids)],
        }


class EactaStudentFinance(models.Model):
    _inherit = 'eacta.student'

    fee_ids = fields.One2many('eacta.student.fee', 'student_id', string='Frais de scolarité')
    fee_balance = fields.Monetary(string='Solde dû', compute='_compute_fee_balance', currency_field='fee_currency_id')
    fee_overdue = fields.Monetary(string='Dont en retard', compute='_compute_fee_balance',
                                  currency_field='fee_currency_id')
    fee_currency_id = fields.Many2one('res.currency', compute='_compute_fee_balance')

    @api.depends('fee_ids.amount_due', 'fee_ids.state', 'fee_ids.due_date')
    def _compute_fee_balance(self):
        today = fields.Date.context_today(self)
        currency = self.env.company.currency_id
        for student in self:
            open_fees = student.fee_ids.filtered(lambda f: f.state in ('unpaid', 'partial'))
            student.fee_balance = sum(open_fees.mapped('amount_due'))
            student.fee_overdue = sum(open_fees.filtered(lambda f: f.due_date and f.due_date < today)
                                      .mapped('amount_due'))
            student.fee_currency_id = currency

    def action_view_fees(self):
        self.ensure_one()
        return {
            'name': f"Frais - {self.name}",
            'type': 'ir.actions.act_window',
            'res_model': 'eacta.student.fee',
            'view_mode': 'list,form',
            'domain': [('student_id', '=', self.id)],
            'context': {'default_student_id': self.id},
        }

    def action_print_statement(self):
        return self.env.ref('eacta_school.action_report_fee_statement').report_action(self)


class EactaClassExtras(models.Model):
    _inherit = 'eacta.class'

    timetable_slot_ids = fields.One2many('eacta.timetable.slot', 'class_id', string='Emploi du temps')
    weekly_hours = fields.Float(string='Heures / semaine', compute='_compute_weekly_hours')

    @api.depends('timetable_slot_ids.duration')
    def _compute_weekly_hours(self):
        for klass in self:
            klass.weekly_hours = sum(klass.timetable_slot_ids.mapped('duration'))

    def action_open_timetable(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'eacta_school.timetable',
            'name': f"Emploi du temps - {self.display_name}",
            'params': {'mode': 'class', 'record_id': self.id},
        }

    def action_open_promotion(self):
        self.ensure_one()
        return {
            'name': "Passage de fin d'année",
            'type': 'ir.actions.act_window',
            'res_model': 'eacta.promotion.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_from_class_id': self.id},
        }

    def action_print_timetable(self):
        return self.env.ref('eacta_school.action_report_class_timetable').report_action(self)
