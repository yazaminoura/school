from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from .eacta_fee import _get_school_currency

JOB_TYPES = [
    ('teacher', 'Enseignant'),
    ('direction', 'Direction'),
    ('admin', 'Administration / Secrétariat'),
    ('supervisor', 'Surveillant'),
    ('nurse', 'Infirmier(ère)'),
    ('driver', 'Chauffeur'),
    ('canteen', 'Cantine'),
    ('maintenance', 'Entretien / Maintenance'),
    ('other', 'Autre'),
]

# Semaines moyennes par mois, pour estimer les heures d'un vacataire depuis l'emploi du temps
WEEKS_PER_MONTH = 4.33


class EactaStaffContract(models.Model):
    _name = 'eacta.staff.contract'
    _description = 'Contrat du personnel'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'state, name'

    name = fields.Char(string='Nom et prénom', required=True, tracking=True)
    user_id = fields.Many2one('res.users', string='Compte utilisateur', tracking=True,
                              help="Lier le compte d'un enseignant permet de calculer ses heures depuis l'emploi du temps.")
    job = fields.Selection(JOB_TYPES, string='Fonction', required=True, default='teacher', tracking=True)
    contract_type = fields.Selection([
        ('cdi', 'CDI'),
        ('cdd', 'CDD'),
        ('vacataire', 'Vacataire (à l\'heure)'),
    ], string='Type de contrat', required=True, default='cdi', tracking=True)
    date_start = fields.Date(string="Date d'embauche", required=True, default=fields.Date.context_today,
                             tracking=True)
    date_end = fields.Date(string='Fin de contrat', tracking=True)
    monthly_wage = fields.Monetary(string='Salaire brut mensuel', currency_field='currency_id', tracking=True)
    hourly_rate = fields.Monetary(string='Taux horaire', currency_field='currency_id', tracking=True)
    currency_id = fields.Many2one('res.currency', default=lambda self: _get_school_currency(self.env))
    weekly_hours = fields.Float(string='Heures / semaine (emploi du temps)', compute='_compute_weekly_hours')
    cin = fields.Char(string='CIN')
    cnss_number = fields.Char(string='N° CNSS')
    bank_account = fields.Char(string='RIB')
    phone = fields.Char(string='Téléphone')
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('running', 'En cours'),
        ('ended', 'Terminé'),
    ], string='État', default='draft', required=True, tracking=True, index=True)
    payslip_ids = fields.One2many('eacta.payslip', 'contract_id', string='Bulletins de paie')
    payslip_count = fields.Integer(compute='_compute_payslip_count', string='Bulletins')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)

    @api.depends('user_id')
    def _compute_weekly_hours(self):
        # Lecture en sudo : le service paie n'a pas accès à l'emploi du temps
        Slot = self.env['eacta.timetable.slot'].sudo()
        for contract in self:
            slots = Slot.search([('teacher_id', '=', contract.user_id.id)]) if contract.user_id else Slot
            contract.weekly_hours = round(sum(slots.mapped('duration')), 2)

    @api.depends('payslip_ids')
    def _compute_payslip_count(self):
        for contract in self:
            contract.payslip_count = len(contract.payslip_ids)

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for contract in self:
            if contract.date_end and contract.date_end < contract.date_start:
                raise ValidationError("La fin du contrat doit être postérieure à la date d'embauche.")

    @api.constrains('contract_type', 'monthly_wage', 'hourly_rate')
    def _check_wage(self):
        for contract in self:
            if contract.monthly_wage < 0 or contract.hourly_rate < 0:
                raise ValidationError("Le salaire et le taux horaire doivent être positifs.")

    @api.onchange('user_id')
    def _onchange_user_id(self):
        if self.user_id and not self.name:
            self.name = self.user_id.name

    def action_start(self):
        for contract in self:
            if contract.contract_type == 'vacataire' and not contract.hourly_rate:
                raise UserError(f"Indiquez le taux horaire de {contract.name}.")
            if contract.contract_type != 'vacataire' and not contract.monthly_wage:
                raise UserError(f"Indiquez le salaire mensuel de {contract.name}.")
        self.write({'state': 'running'})

    def action_end(self):
        self.write({'state': 'ended', 'date_end': fields.Date.context_today(self)})

    def action_view_payslips(self):
        self.ensure_one()
        return {
            'name': f"Bulletins - {self.name}",
            'type': 'ir.actions.act_window',
            'res_model': 'eacta.payslip',
            'view_mode': 'list,form',
            'domain': [('contract_id', '=', self.id)],
            'context': {'default_contract_id': self.id},
        }


