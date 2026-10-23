from datetime import datetime, time, timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.addons.eacta_school.models.sample_data import sample_data_step, sample_records

EVENT_TYPES = [
    ('outing', 'Sortie pédagogique'),
    ('trip', 'Voyage scolaire'),
    ('ceremony', 'Cérémonie'),
    ('competition', 'Compétition'),
    ('sport', 'Activité sportive'),
    ('cultural', 'Activité culturelle'),
    ('meeting', 'Réunion parents-professeurs'),
    ('open_day', 'Journée portes ouvertes'),
    ('conference', 'Conférence / atelier'),
    ('other', 'Autre'),
]


class EactaSchoolEvent(models.Model):
    _name = 'eacta.school.event'
    _description = 'Événement scolaire'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_start desc, id desc'

    name = fields.Char(string="Nom de l'événement", required=True, tracking=True)
    event_type = fields.Selection(EVENT_TYPES, string='Type', default='outing', required=True, tracking=True)
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('confirmed', 'Confirmé'),
        ('in_progress', 'En cours'),
        ('done', 'Terminé'),
        ('cancel', 'Annulé'),
    ], string='État', default='draft', required=True, tracking=True, group_expand='_group_expand_states')
    date_start = fields.Datetime(string='Début', tracking=True,
                                 default=lambda self: datetime.combine(fields.Date.today() + timedelta(days=7), time(8, 0)))
    date_end = fields.Datetime(string='Fin', tracking=True)
    date = fields.Date(string="Date", compute='_compute_date', store=True, readonly=False)
    all_day = fields.Boolean(string='Toute la journée')
    location = fields.Char(string='Lieu', tracking=True)
    organizer_id = fields.Many2one('res.users', string="Organisateur", default=lambda self: self.env.user,
                                   tracking=True)
    supervisor_ids = fields.Many2many('res.users', 'eacta_event_supervisor_rel', 'event_id', 'user_id',
                                      string='Encadrants')
    class_ids = fields.Many2many('eacta.class', 'eacta_event_class_rel', 'event_id', 'class_id',
                                 string='Classes concernées')
    capacity = fields.Integer(string='Places', help="0 = illimité")
    registration_deadline = fields.Date(string="Date limite d'inscription")
    requires_authorization = fields.Boolean(string='Autorisation parentale requise', default=True)
    fee_amount = fields.Monetary(string='Participation par élève', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    description = fields.Text(string="Description")
    program = fields.Html(string='Programme')
    image = fields.Image(string="Image", max_width=1920, max_height=1920)
    color = fields.Integer(string='Couleur')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)

    registration_ids = fields.One2many('eacta.school.event.registration', 'event_id', string='Inscriptions')
    participant_ids = fields.Many2many('eacta.student', string="Participants", compute='_compute_participant_ids',
                                       search='_search_participant_ids')
    participant_count = fields.Integer(string="Inscrits", compute='_compute_stats', store=True)
    attended_count = fields.Integer(string="Présents", compute='_compute_stats', store=True)
    authorized_count = fields.Integer(string="Autorisations reçues", compute='_compute_stats', store=True)
    paid_count = fields.Integer(string="Participations payées", compute='_compute_stats', store=True)
    seats_available = fields.Integer(string='Places restantes', compute='_compute_stats', store=True)
    fill_rate = fields.Float(string='Remplissage (%)', compute='_compute_stats', store=True)
    amount_collected = fields.Monetary(string='Montant encaissé', compute='_compute_stats', store=True,
                                       currency_field='currency_id')
    amount_expected = fields.Monetary(string='Montant attendu', compute='_compute_stats', store=True,
                                      currency_field='currency_id')
    is_past = fields.Boolean(compute='_compute_is_past')

    @api.model
    def _group_expand_states(self, states, domain):
        return [key for key, _label in self._fields['state'].selection]

    @api.depends('date_start')
    def _compute_date(self):
        for event in self:
            if event.date_start:
                event.date = fields.Datetime.context_timestamp(event, event.date_start).date()

    @api.depends('registration_ids.state', 'registration_ids.authorized', 'registration_ids.paid', 'capacity',
                 'fee_amount')
    def _compute_stats(self):
        for event in self:
            regs = event.registration_ids.filtered(lambda r: r.state != 'cancelled')
            event.participant_count = len(regs)
            event.attended_count = len(regs.filtered(lambda r: r.state == 'attended'))
            event.authorized_count = len(regs.filtered('authorized'))
            event.paid_count = len(regs.filtered('paid'))
            event.seats_available = max(event.capacity - len(regs), 0) if event.capacity else 0
            event.fill_rate = round(100.0 * len(regs) / event.capacity, 1) if event.capacity else 0.0
            event.amount_expected = event.fee_amount * len(regs)
            event.amount_collected = event.fee_amount * event.paid_count

    @api.depends('registration_ids.state', 'registration_ids.student_id')
    def _compute_participant_ids(self):
        for event in self:
            event.participant_ids = event.registration_ids.filtered(lambda r: r.state != 'cancelled').student_id

    def _search_participant_ids(self, operator, value):
        regs = self.env['eacta.school.event.registration'].search(
            [('student_id', operator, value), ('state', '!=', 'cancelled')])
        return [('id', 'in', regs.event_id.ids)]

    def _compute_is_past(self):
        now = fields.Datetime.now()
        for event in self:
            event.is_past = bool(event.date_end or event.date_start) and (event.date_end or event.date_start) < now

    @api.onchange('date_start')
    def _onchange_date_start(self):
        if self.date_start and (not self.date_end or self.date_end <= self.date_start):
            self.date_end = self.date_start + timedelta(hours=4)

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for event in self:
            if event.date_start and event.date_end and event.date_end < event.date_start:
                raise ValidationError("La fin de l'événement doit être postérieure à son début.")

    @api.constrains('capacity')
    def _check_capacity(self):
        for event in self:
            if event.capacity < 0:
                raise ValidationError("Le nombre de places ne peut pas être négatif.")

    # ------------------------------------------------------------------
    def action_confirm(self):
        self.write({'state': 'confirmed'})

    def action_start(self):
        self.write({'state': 'in_progress'})

    def action_done(self):
        for event in self:
            event.registration_ids.filtered(lambda r: r.state == 'registered').write({'state': 'absent'})
        self.write({'state': 'done'})

    def action_cancel(self):
        self.write({'state': 'cancel'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})

    action_draft = action_reset_draft

    def action_sync_school_attendance(self):
        """Enregistre une présence dans le registre scolaire pour chaque élève ayant participé."""
        self.ensure_one()
        Attendance = self.env['eacta.attendance']
        event_date = self.date or fields.Date.context_today(self)
        created = 0
        for reg in self.registration_ids.filtered(lambda r: r.state == 'attended'):
            existing = Attendance.search([
                ('student_id', '=', reg.student_id.id),
                ('date', '=', event_date),
            ], limit=1)
            if not existing:
                Attendance.create({
                    'student_id': reg.student_id.id,
                    'class_id': reg.class_id.id if reg.class_id else reg.student_id.current_class_id.id,
                    'date': event_date,
                    'session': 'all_day' if self.all_day else 'morning',
                    'attendance_type': 'present',
                    'justified': True,
                    'reason': 'other',
                    'justification_note': f"Sortie / Événement : {self.name}",
                })
                created += 1
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': "Assiduité synchronisée",
                'message': f"{created} présence(s) enregistrée(s) dans le registre d'assiduité scolaire.",
                'type': 'success',
                'sticky': False,
            }
        }

    def action_register_classes(self):
        """Inscrit tous les élèves actifs des classes concernées (dans la limite des places)."""
        Registration = self.env['eacta.school.event.registration']
        for event in self:
            if not event.class_ids:
                raise UserError("Sélectionnez d'abord les classes concernées.")
            existing = event.registration_ids.student_id
            students = event.class_ids.student_ids.filtered(lambda s: s.state in ('draft', 'enrolled')) - existing
            if event.capacity:
                free = event.capacity - event.participant_count
                if free <= 0:
                    raise UserError(f"« {event.name} » est complet ({event.capacity} places).")
                students = students[:free]
            Registration.create([{'event_id': event.id, 'student_id': s.id} for s in students])
        return True

    def action_view_registrations(self):
        self.ensure_one()
        return {
            'name': f"Inscriptions - {self.name}",
            'type': 'ir.actions.act_window',
            'res_model': 'eacta.school.event.registration',
            'view_mode': 'list,kanban,form',
            'domain': [('event_id', '=', self.id)],
            'context': {'default_event_id': self.id, 'search_default_group_class': 1},
        }

    def action_mark_all_attended(self):
        """Pointe tous les élèves inscrits comme présents."""
        self.ensure_one()
        regs = self.registration_ids.filtered(lambda r: r.state == 'registered')
        regs.write({'state': 'attended'})
        return True

    def action_generate_fees(self):
        """Génère les frais de participation dans le module scolaire pour chaque élève inscrit."""
        self.ensure_one()
        if not self.fee_amount or self.fee_amount <= 0:
            raise UserError("Cet événement n'a pas de montant de participation défini.")
        Fee = self.env['eacta.student.fee']
        fee_type = self.env.ref('eacta_school.fee_type_activities', raise_if_not_found=False)
        if not fee_type:
            fee_type = self.env['eacta.fee.type'].search([('name', 'ilike', 'Activité')], limit=1)
        if not fee_type:
            fee_type = self.env['eacta.fee.type'].create({
                'name': 'Sorties & Événements',
                'sequence': 10,
                'default_amount': self.fee_amount,
            })
        created_fees = []
        for reg in self.registration_ids.filtered(lambda r: r.state != 'cancelled' and not r.fee_id):
            fee = Fee.create({
                'student_id': reg.student_id.id,
                'class_id': reg.class_id.id if reg.class_id else reg.student_id.current_class_id.id,
                'fee_type_id': fee_type.id,
                'description': f"Participation : {self.name}",
                'amount': self.fee_amount,
                'due_date': self.date or fields.Date.context_today(self),
            })
            reg.fee_id = fee.id
            created_fees.append(fee.id)
        if not created_fees:
            raise UserError("Tous les élèves inscrits ont déjà été facturés pour cet événement.")
        return {
            'name': f"Frais générés - {self.name}",
            'type': 'ir.actions.act_window',
            'res_model': 'eacta.student.fee',
            'view_mode': 'list,form',
            'domain': [('id', 'in', created_fees)],
        }

    # Compatibilité avec l'ancien bouton
    action_view_participants = action_view_registrations

    def action_print_attendance(self):
        return self.env.ref('eacta_event.action_report_event_attendance').report_action(self)

    def action_print_authorizations(self):
        regs = self.registration_ids.filtered(lambda r: r.state != 'cancelled')
        if not regs:
            raise UserError("Aucun élève inscrit.")
        return self.env.ref('eacta_event.action_report_event_authorization').report_action(regs)

    @api.model
    def _generate_demo_events(self):
        if not sample_data_step(self.env, 'events', 'eacta.school.event'):
            return
        self = self.with_context(tracking_disable=True, mail_create_nolog=True, mail_notrack=True)
        # Même ordre que « year desc, name » : nom croissant, puis année décroissante (tri stable)
        classes = sample_records(self.env, 'eacta.class').sorted('name').sorted(lambda c: c.year or '', reverse=True)
        if not classes:
            return
        today = fields.Date.context_today(self)
        demos = [
            ('Visite du Musée Mohammed VI', 'outing', 12, 'Rabat', 40, 50.0, classes[:2], 'confirmed'),
            ('Tournoi inter-classes de football', 'sport', 20, "Terrain de l'école", 0, 0.0, classes[:4], 'confirmed'),
            ('Réunion parents-professeurs du 1er trimestre', 'meeting', 5, 'Salle polyvalente', 0, 0.0, classes, 'confirmed'),
            ('Cérémonie de fin d\'année', 'ceremony', 45, 'Amphithéâtre', 300, 0.0, classes, 'draft'),
            ('Atelier robotique', 'conference', -15, 'Laboratoire', 24, 30.0, classes[2:3], 'done'),
            ('Voyage culturel à Marrakech', 'trip', 32, 'Marrakech', 45, 1200.0, classes[:2], 'confirmed'),
            ('Semaine des sciences', 'cultural', 18, 'Laboratoire & CDI', 60, 0.0, classes[:4], 'confirmed'),
            ('Cross solidaire', 'sport', -30, 'Forêt de la Maâmora', 0, 20.0, classes[:4], 'done'),
            ('Conférence : bien utiliser Internet', 'conference', -8, 'Amphithéâtre', 80, 0.0, classes[2:4], 'done'),
            ('Sortie au Jardin d\'essais botaniques', 'outing', 9, 'Rabat', 30, 25.0, classes[3:4], 'confirmed'),
            ('Journée du théâtre', 'cultural', 25, 'Salle polyvalente', 0, 0.0, classes[:3], 'draft'),
            ('Réunion parents-professeurs du 2e trimestre', 'meeting', 70, 'Salle polyvalente', 0, 0.0, classes, 'draft'),
        ]
        for name, etype, offset, place, cap, fee, klasses, state in demos:
            start = datetime.combine(today + timedelta(days=offset), time(9, 0))
            event = self.create({
                'name': name, 'event_type': etype, 'date_start': start, 'date_end': start + timedelta(hours=5),
                'location': place, 'capacity': cap, 'fee_amount': fee, 'class_ids': [(6, 0, klasses.ids)],
                'registration_deadline': today + timedelta(days=max(offset - 3, 1)) if offset > 0 else False,
                'requires_authorization': etype in ('outing', 'trip', 'conference'),
            })
            if etype != 'meeting':
                event.action_register_classes()
            regs = event.registration_ids
            for i, reg in enumerate(regs):
                vals = {}
                if event.requires_authorization and i % 4:
                    vals['authorized'] = True
                if fee and i % 3:
                    vals['paid'] = True
                if state == 'done':
                    vals['state'] = 'attended' if i % 5 else 'absent'
                if vals:
                    reg.write(vals)
            event.state = state


