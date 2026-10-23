import logging

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

PAYMENT_METHODS = [
    ('cash', 'Espèces'),
    ('check', 'Chèque'),
    ('transfer', 'Virement'),
    ('card', 'Carte bancaire'),
    ('other', 'Autre'),
]


def _get_school_currency(env):
    mad = env.ref('base.MAD', raise_if_not_found=False)
    if mad:
        if not mad.active:
            mad.sudo().active = True
        return mad
    return env.company.currency_id


class EactaFeeType(models.Model):
    _name = 'eacta.fee.type'
    _description = 'Type de frais'
    _order = 'sequence, name'

    name = fields.Char(string='Nom', required=True, translate=True)
    sequence = fields.Integer(default=10)
    default_amount = fields.Monetary(string='Montant par défaut', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', default=lambda self: _get_school_currency(self.env))
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
    academic_year_id = fields.Many2one('eacta.academic.year', string='Année académique', compute='_compute_class_id',
                                       store=True, readonly=False, index=True)
    year = fields.Char(string='Année', compute='_compute_class_id', store=True, readonly=False)

    @property
    def year_id(self):
        return self.academic_year_id

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None):
        def _remap(term):
            if isinstance(term, (list, tuple)) and len(term) == 3 and term[0] == 'year_id':
                return ('academic_year_id', term[1], term[2])
            return term
        remapped_domain = [_remap(term) for term in domain] if domain else domain
        return super()._search(remapped_domain, offset=offset, limit=limit, order=order)
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
    currency_id = fields.Many2one('res.currency', default=lambda self: _get_school_currency(self.env), required=True)
    date = fields.Date(string="Date d'émission", default=fields.Date.context_today, required=True)
    due_date = fields.Date(string="Échéance", required=True, default=fields.Date.context_today, tracking=True)
    payment_ids = fields.One2many('eacta.fee.payment', 'fee_id', string='Paiements & Remboursements')
    is_cancelled = fields.Boolean(string='Annulé', tracking=True, readonly=True)
    state = fields.Selection([
        ('unpaid', 'À payer'),
        ('partial', 'Partiellement payé'),
        ('paid', 'Payé'),
        ('cancelled', 'Annulé'),
    ], string='État', compute='_compute_amounts', store=True, tracking=True, index=True)
    is_overdue = fields.Boolean(string='En retard', compute='_compute_is_overdue', search='_search_is_overdue')
    late_fee_applied = fields.Boolean(string='Pénalité de retard appliquée', default=False)
    late_fee_amount = fields.Monetary(string='Montant pénalité', currency_field='currency_id', default=0.0)
    reminder_count = fields.Integer(string='Nombre de relances', default=0, readonly=True)
    last_reminder_date = fields.Date(string='Dernière relance', readonly=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)

    # Intégration comptable
    move_id = fields.Many2one('account.move', string='Facture client', readonly=True, copy=False)
    move_state = fields.Selection(related='move_id.state', string='État facture', readonly=True)
    payment_state = fields.Selection(related='move_id.payment_state', string='Paiement comptable', readonly=True)

    @api.depends('student_id', 'class_id')
    def _compute_class_id(self):
        for fee in self:
            if not fee.class_id:
                fee.class_id = fee.student_id.current_class_id
            if not fee.academic_year_id:
                fee.academic_year_id = (fee.class_id.academic_year_id if fee.class_id else False) or self.env['eacta.academic.year'].get_current_year()
            if not fee.year:
                fee.year = fee.academic_year_id.name or (fee.class_id.year if fee.class_id else '')

    @api.depends('student_id')
    def _compute_parent_id(self):
        for fee in self:
            if not fee.parent_id:
                fee.parent_id = fee.student_id.parent_ids[:1]

    @api.depends('amount', 'discount', 'payment_ids.amount', 'payment_ids.payment_type', 'is_cancelled')
    def _compute_amounts(self):
        for fee in self:
            total = max(fee.amount - fee.discount, 0.0)
            payments = sum(fee.payment_ids.filtered(lambda p: p.payment_type == 'payment').mapped('amount'))
            refunds = sum(fee.payment_ids.filtered(lambda p: p.payment_type == 'refund').mapped('amount'))
            paid = max(payments - refunds, 0.0)

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
        self._apply_sibling_discount()

    @api.onchange('student_id')
    def _onchange_student_id(self):
        self._apply_sibling_discount()

    def _apply_sibling_discount(self):
        ICP = self.env['ir.config_parameter'].sudo()
        enable_discount = ICP.get_param('eacta_school.enable_sibling_discount', 'False') in ('True', '1', True)
        if enable_discount and self.student_id and self.student_id.parent_ids and self.amount:
            if not self.student_id._is_eldest_sibling():
                rate = float(ICP.get_param('eacta_school.sibling_discount_rate', 10.0))
                self.discount = round(self.amount * (rate / 100.0), 2)

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
            if 'year_id' in vals and 'academic_year_id' not in vals:
                vals['academic_year_id'] = vals.pop('year_id')
            if not vals.get('name') or vals['name'] == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code('eacta.student.fee') or '/'
        records = super().create(vals_list)
        for rec in records:
            rec._sync_account_invoice()
        return records

    def write(self, vals):
        if 'year_id' in vals and 'academic_year_id' not in vals:
            vals['academic_year_id'] = vals.pop('year_id')
        return super().write(vals)

    @api.depends('name', 'fee_type_id', 'description')
    def _compute_display_name(self):
        for fee in self:
            label = fee.description or fee.fee_type_id.name or ''
            fee.display_name = f"{fee.name} · {label}" if label else fee.name

    def unlink(self):
        if any(f.payment_ids for f in self):
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
            'context': {
                'default_fee_id': self.id,
                'default_amount': self.amount_due,
                'default_payment_type': 'payment',
            },
        }

    def action_cancel(self):
        for fee in self:
            if fee.amount_paid > 0:
                raise UserError(
                    f"Des paiements ({fee.amount_paid:.2f} {fee.currency_id.symbol}) sont enregistrés sur « {fee.display_name} » : "
                    f"veuillez d'abord enregistrer un remboursement avant d'annuler ces frais."
                )
        self.write({'is_cancelled': True})

    def action_reset(self):
        self.write({'is_cancelled': False})

    def action_view_invoice(self):
        self.ensure_one()
        if not self.move_id:
            raise UserError("Aucune facture client associée à ces frais.")
        return {
            'name': 'Facture client',
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': self.move_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_create_invoice(self):
        Journal = self.env['account.journal']
        for fee in self:
            if not fee.move_id and not fee.is_cancelled:
                sale_journal = Journal.search([
                    ('type', '=', 'sale'),
                    ('company_id', '=', fee.company_id.id),
                ], limit=1)
                if not sale_journal:
                    raise UserError(
                        f"Aucun journal des ventes n'est configuré pour l'établissement « {fee.company_id.name} ». "
                        f"Veuillez configurer un plan comptable (ex. module l10n_ma pour le Maroc) ou créer un journal des ventes avant de générer des factures."
                    )
                partner = fee.parent_id or (fee.student_id.parent_ids[:1] if fee.student_id else False) or (fee.student_id.partner_id if fee.student_id else False)
                if not partner:
                    raise UserError(
                        f"Impossible de créer la facture pour le frais « {fee.name} » : aucun parent ou contact n'est associé à l'élève {fee.student_id.name}."
                    )
                fee._sync_account_invoice()
        return True

    def _sync_account_invoice(self):
        """Intégration automatique avec account.move."""
        if 'account.move' not in self.env:
            return
        Journal = self.env['account.journal']
        for fee in self:
            if fee.move_id or not fee.amount_total or fee.is_cancelled:
                continue
            partner = fee.parent_id or (fee.student_id.parent_ids[:1] if fee.student_id else False)
            if not partner and fee.student_id and fee.student_id.partner_id:
                partner = fee.student_id.partner_id
            if not partner:
                continue

            journal = Journal.search([
                ('type', '=', 'sale'),
                ('company_id', '=', fee.company_id.id),
            ], limit=1)
            if not journal:
                continue

            currency = fee.currency_id or _get_school_currency(self.env)
            line_name = f"{fee.description or fee.fee_type_id.name or 'Frais scolaires'} - {fee.student_id.name or ''}"
            if fee.student_code:
                line_name += f" ({fee.student_code})"

            move_vals = {
                'move_type': 'out_invoice',
                'partner_id': partner.id,
                'journal_id': journal.id,
                'currency_id': currency.id,
                'invoice_date': fee.date or fields.Date.context_today(self),
                'invoice_date_due': fee.due_date or fee.date or fields.Date.context_today(self),
                'ref': fee.name,
                'invoice_line_ids': [(0, 0, {
                    'name': line_name,
                    'quantity': 1.0,
                    'price_unit': fee.amount_total,
                })],
            }
            try:
                move = self.env['account.move'].create(move_vals)
                fee.move_id = move.id
                fee.message_post(body=f"Facture client {move.name or ''} générée avec succès.")
            except Exception as e:
                # Log non-fatal error in chatter
                fee.message_post(body=f"Création de la facture client différée : {str(e)}")

    def _add_late_fee_to_invoice(self, penalty):
        """Répercute la pénalité sur la facture client pour garder frais et comptabilité alignés."""
        self.ensure_one()
        if not self.move_id:
            return
        if self.move_id.state == 'draft':
            self.move_id.write({'invoice_line_ids': [(0, 0, {
                'name': f"Pénalité de retard - {self.name}",
                'quantity': 1.0,
                'price_unit': penalty,
            })]})
        else:
            self.message_post(
                body=f"La facture {self.move_id.name} est déjà validée : la pénalité de {penalty:.2f} "
                     f"{self.currency_id.symbol or ''} doit être facturée séparément (note de débit)."
            )

    @api.model
    def _cron_check_overdue_fees(self):
        """Action planifiée : identifie les frais en retard, applique les pénalités et notifie les parents."""
        today = fields.Date.context_today(self)
        ICP = self.env['ir.config_parameter'].sudo()
        enable_late_fee = ICP.get_param('eacta_school.enable_late_fee', 'False') in ('True', '1', True)
        late_fee_type = ICP.get_param('eacta_school.late_fee_type', 'fixed')
        late_fee_val = float(ICP.get_param('eacta_school.late_fee_amount', 50.0))
        send_reminder = ICP.get_param('eacta_school.send_fee_reminder_email', 'True') in ('True', '1', True)
        min_interval_days = int(ICP.get_param('eacta_school.fee_reminder_interval_days', 7))

        overdue_fees = self.search([
            ('state', 'in', ('unpaid', 'partial')),
            ('due_date', '<', today),
            ('is_cancelled', '=', False),
        ])

        template = self.env.ref('eacta_school.email_template_fee_reminder', raise_if_not_found=False)

        for fee in overdue_fees:
            # 1. Pénalité de retard si activée (opt-in) et non encore appliquée
            if enable_late_fee and not fee.late_fee_applied and late_fee_val > 0:
                if late_fee_type == 'fixed':
                    penalty = late_fee_val
                else:
                    penalty = round(fee.amount_due * (late_fee_val / 100.0), 2)

                fee.amount += penalty
                fee.late_fee_applied = True
                fee.late_fee_amount = penalty
                fee.message_post(
                    body=f"Pénalité de retard appliquée : +{penalty:.2f} {fee.currency_id.symbol or ''} (Échéance dépassée le {fee.due_date})."
                )
                fee._add_late_fee_to_invoice(penalty)

            # 2. Relance email au parent si configurée (avec intervalle minimum pour éviter les doublons)
            parent = fee.parent_id or (fee.student_id.parent_ids[:1] if fee.student_id else False)
            parent_email = parent.email if parent else False
            days_since_last = (today - fee.last_reminder_date).days if fee.last_reminder_date else 9999

            if send_reminder and parent_email and days_since_last >= min_interval_days and template:
                try:
                    template.send_mail(fee.id, force_send=True)
                except Exception as e:
                    # Pas de compteur ni de date : la relance sera retentée au prochain passage
                    fee.message_post(body=f"Échec de l'envoi du mail de relance : {str(e)}")
                    continue
                fee.last_reminder_date = today
                fee.reminder_count += 1
                fee.message_post(
                    body=f"Relance d'impayé #{fee.reminder_count} envoyée au parent {parent.name} ({parent_email}) pour un reste dû de {fee.amount_due:.2f} {fee.currency_id.symbol or 'DH'}."
                )


class EactaFeePayment(models.Model):
    _name = 'eacta.fee.payment'
    _description = 'Paiement / Remboursement de frais'
    _inherit = ['mail.thread']
    _order = 'date desc, id desc'

    name = fields.Char(string='N° de reçu', readonly=True, copy=False, default='/', index=True)
    payment_type = fields.Selection([
        ('payment', 'Paiement'),
        ('refund', 'Remboursement'),
    ], string='Type', default='payment', required=True, tracking=True)
    refund_payment_id = fields.Many2one(
        'eacta.fee.payment', string="Paiement d'origine",
        domain="[('fee_id', '=', fee_id), ('payment_type', '=', 'payment')]"
    )
    fee_id = fields.Many2one('eacta.student.fee', string='Frais', required=True, ondelete='cascade', index=True)
    student_id = fields.Many2one(related='fee_id.student_id', store=True, string='Élève')
    class_id = fields.Many2one(related='fee_id.class_id', store=True, string='Classe')
    fee_type_id = fields.Many2one(related='fee_id.fee_type_id', store=True, string='Type de frais')
    date = fields.Date(string='Date', required=True, default=fields.Date.context_today, tracking=True)
    amount = fields.Monetary(string='Montant', required=True, currency_field='currency_id', tracking=True)
    currency_id = fields.Many2one(related='fee_id.currency_id')
    method = fields.Selection(PAYMENT_METHODS, string='Moyen de paiement', default='cash', required=True)
    reference = fields.Char(string='Référence (chèque, virement…)')
    received_by = fields.Many2one('res.users', string='Encaissé / Traité par', default=lambda self: self.env.user,
                                  readonly=True)
    note = fields.Char(string='Remarque')

    @api.constrains('amount', 'fee_id', 'payment_type', 'refund_payment_id')
    def _check_amount(self):
        for payment in self:
            if payment.amount <= 0:
                raise ValidationError("Le montant du paiement ou du remboursement doit être strictement positif.")
            fee = payment.fee_id
            if payment.payment_type == 'payment':
                all_payments = sum(fee.payment_ids.filtered(lambda p: p.payment_type == 'payment').mapped('amount'))
                all_refunds = sum(fee.payment_ids.filtered(lambda p: p.payment_type == 'refund').mapped('amount'))
                if (all_payments - all_refunds) - fee.amount_total > 0.001:
                    raise ValidationError(
                        f"Le total des paiements dépasse le montant dû pour {fee.display_name} "
                        f"({fee.amount_total:.2f} {fee.currency_id.symbol or ''})."
                    )
            elif payment.payment_type == 'refund':
                if payment.refund_payment_id and payment.amount > payment.refund_payment_id.amount:
                    raise ValidationError(
                        f"Le montant du remboursement ({payment.amount:.2f}) ne peut pas dépasser "
                        f"le paiement d'origine ({payment.refund_payment_id.amount:.2f})."
                    )
                all_payments = sum(fee.payment_ids.filtered(lambda p: p.payment_type == 'payment').mapped('amount'))
                all_refunds = sum(fee.payment_ids.filtered(lambda p: p.payment_type == 'refund').mapped('amount'))
                if all_refunds > all_payments:
                    raise ValidationError("Le montant total remboursé ne peut pas dépasser le total déjà encaissé.")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == '/':
                prefix = 'eacta.fee.refund' if vals.get('payment_type') == 'refund' else 'eacta.fee.payment'
                vals['name'] = self.env['ir.sequence'].next_by_code(prefix) or '/'
        payments = super().create(vals_list)
        for payment in payments:
            if payment.payment_type == 'refund':
                msg = f"Remboursement {payment.name} de {payment.amount:.2f} {payment.currency_id.symbol or ''} enregistré."
            else:
                msg = f"Paiement {payment.name} de {payment.amount:.2f} {payment.currency_id.symbol or ''} enregistré."
            payment.fee_id.message_post(body=msg)
            payment._sync_account_payment()
        return payments

    def write(self, vals):
        # Règle d'immutabilité des paiements après création
        if 'amount' in vals:
            raise UserError(
                "Le montant d'un paiement ou d'un remboursement ne peut jamais être modifié après sa création. "
                "Veuillez enregistrer une opération de contre-passation (remboursement) si nécessaire."
            )
        if any(k in vals for k in ('fee_id', 'student_id', 'payment_type')):
            if not self.env.user.has_group('eacta_school.group_eacta_school_manager'):
                raise UserError("Seul un administrateur peut modifier les informations d'un paiement existant.")
        return super().write(vals)

    def action_create_refund(self):
        """Ouvre un formulaire pré-rempli pour rembourser ce paiement."""
        self.ensure_one()
        if self.payment_type != 'payment':
            raise UserError("Impossible de rembourser un remboursement.")
        return {
            'name': f"Rembourser - {self.name}",
            'type': 'ir.actions.act_window',
            'res_model': 'eacta.fee.payment',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_fee_id': self.fee_id.id,
                'default_payment_type': 'refund',
                'default_refund_payment_id': self.id,
                'default_amount': self.amount,
                'default_method': self.method,
            },
        }

    def _sync_account_payment(self):
        """Enregistre le paiement dans le module account si présent."""
        if 'account.payment' not in self.env:
            return
        for payment in self:
            fee = payment.fee_id
            if not fee.move_id:
                continue
            partner = fee.parent_id or (fee.student_id.parent_ids[:1] if fee.student_id else False)
            if not partner and fee.student_id and fee.student_id.partner_id:
                partner = fee.student_id.partner_id
            if not partner:
                continue
            try:
                if fee.move_id.state == 'draft':
                    try:
                        fee.move_id.action_post()
                    except Exception:
                        _logger.warning("Validation de la facture %s impossible", fee.move_id.display_name, exc_info=True)
                journal = self.env['account.journal'].search([
                    ('type', 'in', ('bank', 'cash')),
                    ('company_id', '=', fee.company_id.id),
                ], limit=1)
                if not journal:
                    continue
                pay_type = 'outbound' if payment.payment_type == 'refund' else 'inbound'
                currency = payment.currency_id or fee.currency_id or _get_school_currency(self.env)
                self.env['account.payment'].create({
                    'payment_type': pay_type,
                    'partner_type': 'customer',
                    'partner_id': partner.id,
                    'amount': payment.amount,
                    'date': payment.date,
                    'currency_id': currency.id,
                    'journal_id': journal.id,
                    'ref': f"{payment.name} - {fee.name}",
                })
            except Exception:
                _logger.warning("Synchronisation comptable du paiement %s impossible", payment.name, exc_info=True)

    def action_print_receipt(self):
        return self.env.ref('eacta_school.action_report_fee_receipt').report_action(self)

    def action_save_and_print(self):
        return self.action_print_receipt()


