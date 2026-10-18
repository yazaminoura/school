from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class EactaAcademicYear(models.Model):
    _name = 'eacta.academic.year'
    _description = 'Année académique'
    _inherit = ['mail.thread']
    _order = 'date_start desc, name desc'

    name = fields.Char(string='Nom', required=True, tracking=True, help="Ex: 2026-2027")
    date_start = fields.Date(string='Date de début', required=True, tracking=True)
    date_end = fields.Date(string='Date de fin', required=True, tracking=True)
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('open', 'En cours'),
        ('closed', 'Clôturée'),
    ], string='État', default='draft', required=True, tracking=True)
    term_ids = fields.One2many('eacta.term', 'academic_year_id', string='Trimestres / Semestres')
    class_ids = fields.One2many('eacta.class', 'academic_year_id', string='Classes')
    class_count = fields.Integer(string='Nombre de classes', compute='_compute_counts')
    term_count = fields.Integer(string='Nombre de trimestres', compute='_compute_counts')
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', string='Établissement', default=lambda self: self.env.company)

    _sql_constraints = [
        ('name_unique', 'UNIQUE(name)', "Une année académique avec ce nom existe déjà !"),
    ]

    @api.depends('class_ids', 'term_ids')
    def _compute_counts(self):
        for rec in self:
            rec.class_count = len(rec.class_ids)
            rec.term_count = len(rec.term_ids)

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for rec in self:
            if rec.date_start and rec.date_end and rec.date_end <= rec.date_start:
                raise ValidationError("La date de fin doit être strictement postérieure à la date de début.")

    @api.constrains('state')
    def _check_single_open_year(self):
        for rec in self:
            if rec.state == 'open':
                other = self.search([('id', '!=', rec.id), ('state', '=', 'open')], limit=1)
                if other:
                    raise ValidationError(
                        f"Une seule année académique peut être ouverte à la fois. "
                        f"L'année « {other.name} » est actuellement ouverte. Veuillez la clôturer d'abord."
                    )

    def action_open(self):
        for rec in self:
            other = self.search([('id', '!=', rec.id), ('state', '=', 'open')], limit=1)
            if other:
                raise UserError(
                    f"Impossible d'ouvrir l'année « {rec.name} » car l'année « {other.name} » est déjà ouverte. "
                    f"Veuillez d'abord clôturer « {other.name} »."
                )
            rec.state = 'open'

    def action_close(self):
        self.write({'state': 'closed'})

    def action_draft(self):
        self.write({'state': 'draft'})

    @api.model
    def get_current_year(self):
        """Retourne l'année académique active (ouverte) ou la plus récente."""
        open_year = self.search([('state', '=', 'open')], limit=1)
        if open_year:
            return open_year
        return self.search([], order='date_start desc, id desc', limit=1)


class EactaTerm(models.Model):
    _name = 'eacta.term'
    _description = 'Trimestre / Semestre'
    _order = 'academic_year_id desc, sequence, date_start'

    name = fields.Char(string='Nom', required=True, help="Ex: 1er Trimestre")
    academic_year_id = fields.Many2one(
        'eacta.academic.year', string='Année académique',
        required=True, ondelete='cascade', index=True
    )
    date_start = fields.Date(string='Date de début', required=True)
    date_end = fields.Date(string='Date de fin', required=True)
    sequence = fields.Integer(string='Séquence', default=10)
    weight = fields.Float(string='Pondération annuelle', default=1.0, help="Poids de ce trimestre dans la moyenne annuelle")
    active = fields.Boolean(default=True)

    @property
    def year_id(self):
        return self.academic_year_id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'year_id' in vals and 'academic_year_id' not in vals:
                vals['academic_year_id'] = vals.pop('year_id')
        return super().create(vals_list)

    def write(self, vals):
        if 'year_id' in vals and 'academic_year_id' not in vals:
            vals['academic_year_id'] = vals.pop('year_id')
        return super().write(vals)

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None):
        if domain:
            new_domain = []
            for leaf in domain:
                if isinstance(leaf, (list, tuple)) and len(leaf) == 3 and leaf[0] == 'year_id':
                    new_domain.append(('academic_year_id', leaf[1], leaf[2]))
                else:
                    new_domain.append(leaf)
            domain = new_domain
        return super()._search(domain, offset=offset, limit=limit, order=order)

    @api.depends('name', 'academic_year_id.name')
    def _compute_display_name(self):
        for term in self:
            if term.academic_year_id:
                term.display_name = f"{term.name} ({term.academic_year_id.name})"
            else:
                term.display_name = term.name or ''

    @api.constrains('date_start', 'date_end', 'academic_year_id')
    def _check_term_dates(self):
        for term in self:
            if term.date_start and term.date_end:
                if term.date_end <= term.date_start:
                    raise ValidationError("La date de fin doit être strictement postérieure à la date de début.")
                if term.academic_year_id:
                    if term.date_start < term.academic_year_id.date_start or term.date_end > term.academic_year_id.date_end:
                        raise ValidationError(
                            f"Les dates du trimestre « {term.name} » ({term.date_start} au {term.date_end}) "
                            f"doivent être comprises dans celles de l'année « {term.academic_year_id.name} » "
                            f"({term.academic_year_id.date_start} au {term.academic_year_id.date_end})."
                        )
                    overlap = self.search([
                        ('id', '!=', term.id),
                        ('academic_year_id', '=', term.academic_year_id.id),
                        ('date_start', '<=', term.date_end),
                        ('date_end', '>=', term.date_start),
                    ], limit=1)
                    if overlap:
                        raise ValidationError(
                            f"Les dates du trimestre « {term.name} » chevauchent celles de « {overlap.name} »."
                        )

