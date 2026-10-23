from odoo import api, fields, models
from odoo.exceptions import ValidationError

VISIT_REASONS = [
    ('headache', 'Maux de tête'),
    ('stomach', 'Maux de ventre / nausées'),
    ('fever', 'Fièvre'),
    ('injury', 'Blessure / chute'),
    ('allergy', 'Réaction allergique'),
    ('asthma', 'Crise d\'asthme / respiratoire'),
    ('fatigue', 'Fatigue / malaise'),
    ('other', 'Autre'),
]

VISIT_OUTCOMES = [
    ('back_to_class', 'Retour en classe'),
    ('rest', 'Repos à l\'infirmerie'),
    ('parents_called', 'Parents appelés'),
    ('sent_home', 'Rentré à la maison'),
    ('hospital', 'Orienté vers un médecin / hôpital'),
]


class EactaInfirmaryVisit(models.Model):
    _name = 'eacta.infirmary.visit'
    _description = "Passage à l'infirmerie"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'visit_datetime desc, id desc'

    name = fields.Char(string='Référence', readonly=True, copy=False, default='/', index=True)
    student_id = fields.Many2one('eacta.student', string='Élève', required=True, index=True, tracking=True)
    student_image = fields.Image(related='student_id.image_128', string='Photo')
    class_id = fields.Many2one('eacta.class', string='Classe', compute='_compute_class_id', store=True,
                               readonly=False, index=True)
    visit_datetime = fields.Datetime(string='Arrivée', required=True, default=fields.Datetime.now, index=True)
    reason = fields.Selection(VISIT_REASONS, string='Motif', required=True, tracking=True)
    symptoms = fields.Text(string='Symptômes / observations')
    temperature = fields.Float(string='Température (°C)', digits=(3, 1))
    treatment = fields.Text(string='Soins apportés')
    medication_given = fields.Char(string='Médicament administré',
                                   help="Uniquement avec l'autorisation écrite des parents (PAI).")
    outcome = fields.Selection(VISIT_OUTCOMES, string='Suite donnée', default='back_to_class', required=True,
                               tracking=True)
    duration_minutes = fields.Integer(string='Durée (min)', default=15)
    nurse_id = fields.Many2one('res.users', string='Infirmier(ère)', default=lambda self: self.env.user,
                               readonly=True)
    parent_notified = fields.Boolean(string='Parents prévenus', copy=False, tracking=True)
    follow_up = fields.Boolean(string='Suivi nécessaire')
    allergies = fields.Text(related='student_id.allergies', string='Allergies connues')
    medical_notes = fields.Text(related='student_id.medical_notes', string='Suivi médical / PAI')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)

    @api.depends('student_id')
    def _compute_class_id(self):
        for visit in self:
            if not visit.class_id:
                visit.class_id = visit.student_id.current_class_id

    @api.constrains('temperature')
    def _check_temperature(self):
        for visit in self:
            if visit.temperature and not 30.0 <= visit.temperature <= 45.0:
                raise ValidationError("La température saisie doit être comprise entre 30 et 45 °C.")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code('eacta.infirmary.visit') or '/'
        return super().create(vals_list)

    def action_notify_parents(self):
        Channel = self.env['eacta.notification.channel']
        for visit in self:
            notified = self.env['res.partner']
            for parent in visit.student_id.parent_ids.filtered('email'):
                if Channel.send_notification('email', parent, 'eacta_school.email_template_infirmary_visit',
                                             visit._name, visit.id):
                    notified |= parent
            if notified:
                visit.parent_notified = True
                visit.message_post(body=f"Parents prévenus par email : {', '.join(notified.mapped('name'))}.")
        return True


class EactaVaccination(models.Model):
    _name = 'eacta.vaccination'
    _description = 'Vaccination'
    _order = 'date desc, id desc'

    student_id = fields.Many2one('eacta.student', string='Élève', required=True, ondelete='cascade', index=True)
    vaccine = fields.Char(string='Vaccin', required=True, help="ex : ROR, DTCP, Hépatite B")
    dose = fields.Char(string='Dose / rappel', help="ex : 1re dose, rappel 6 ans")
    date = fields.Date(string='Date', required=True)
    next_due_date = fields.Date(string='Prochain rappel')
    note = fields.Char(string='Remarque')


class EactaMedicalCertificate(models.Model):
    _name = 'eacta.medical.certificate'
    _description = 'Certificat médical'
    _order = 'date_from desc, id desc'

    student_id = fields.Many2one('eacta.student', string='Élève', required=True, ondelete='cascade', index=True)
    certificate_type = fields.Selection([
        ('sport_aptitude', 'Aptitude au sport'),
        ('sport_exemption', "Dispense d'EPS"),
        ('illness', 'Arrêt maladie'),
        ('other', 'Autre'),
    ], string='Type', required=True, default='sport_exemption')
    date_from = fields.Date(string='Du', required=True, default=fields.Date.context_today)
    date_to = fields.Date(string='Au')
    doctor_name = fields.Char(string='Médecin')
    attachment = fields.Binary(string='Certificat', attachment=True)
    attachment_filename = fields.Char(string='Nom du fichier')
    is_valid = fields.Boolean(string='En cours', compute='_compute_is_valid')
    note = fields.Char(string='Remarque')

    @api.depends('date_from', 'date_to')
    def _compute_is_valid(self):
        today = fields.Date.context_today(self)
        for cert in self:
            cert.is_valid = bool(cert.date_from and cert.date_from <= today
                                 and (not cert.date_to or cert.date_to >= today))

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for cert in self:
            if cert.date_to and cert.date_from and cert.date_to < cert.date_from:
                raise ValidationError("La date de fin du certificat doit être postérieure à sa date de début.")


class EactaStudentHealth(models.Model):
    _inherit = 'eacta.student'

    infirmary_visit_ids = fields.One2many('eacta.infirmary.visit', 'student_id', string="Passages à l'infirmerie",
                                          groups="eacta_school.group_eacta_school_nurse,eacta_school.group_eacta_school_manager")
    vaccination_ids = fields.One2many('eacta.vaccination', 'student_id', string='Vaccinations',
                                      groups="eacta_school.group_eacta_school_nurse,eacta_school.group_eacta_school_manager")
    medical_certificate_ids = fields.One2many('eacta.medical.certificate', 'student_id',
                                              string='Certificats médicaux')
    infirmary_visit_count = fields.Integer(string='Infirmerie', compute='_compute_health_stats',
                                           groups="eacta_school.group_eacta_school_nurse,eacta_school.group_eacta_school_manager")
    sport_exempted = fields.Boolean(string="Dispensé d'EPS", compute='_compute_sport_exempted',
                                    help="Un certificat de dispense d'EPS est en cours de validité.")

    def _compute_health_stats(self):
        for student in self:
            student.infirmary_visit_count = len(student.infirmary_visit_ids)

    @api.depends('medical_certificate_ids.date_from', 'medical_certificate_ids.date_to',
                 'medical_certificate_ids.certificate_type')
    def _compute_sport_exempted(self):
        for student in self:
            student.sport_exempted = any(
                cert.certificate_type == 'sport_exemption' and cert.is_valid
                for cert in student.sudo().medical_certificate_ids)

    def action_view_infirmary_visits(self):
        self.ensure_one()
        return {
            'name': f"Infirmerie - {self.name}",
            'type': 'ir.actions.act_window',
            'res_model': 'eacta.infirmary.visit',
            'view_mode': 'list,form',
            'domain': [('student_id', '=', self.id)],
            'context': {'default_student_id': self.id},
        }
