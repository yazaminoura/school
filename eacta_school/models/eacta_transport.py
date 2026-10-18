from odoo import api, fields, models
from odoo.exceptions import ValidationError


class EactaTransportLine(models.Model):
    _name = 'eacta.transport.line'
    _description = 'Ligne de transport scolaire'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'code, name'

    name = fields.Char(string='Nom de la ligne', required=True, tracking=True)
    code = fields.Char(string='Code / Numéro', required=True, tracking=True)
    active = fields.Boolean(default=True)

    vehicle_name = fields.Char(string='Véhicule / Immatriculation', tracking=True)
    driver_name = fields.Char(string='Nom du conducteur', tracking=True)
    driver_phone = fields.Char(string='Téléphone du conducteur', tracking=True)
    driver_user_id = fields.Many2one('res.users', string='Chauffeur (Compte utilisateur)', tracking=True)

    capacity = fields.Integer(string='Capacité (places)', required=True, default=20, tracking=True)
    passenger_ids = fields.One2many('eacta.student', 'transport_line_id', string='Passagers inscrits')
    passenger_count = fields.Integer(string='Passagers', compute='_compute_passengers', store=True)
    available_seats = fields.Integer(string='Places disponibles', compute='_compute_passengers', store=True)

    stop_ids = fields.One2many('eacta.transport.stop', 'line_id', string='Arrêts desservis')
    stop_count = fields.Integer(string="Nombre d'arrêts", compute='_compute_stop_count')

    note = fields.Text(string='Itinéraire / Remarques')
    company_id = fields.Many2one('res.company', string='Établissement', default=lambda self: self.env.company)

    _sql_constraints = [
        ('code_uniq', 'UNIQUE(code, company_id)', "Le code de cette ligne de transport doit être unique par établissement."),
    ]

    @api.depends('passenger_ids', 'capacity')
    def _compute_passengers(self):
        for line in self:
            count = len(line.passenger_ids)
            line.passenger_count = count
            line.available_seats = max(line.capacity - count, 0)

    @api.depends('stop_ids')
    def _compute_stop_count(self):
        for line in self:
            line.stop_count = len(line.stop_ids)

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for line in self:
            line.display_name = f"[{line.code}] {line.name}" if line.code else line.name

    @api.constrains('capacity', 'passenger_ids')
    def _check_capacity(self):
        for line in self:
            if line.capacity <= 0:
                raise ValidationError("La capacité d'un véhicule de transport doit être strictement supérieure à zéro.")
            if line.capacity and len(line.passenger_ids) > line.capacity:
                raise ValidationError(
                    f"Capacité dépassée pour la ligne « {line.name} » : "
                    f"{len(line.passenger_ids)} passager(s) inscrit(s) pour {line.capacity} place(s) disponible(s)."
                )


class EactaTransportStop(models.Model):
    _name = 'eacta.transport.stop'
    _description = "Arrêt de transport scolaire"
    _order = 'line_id, sequence, id'

    name = fields.Char(string="Nom de l'arrêt", required=True)
    sequence = fields.Integer(string='Ordre de passage', default=10)
    line_id = fields.Many2one('eacta.transport.line', string='Ligne de transport', required=True, ondelete='cascade', index=True)

    time_morning = fields.Char(string='Passage matin', default='07:30', help="Heure estimée de passage le matin (ex: 07:35)")
    time_evening = fields.Char(string='Passage soir', default='17:00', help="Heure estimée de passage l'après-midi (ex: 17:15)")
    location = fields.Char(string='Adresse / Repère')

    student_ids = fields.One2many('eacta.student', 'transport_stop_id', string='Élèves à cet arrêt')
    student_count = fields.Integer(string="Nombre d'élèves", compute='_compute_student_count')

    @api.depends('student_ids')
    def _compute_student_count(self):
        for stop in self:
            stop.student_count = len(stop.student_ids)

    @api.depends('name', 'line_id.name', 'time_morning')
    def _compute_display_name(self):
        for stop in self:
            time_str = f" ({stop.time_morning})" if stop.time_morning else ""
            stop.display_name = f"{stop.name}{time_str} - {stop.line_id.name}" if stop.line_id else stop.name
