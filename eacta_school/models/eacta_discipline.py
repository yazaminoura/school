from odoo import api, fields, models
from odoo.exceptions import UserError

SANCTION_TYPES = [
    ('oral_warning', 'Avertissement oral'),
    ('written_warning', 'Avertissement écrit'),
    ('blame', 'Blâme'),
    ('detention', 'Retenue'),
    ('temporary_exclusion', 'Exclusion temporaire'),
    ('council', 'Conseil de discipline'),
]

CONDUCT_BASE = 20.0


class EactaDisciplineIncidentType(models.Model):
    _name = 'eacta.discipline.incident.type'
    _description = "Type d'incident / de comportement"
    _order = 'kind, sequence, name'

    name = fields.Char(string='Nom', required=True, translate=True)
    sequence = fields.Integer(default=10)
    kind = fields.Selection([
        ('negative', 'Incident'),
        ('positive', 'Comportement positif'),
    ], string='Nature', default='negative', required=True)
    severity = fields.Selection([
        ('minor', 'Mineur'),
        ('major', 'Grave'),
        ('serious', 'Très grave'),
    ], string='Gravité', default='minor')
    default_points = fields.Float(string='Points de conduite', default=-1.0,
                                  help="Impact sur la note de conduite (sur 20) : négatif pour un incident, "
                                       "positif pour un comportement exemplaire.")
    active = fields.Boolean(default=True)


