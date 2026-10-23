from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from .eacta_fee import _get_school_currency

CANTEEN_PLANS = [
    ('full', 'Forfait 5 jours'),
    ('four_days', 'Forfait 4 jours (sans mercredi)'),
    ('occasional', 'Repas occasionnels'),
]


class EactaCanteenMenu(models.Model):
    _name = 'eacta.canteen.menu'
    _description = 'Menu de la cantine'
    _order = 'date desc, meal'

    date = fields.Date(string='Date', required=True, index=True)
    meal = fields.Selection([
        ('lunch', 'Déjeuner'),
        ('snack', 'Goûter'),
    ], string='Repas', default='lunch', required=True)
    starter = fields.Char(string='Entrée')
    main_course = fields.Char(string='Plat principal', required=True)
    vegetarian_option = fields.Char(string='Option végétarienne')
    dessert = fields.Char(string='Dessert')
    allergens = fields.Char(string='Allergènes', help="ex : gluten, lait, œufs, arachides")
    note = fields.Char(string='Remarque')
    weekday = fields.Char(string='Jour', compute='_compute_weekday')

    _sql_constraints = [
        ('date_meal_unique', 'UNIQUE(date, meal)', "Un menu existe déjà pour ce repas à cette date."),
    ]

    @api.depends('date')
    def _compute_weekday(self):
        days = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']
        for menu in self:
            menu.weekday = days[menu.date.weekday()] if menu.date else False

    @api.depends('date', 'meal', 'main_course')
    def _compute_display_name(self):
        meals = dict(self._fields['meal'].selection)
        for menu in self:
            menu.display_name = f"{meals.get(menu.meal)} du {menu.date} : {menu.main_course or ''}"


class EactaCanteenSubscription(models.Model):
    _name = 'eacta.canteen.subscription'
    _description = 'Abonnement cantine'
    _inherit = ['mail.thread']
    _order = 'date_start desc, id desc'

    student_id = fields.Many2one('eacta.student', string='Élève', required=True, index=True, tracking=True)
    class_id = fields.Many2one(related='student_id.current_class_id', store=True, string='Classe')
    academic_year_id = fields.Many2one('eacta.academic.year', string='Année académique', required=True,
                                       default=lambda self: self.env['eacta.academic.year'].get_current_year())
    plan = fields.Selection(CANTEEN_PLANS, string='Formule', default='full', required=True, tracking=True)
    date_start = fields.Date(string='Début', required=True, default=fields.Date.context_today, tracking=True)
    date_end = fields.Date(string='Fin', tracking=True)
    monthly_price = fields.Monetary(string='Prix mensuel', currency_field='currency_id', tracking=True)
    currency_id = fields.Many2one('res.currency', default=lambda self: _get_school_currency(self.env))
    diet_note = fields.Char(string='Régime / allergies',
                            help="ex : sans porc, sans gluten, végétarien. Rappelé sur l'effectif du jour.")
    state = fields.Selection([
        ('active', 'Actif'),
        ('suspended', 'Suspendu'),
        ('ended', 'Terminé'),
    ], string='État', default='active', required=True, tracking=True, index=True)
    fee_ids = fields.One2many('eacta.student.fee', 'canteen_subscription_id', string='Frais facturés')
    fee_count = fields.Integer(compute='_compute_fee_count', string='Frais')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)

    @api.depends('fee_ids')
    def _compute_fee_count(self):
        for subscription in self:
            subscription.fee_count = len(subscription.fee_ids)

    @api.depends('student_id', 'plan')
    def _compute_display_name(self):
        plans = dict(CANTEEN_PLANS)
        for subscription in self:
            subscription.display_name = f"{subscription.student_id.name or ''} - {plans.get(subscription.plan)}"

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for subscription in self:
            if subscription.date_end and subscription.date_end < subscription.date_start:
                raise ValidationError("La date de fin de l'abonnement doit être postérieure à sa date de début.")

    @api.constrains('student_id', 'state', 'date_start', 'date_end')
    def _check_single_active(self):
        for subscription in self.filtered(lambda s: s.state == 'active'):
            if self.search_count([('student_id', '=', subscription.student_id.id), ('state', '=', 'active'),
                                  ('id', '!=', subscription.id)]):
                raise ValidationError(f"{subscription.student_id.name} a déjà un abonnement cantine actif.")

    @api.onchange('plan')
    def _onchange_plan(self):
        ICP = self.env['ir.config_parameter'].sudo()
        prices = {
            'full': float(ICP.get_param('eacta_school.canteen_price_full', 900.0)),
            'four_days': float(ICP.get_param('eacta_school.canteen_price_four_days', 750.0)),
            'occasional': 0.0,
        }
        self.monthly_price = prices.get(self.plan, 0.0)

    @api.model_create_multi
    def create(self, vals_list):
        subscriptions = super().create(vals_list)
        subscriptions._sync_student_canteen()
        return subscriptions

    def write(self, vals):
        res = super().write(vals)
        if 'state' in vals or 'student_id' in vals:
            self._sync_student_canteen()
        return res

    def _sync_student_canteen(self):
        for subscription in self:
            active = bool(self.search_count([('student_id', '=', subscription.student_id.id),
                                             ('state', '=', 'active')]))
            if subscription.student_id.canteen != active:
                subscription.student_id.canteen = active

    def action_suspend(self):
        self.write({'state': 'suspended'})

    def action_resume(self):
        self.write({'state': 'active'})

    def action_end(self):
        self.write({'state': 'ended', 'date_end': fields.Date.context_today(self)})

    def action_generate_month_fee(self, month_date=None):
        """Facture le mois en cours (ou celui de month_date) dans les frais de scolarité."""
        fee_type = self.env.ref('eacta_school.fee_type_canteen', raise_if_not_found=False)
        if not fee_type:
            raise UserError("Le type de frais « Cantine » est introuvable.")
        month_start = (month_date or fields.Date.context_today(self)).replace(day=1)
        label = f"Cantine {month_start.strftime('%m/%Y')}"
        Fee = self.env['eacta.student.fee']
        created = Fee
        for subscription in self.filtered(lambda s: s.state == 'active' and s.monthly_price > 0):
            if subscription.fee_ids.filtered(lambda f: f.description == label and not f.is_cancelled):
                continue
            created |= Fee.create({
                'student_id': subscription.student_id.id,
                'fee_type_id': fee_type.id,
                'academic_year_id': subscription.academic_year_id.id,
                'description': label,
                'amount': subscription.monthly_price,
                'currency_id': subscription.currency_id.id,
                'due_date': month_start + relativedelta(days=9),
                'canteen_subscription_id': subscription.id,
            })
        return created

    @api.model
    def _cron_generate_canteen_fees(self):
        self.search([('state', '=', 'active')]).action_generate_month_fee()

    def action_view_fees(self):
        self.ensure_one()
        return {
            'name': f"Frais cantine - {self.student_id.name}",
            'type': 'ir.actions.act_window',
            'res_model': 'eacta.student.fee',
            'view_mode': 'list,form',
            'domain': [('canteen_subscription_id', '=', self.id)],
        }