class EactaFeeGenerateWizard(models.TransientModel):
    _name = 'eacta.fee.generate.wizard'
    _description = 'Génération des frais de scolarité'

    fee_type_id = fields.Many2one('eacta.fee.type', string='Type de frais', required=True)
    academic_year_id = fields.Many2one('eacta.academic.year', string='Année académique',
                                       default=lambda self: self.env['eacta.academic.year'].get_current_year(),
                                       required=True)
    class_ids = fields.Many2many('eacta.class', string='Classes')
    description = fields.Char(string='Libellé', help="ex : Scolarité 2026-2027")
    amount = fields.Monetary(string='Montant par élève', required=True, currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', default=lambda self: _get_school_currency(self.env))
    installments = fields.Integer(string="Nombre d'échéances", default=1,
                                  help="Divise le montant en échéances mensuelles")
    first_due_date = fields.Date(string='Première échéance', required=True, default=fields.Date.context_today)
    skip_existing = fields.Boolean(string='Ignorer les élèves déjà facturés pour ce type et cette année',
                                   default=True)
    apply_sibling_discount = fields.Boolean(string='Appliquer la remise fratrie configurée', default=True)
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
        if not self.class_ids and not self.student_ids:
            raise UserError("Veuillez sélectionner au moins une classe ou un élève.")
        Fee = self.env['eacta.student.fee']
        per = round(self.amount / self.installments, 2)
        vals_list = []

        ICP = self.env['ir.config_parameter'].sudo()
        sibling_rate = float(ICP.get_param('eacta_school.sibling_discount_rate', 10.0))

        if self.student_ids:
            students = self.student_ids
        else:
            students = self.class_ids.student_ids.filtered(lambda s: s.state in ('draft', 'enrolled'))

        if not students:
            raise UserError("Aucun élève trouvé pour la génération des frais.")

        for student in students:
            klass = student.current_class_id or (self.class_ids[:1] if self.class_ids else False)
            year_id = (klass.academic_year_id.id if klass and klass.academic_year_id else False) or self.academic_year_id.id
            if self.skip_existing and Fee.search_count([
                    ('student_id', '=', student.id),
                    ('fee_type_id', '=', self.fee_type_id.id),
                    ('academic_year_id', '=', year_id),
                    ('is_cancelled', '=', False)]):
                continue

            total_discount = 0.0
            discount_per_installment = 0.0
            if self.apply_sibling_discount and student.parent_ids:
                if not student._is_eldest_sibling():
                    total_discount = round(self.amount * (sibling_rate / 100.0), 2)
                    discount_per_installment = round(total_discount / self.installments, 2)

            for i in range(self.installments):
                amount = per if i < self.installments - 1 else round(self.amount - per * (self.installments - 1), 2)
                disc = discount_per_installment if i < self.installments - 1 else round(total_discount - discount_per_installment * (self.installments - 1), 2)
                label = self.description or self.fee_type_id.name
                if self.installments > 1:
                    label = f"{label} ({i + 1}/{self.installments})"
                vals_list.append({
                    'student_id': student.id,
                    'class_id': klass.id if klass else False,
                    'academic_year_id': year_id,
                    'year': (klass.academic_year_id.name if klass and klass.academic_year_id else False) or self.academic_year_id.name or '',
                    'fee_type_id': self.fee_type_id.id,
                    'description': label,
                    'amount': amount,
                    'discount': min(disc, amount),
                    'currency_id': self.currency_id.id,
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
    fee_count = fields.Integer(string='Nombre de frais', compute='_compute_fee_balance')

    @api.depends('fee_ids.amount_due', 'fee_ids.state', 'fee_ids.due_date')
    def _compute_fee_balance(self):
        today = fields.Date.context_today(self)
        for student in self:
            open_fees = student.fee_ids.filtered(lambda f: f.state in ('unpaid', 'partial'))
            student.fee_balance = sum(open_fees.mapped('amount_due'))
            student.fee_overdue = sum(open_fees.filtered(lambda f: f.due_date and f.due_date < today).mapped('amount_due'))
            student.fee_currency_id = student.fee_ids[:1].currency_id or _get_school_currency(self.env)
            student.fee_count = len(student.fee_ids)

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