class EactaPayslip(models.Model):
    _name = 'eacta.payslip'
    _description = 'Bulletin de paie'
    _inherit = ['mail.thread']
    _order = 'date_from desc, contract_id'

    name = fields.Char(string='Référence', readonly=True, copy=False, default='/', index=True)
    contract_id = fields.Many2one('eacta.staff.contract', string='Contrat', required=True, index=True,
                                  ondelete='restrict')
    employee_name = fields.Char(related='contract_id.name', store=True, string='Employé')
    job = fields.Selection(related='contract_id.job', store=True, string='Fonction')
    contract_type = fields.Selection(related='contract_id.contract_type', string='Type de contrat')
    date_from = fields.Date(string='Du', required=True)
    date_to = fields.Date(string='Au', required=True)
    worked_hours = fields.Float(string='Heures effectuées')
    base_amount = fields.Monetary(string='Salaire de base', compute='_compute_amounts', store=True,
                                  currency_field='currency_id')
    bonus = fields.Monetary(string='Primes', currency_field='currency_id')
    overtime_amount = fields.Monetary(string='Heures supplémentaires', currency_field='currency_id')
    gross = fields.Monetary(string='Salaire brut', compute='_compute_amounts', store=True,
                            currency_field='currency_id')
    cnss_amount = fields.Monetary(string='CNSS salarié', compute='_compute_amounts', store=True,
                                  currency_field='currency_id')
    amo_amount = fields.Monetary(string='AMO salarié', compute='_compute_amounts', store=True,
                                 currency_field='currency_id')
    income_tax = fields.Monetary(string='IR retenu', currency_field='currency_id',
                                 help="Impôt sur le revenu retenu à la source, saisi par le service comptable.")
    other_deductions = fields.Monetary(string='Autres retenues', currency_field='currency_id',
                                       help="Avances, absences non payées...")
    net = fields.Monetary(string='Net à payer', compute='_compute_amounts', store=True,
                          currency_field='currency_id')
    currency_id = fields.Many2one(related='contract_id.currency_id', store=True)
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('confirmed', 'Validé'),
        ('paid', 'Payé'),
    ], string='État', default='draft', required=True, tracking=True, index=True)
    payment_date = fields.Date(string='Payé le', readonly=True, copy=False)
    note = fields.Text(string='Remarque')
    company_id = fields.Many2one(related='contract_id.company_id', store=True)

    _sql_constraints = [
        ('contract_period_unique', 'UNIQUE(contract_id, date_from)',
         "Un bulletin existe déjà pour ce contrat sur cette période."),
    ]

    @api.depends('contract_id.contract_type', 'contract_id.monthly_wage', 'contract_id.hourly_rate',
                 'worked_hours', 'bonus', 'overtime_amount', 'income_tax', 'other_deductions')
    def _compute_amounts(self):
        ICP = self.env['ir.config_parameter'].sudo()
        cnss_rate = float(ICP.get_param('eacta_school.payroll_cnss_rate', 4.48)) / 100.0
        cnss_ceiling = float(ICP.get_param('eacta_school.payroll_cnss_ceiling', 6000.0))
        amo_rate = float(ICP.get_param('eacta_school.payroll_amo_rate', 2.26)) / 100.0
        for slip in self:
            contract = slip.contract_id
            if contract.contract_type == 'vacataire':
                base = round(slip.worked_hours * contract.hourly_rate, 2)
            else:
                base = contract.monthly_wage
            gross = base + slip.bonus + slip.overtime_amount
            cnss = round(min(gross, cnss_ceiling) * cnss_rate, 2)
            amo = round(gross * amo_rate, 2)
            slip.base_amount = base
            slip.gross = gross
            slip.cnss_amount = cnss
            slip.amo_amount = amo
            slip.net = round(gross - cnss - amo - slip.income_tax - slip.other_deductions, 2)

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for slip in self:
            if slip.date_to < slip.date_from:
                raise ValidationError("La fin de période doit être postérieure à son début.")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code('eacta.payslip') or '/'
        return super().create(vals_list)

    def write(self, vals):
        locked = {'worked_hours', 'bonus', 'overtime_amount', 'income_tax', 'other_deductions', 'contract_id',
                  'date_from', 'date_to'}
        if locked & set(vals) and any(slip.state != 'draft' for slip in self):
            raise UserError("Un bulletin validé ne peut plus être modifié : remettez-le d'abord en brouillon.")
        return super().write(vals)

    def unlink(self):
        if any(slip.state == 'paid' for slip in self):
            raise UserError("Impossible de supprimer un bulletin déjà payé.")
        return super().unlink()

    def action_confirm(self):
        for slip in self:
            if slip.net < 0:
                raise UserError(f"Le net à payer de {slip.employee_name} est négatif : vérifiez les retenues.")
        self.write({'state': 'confirmed'})

    def action_mark_paid(self):
        self.filtered(lambda s: s.state == 'confirmed').write({
            'state': 'paid', 'payment_date': fields.Date.context_today(self)})

    def action_draft(self):
        if any(slip.state == 'paid' for slip in self):
            raise UserError("Un bulletin payé ne peut pas être remis en brouillon.")
        self.write({'state': 'draft'})

    def action_print(self):
        return self.env.ref('eacta_school.action_report_payslip').report_action(self)


class EactaPayslipGenerateWizard(models.TransientModel):
    _name = 'eacta.payslip.generate.wizard'
    _description = 'Génération des bulletins du mois'

    month = fields.Date(string='Mois', required=True,
                        default=lambda self: fields.Date.context_today(self).replace(day=1))
    contract_ids = fields.Many2many('eacta.staff.contract', string='Contrats',
                                    domain="[('state', '=', 'running')]",
                                    help="Laisser vide pour tous les contrats en cours.")

    def action_generate(self):
        self.ensure_one()
        date_from = self.month.replace(day=1)
        date_to = date_from + relativedelta(months=1, days=-1)
        contracts = self.contract_ids or self.env['eacta.staff.contract'].search([('state', '=', 'running')])
        Payslip = self.env['eacta.payslip']
        vals_list = []
        for contract in contracts:
            if contract.date_start > date_to or (contract.date_end and contract.date_end < date_from):
                continue
            if Payslip.search_count([('contract_id', '=', contract.id), ('date_from', '=', date_from)]):
                continue
            hours = round(contract.weekly_hours * WEEKS_PER_MONTH, 1) if contract.contract_type == 'vacataire' \
                else 0.0
            vals_list.append({'contract_id': contract.id, 'date_from': date_from, 'date_to': date_to,
                              'worked_hours': hours})
        slips = Payslip.create(vals_list)
        return {
            'name': f"Bulletins de {date_from.strftime('%m/%Y')}",
            'type': 'ir.actions.act_window',
            'res_model': 'eacta.payslip',
            'view_mode': 'list,form',
            'domain': [('date_from', '=', date_from)],
            'context': {'created_ids': slips.ids},
        }