class EactaStudentFeeCanteen(models.Model):
    _inherit = 'eacta.student.fee'

    canteen_subscription_id = fields.Many2one('eacta.canteen.subscription', string='Abonnement cantine',
                                              ondelete='set null', index=True)


class EactaCanteenCountWizard(models.TransientModel):
    _name = 'eacta.canteen.count.wizard'
    _description = 'Effectif cantine du jour'

    date = fields.Date(string='Date', required=True, default=fields.Date.context_today)
    menu_id = fields.Many2one('eacta.canteen.menu', string='Menu', compute='_compute_lines')
    line_ids = fields.One2many('eacta.canteen.count.line', 'wizard_id', string='Par classe',
                               compute='_compute_lines')
    total_expected = fields.Integer(string='Repas à préparer', compute='_compute_lines')
    diet_summary = fields.Text(string='Régimes particuliers', compute='_compute_lines')

    @api.depends('date')
    def _compute_lines(self):
        Subscription = self.env['eacta.canteen.subscription']
        Attendance = self.env['eacta.attendance']
        for wizard in self:
            day = wizard.date
            wizard.menu_id = self.env['eacta.canteen.menu'].search([('date', '=', day), ('meal', '=', 'lunch')],
                                                                    limit=1)
            if not day:
                wizard.line_ids = [(5, 0, 0)]
                wizard.total_expected = 0
                wizard.diet_summary = False
                continue
            plans = ['full'] if day.weekday() == 2 else ['full', 'four_days']
            subscriptions = Subscription.search([
                ('state', '=', 'active'), ('plan', 'in', plans), ('date_start', '<=', day),
                '|', ('date_end', '=', False), ('date_end', '>=', day),
            ])
            absent = Attendance.search([
                ('date', '=', day), ('attendance_type', '=', 'absent'),
                ('session', 'in', ('all_day', 'morning')),
                ('student_id', 'in', subscriptions.student_id.ids),
            ]).student_id
            lines = [(5, 0, 0)]
            total = 0
            for klass in subscriptions.class_id.sorted('name'):
                class_subs = subscriptions.filtered(lambda s: s.class_id == klass)
                class_absent = class_subs.student_id & absent
                expected = len(class_subs) - len(class_absent)
                total += expected
                lines.append((0, 0, {
                    'class_id': klass.id,
                    'subscribed': len(class_subs),
                    'absent': len(class_absent),
                    'expected': expected,
                }))
            wizard.line_ids = lines
            wizard.total_expected = total
            diets = subscriptions.filtered(lambda s: s.diet_note and s.student_id not in absent)
            wizard.diet_summary = '\n'.join(
                f"{s.student_id.name} ({s.class_id.name or '-'}) : {s.diet_note}" for s in diets) or False


class EactaCanteenCountLine(models.TransientModel):
    _name = 'eacta.canteen.count.line'
    _description = 'Effectif cantine par classe'

    wizard_id = fields.Many2one('eacta.canteen.count.wizard', ondelete='cascade')
    class_id = fields.Many2one('eacta.class', string='Classe')
    subscribed = fields.Integer(string='Inscrits')
    absent = fields.Integer(string='Absents')
    expected = fields.Integer(string='Repas')
