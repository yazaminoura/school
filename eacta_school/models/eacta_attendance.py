from odoo import api, fields, models


class EactaAttendance(models.Model):
    _name = 'eacta.attendance'
    _description = 'Assiduité & Absence'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(string='Référence', compute='_compute_name', store=True)
    student_id = fields.Many2one('eacta.student', string='Élève', required=True, tracking=True, index=True)
    student_image = fields.Image(related='student_id.image_128', string='Photo')
    student_code = fields.Char(related='student_id.code', string='Matricule')
    class_id = fields.Many2one('eacta.class', string='Classe', compute='_compute_class_id', store=True, readonly=False, tracking=True)
    date = fields.Date(string='Date', default=fields.Date.context_today, required=True, tracking=True, index=True)
    attendance_type = fields.Selection([
        ('absent', 'Absence'),
        ('late', 'Retard'),
        ('present', 'Présent'),
    ], string='Type', default='absent', required=True, tracking=True)
    session = fields.Selection([
        ('all_day', 'Journée entière'),
        ('morning', 'Matin'),
        ('afternoon', 'Après-midi'),
    ], string='Créneau', default='all_day', required=True)
    duration_hours = fields.Float(string='Durée (heures)', default=1.0)
    justified = fields.Boolean(string='Justifié(e)', default=False, tracking=True)
    reason = fields.Selection([
        ('illness', 'Maladie'),
        ('family', 'Raison familiale'),
        ('transport', 'Problème de transport'),
        ('appointment', 'Rendez-vous médical'),
        ('convocation', 'Convocation administrative'),
        ('other', 'Autre motif'),
    ], string='Motif')
    justification_note = fields.Text(string='Détail ou justificatif')
    company_id = fields.Many2one('res.company', string='Établissement', default=lambda self: self.env.company)

    @api.depends('student_id.name', 'attendance_type', 'date')
    def _compute_name(self):
        type_labels = dict(self._fields['attendance_type'].selection)
        for att in self:
            label = type_labels.get(att.attendance_type, 'Présence')
            date_str = fields.Date.to_string(att.date) if att.date else ''
            student_name = att.student_id.name or 'Élève'
            att.name = f"{label} - {student_name} ({date_str})"

    @api.depends('student_id', 'student_id.current_class_id')
    def _compute_class_id(self):
        for att in self:
            if not att.class_id and att.student_id:
                att.class_id = att.student_id.current_class_id

    def action_mark_justified(self):
        self.write({'justified': True})

    def action_mark_unjustified(self):
        self.write({'justified': False})