class EactaSchoolEventRegistration(models.Model):
    _name = 'eacta.school.event.registration'
    _description = "Inscription à un événement"
    _order = 'event_id, class_id, student_id'
    _rec_name = 'student_id'

    event_id = fields.Many2one('eacta.school.event', string='Événement', required=True, ondelete='cascade',
                               index=True)
    student_id = fields.Many2one('eacta.student', string='Élève', required=True, ondelete='cascade', index=True)
    student_code = fields.Char(related='student_id.code', string='Matricule')
    class_id = fields.Many2one(related='student_id.current_class_id', string='Classe', store=True)
    parent_id = fields.Many2one('res.partner', string='Parent / tuteur', compute='_compute_parent_id', store=True,
                                readonly=False)
    event_date = fields.Datetime(related='event_id.date_start', string='Date', store=True)
    event_state = fields.Selection(related='event_id.state', string="État de l'événement")
    state = fields.Selection([
        ('registered', 'Inscrit'),
        ('attended', 'Présent'),
        ('absent', 'Absent'),
        ('cancelled', 'Annulé'),
    ], string='Statut', default='registered', required=True)
    authorized = fields.Boolean(string='Autorisation parentale')
    authorization_date = fields.Date(string="Reçue le")
    fee_id = fields.Many2one('eacta.student.fee', string='Frais facturé', ondelete='set null')
    fee_state = fields.Selection(related='fee_id.state', string='État des frais')
    paid = fields.Boolean(string='Payé', compute='_compute_paid', store=True, readonly=False)
    amount = fields.Monetary(related='event_id.fee_amount', string='Montant')
    currency_id = fields.Many2one(related='event_id.currency_id')
    company_id = fields.Many2one(related='event_id.company_id', string='Établissement', store=True, readonly=True)
    note = fields.Char(string='Remarque')

    _sql_constraints = [
        ('event_student_unique', 'UNIQUE(event_id, student_id)', "Cet élève est déjà inscrit à cet événement."),
    ]

    @api.depends('fee_id.state')
    def _compute_paid(self):
        for reg in self:
            if reg.fee_id and reg.fee_id.state == 'paid':
                reg.paid = True

    @api.depends('student_id')
    def _compute_parent_id(self):
        for reg in self:
            if not reg.parent_id:
                reg.parent_id = reg.student_id.parent_ids[:1]

    @api.onchange('authorized')
    def _onchange_authorized(self):
        if self.authorized and not self.authorization_date:
            self.authorization_date = fields.Date.context_today(self)

    @api.constrains('event_id', 'state')
    def _check_capacity(self):
        for event in self.event_id:
            active = event.registration_ids.filtered(lambda r: r.state != 'cancelled')
            if event.capacity and len(active) > event.capacity:
                raise ValidationError(f"« {event.name} » est complet ({event.capacity} places).")

    def write(self, vals):
        if vals.get('authorized') and 'authorization_date' not in vals:
            vals['authorization_date'] = fields.Date.context_today(self)
        return super().write(vals)

    def action_mark_attended(self):
        self.write({'state': 'attended'})

    def action_mark_absent(self):
        self.write({'state': 'absent'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_toggle_authorized(self):
        for reg in self:
            reg.authorized = not reg.authorized

    def action_toggle_paid(self):
        for reg in self:
            reg.paid = not reg.paid