class EactaDisciplineIncident(models.Model):
    _name = 'eacta.discipline.incident'
    _description = 'Incident de vie scolaire'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(string='Référence', readonly=True, copy=False, default='/', index=True)
    student_id = fields.Many2one('eacta.student', string='Élève', required=True, index=True, tracking=True)
    student_image = fields.Image(related='student_id.image_128', string='Photo')
    class_id = fields.Many2one('eacta.class', string='Classe', compute='_compute_class_id', store=True,
                               readonly=False, index=True)
    academic_year_id = fields.Many2one(related='class_id.academic_year_id', store=True, string='Année académique')
    date = fields.Date(string='Date', required=True, default=fields.Date.context_today, index=True, tracking=True)
    type_id = fields.Many2one('eacta.discipline.incident.type', string='Type', required=True, tracking=True)
    kind = fields.Selection(related='type_id.kind', store=True, string='Nature')
    severity = fields.Selection(related='type_id.severity', store=True, string='Gravité')
    points = fields.Float(string='Points de conduite', tracking=True)
    location = fields.Char(string='Lieu', help="ex : Cour, Salle B201, Cantine")
    course_id = fields.Many2one('eacta.course', string='Pendant le cours de')
    description = fields.Text(string='Description des faits', required=True)
    reported_by = fields.Many2one('res.users', string='Signalé par', default=lambda self: self.env.user,
                                  readonly=True)
    state = fields.Selection([
        ('draft', 'Signalé'),
        ('confirmed', 'Validé'),
        ('closed', 'Clôturé'),
        ('cancelled', 'Annulé'),
    ], string='État', default='draft', required=True, tracking=True, index=True)
    sanction_ids = fields.One2many('eacta.discipline.sanction', 'incident_id', string='Sanctions')
    sanction_count = fields.Integer(compute='_compute_sanction_count', string='Sanctions')
    parent_notified = fields.Boolean(string='Parents informés', readonly=True, copy=False, tracking=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)

    @api.depends('student_id')
    def _compute_class_id(self):
        for incident in self:
            if not incident.class_id:
                incident.class_id = incident.student_id.current_class_id

    @api.depends('sanction_ids')
    def _compute_sanction_count(self):
        for incident in self:
            incident.sanction_count = len(incident.sanction_ids)

    @api.onchange('type_id')
    def _onchange_type_id(self):
        if self.type_id:
            self.points = self.type_id.default_points

    @api.model_create_multi
    def create(self, vals_list):
        Type = self.env['eacta.discipline.incident.type']
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code('eacta.discipline.incident') or '/'
            if 'points' not in vals and vals.get('type_id'):
                vals['points'] = Type.browse(vals['type_id']).default_points
        return super().create(vals_list)

    def action_confirm(self):
        for incident in self:
            if incident.state != 'draft':
                raise UserError(f"Seul un incident signalé peut être validé ({incident.name}).")
        self.write({'state': 'confirmed'})
        self.filtered(lambda i: i.kind == 'negative' and i.severity in ('major', 'serious'))._notify_parents()

    def action_close(self):
        self.write({'state': 'closed'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_draft(self):
        self.write({'state': 'draft'})

    def action_notify_parents(self):
        self._notify_parents()
        return True

    def _notify_parents(self):
        Channel = self.env['eacta.notification.channel']
        for incident in self:
            notified = self.env['res.partner']
            for parent in incident.student_id.parent_ids.filtered('email'):
                if Channel.send_notification('email', parent, 'eacta_school.email_template_discipline_incident',
                                             incident._name, incident.id):
                    notified |= parent
            if notified:
                incident.parent_notified = True
                incident.message_post(body=f"Parents informés par email : {', '.join(notified.mapped('name'))}.")

    def action_add_sanction(self):
        self.ensure_one()
        return {
            'name': 'Nouvelle sanction',
            'type': 'ir.actions.act_window',
            'res_model': 'eacta.discipline.sanction',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_incident_id': self.id},
        }


class EactaDisciplineSanction(models.Model):
    _name = 'eacta.discipline.sanction'
    _description = 'Sanction disciplinaire'
    _inherit = ['mail.thread']
    _order = 'date desc, id desc'

    incident_id = fields.Many2one('eacta.discipline.incident', string='Incident', required=True,
                                  ondelete='cascade', index=True)
    student_id = fields.Many2one(related='incident_id.student_id', store=True, string='Élève', index=True)
    class_id = fields.Many2one(related='incident_id.class_id', store=True, string='Classe')
    sanction_type = fields.Selection(SANCTION_TYPES, string='Sanction', required=True, tracking=True)
    date = fields.Date(string='Date de décision', required=True, default=fields.Date.context_today)
    date_from = fields.Date(string='Du')
    date_to = fields.Date(string='Au')
    duration_days = fields.Integer(string='Durée (jours)', compute='_compute_duration_days', store=True)
    decided_by = fields.Many2one('res.users', string='Décidée par', default=lambda self: self.env.user)
    note = fields.Text(string='Motif / Observations')

    @api.depends('date_from', 'date_to')
    def _compute_duration_days(self):
        for sanction in self:
            if sanction.date_from and sanction.date_to and sanction.date_to >= sanction.date_from:
                sanction.duration_days = (sanction.date_to - sanction.date_from).days + 1
            else:
                sanction.duration_days = 0

    @api.depends('sanction_type', 'student_id')
    def _compute_display_name(self):
        labels = dict(SANCTION_TYPES)
        for sanction in self:
            sanction.display_name = f"{labels.get(sanction.sanction_type, '')} - {sanction.student_id.name or ''}"


class EactaStudentDiscipline(models.Model):
    _inherit = 'eacta.student'

    incident_ids = fields.One2many('eacta.discipline.incident', 'student_id', string='Vie scolaire')
    incident_count = fields.Integer(string='Incidents', compute='_compute_conduct')
    conduct_score = fields.Float(string='Note de conduite', compute='_compute_conduct', digits=(4, 2),
                                 help="Note de conduite sur 20 pour l'année en cours : 20 + points des "
                                      "incidents et comportements validés.")

    @api.depends('incident_ids.points', 'incident_ids.state', 'incident_ids.academic_year_id', 'academic_year_id')
    def _compute_conduct(self):
        for student in self:
            # Lecture en sudo : la note de conduite s'affiche à tous ceux qui voient la fiche élève
            incidents = student.sudo().incident_ids.filtered(
                lambda i: i.state in ('confirmed', 'closed')
                and (not student.academic_year_id or i.academic_year_id == student.academic_year_id))
            student.incident_count = len(incidents.filtered(lambda i: i.kind == 'negative'))
            score = CONDUCT_BASE + sum(incidents.mapped('points'))
            student.conduct_score = round(min(max(score, 0.0), CONDUCT_BASE), 2)

    def action_view_incidents(self):
        self.ensure_one()
        return {
            'name': f"Vie scolaire - {self.name}",
            'type': 'ir.actions.act_window',
            'res_model': 'eacta.discipline.incident',
            'view_mode': 'list,form',
            'domain': [('student_id', '=', self.id)],
            'context': {'default_student_id': self.id},
        }
