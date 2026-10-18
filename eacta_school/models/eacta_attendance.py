from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class EactaAttendance(models.Model):
    _name = 'eacta.attendance'
    _description = 'Assiduité & Absence'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(string='Référence', compute='_compute_name', store=True)
    student_id = fields.Many2one('eacta.student', string='Élève', required=True, tracking=True, index=True)
    student_image = fields.Image(related='student_id.image_128', string='Photo')
    student_code = fields.Char(related='student_id.code', string='Matricule')
    class_id = fields.Many2one('eacta.class', string='Classe', compute='_compute_class_id', store=True, readonly=False, tracking=True, index=True)
    academic_year_id = fields.Many2one('eacta.academic.year', string='Année académique', related='class_id.academic_year_id', store=True, index=True)
    date = fields.Date(string='Date', default=fields.Date.context_today, required=True, tracking=True, index=True)
    attendance_type = fields.Selection([
        ('absent', 'Absence'),
        ('late', 'Retard'),
        ('present', 'Présent'),
    ], string='Type', default='absent', required=True, tracking=True)

    @property
    def type(self):
        return self.attendance_type

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None):
        def _remap(term):
            if isinstance(term, (list, tuple)) and len(term) == 3 and term[0] == 'type':
                return ('attendance_type', term[1], term[2])
            return term
        remapped_domain = [_remap(term) for term in domain] if domain else domain
        return super()._search(remapped_domain, offset=offset, limit=limit, order=order)
    session = fields.Selection([
        ('all_day', 'Journée entière'),
        ('morning', 'Matin'),
        ('afternoon', 'Après-midi'),
    ], string='Créneau', default='all_day', required=True)
    slot_id = fields.Many2one('eacta.timetable.slot', string="Créneau d'emploi du temps", ondelete='set null')
    course_id = fields.Many2one('eacta.course', string='Matière', compute='_compute_course_id', store=True, readonly=False)
    duration_hours = fields.Float(string='Durée (heures)', default=1.0)
    justified = fields.Boolean(string='Justifié(e)', default=False, tracking=True)
    reason = fields.Selection([
        ('illness', 'Maladie'),
        ('family', 'Raison familiale'),
        ('transport', 'Problème de transport'),
        ('appointment', 'Rendez-vous médical'),
        ('convocation', 'Convocation administrative'),
        ('other', 'Autre motif'),
    ], string='Motif', tracking=True)
    justification_note = fields.Text(string='Détail ou motif', tracking=True)
    justification_attachment = fields.Binary(string='Pièce justificative', attachment=True)
    justification_filename = fields.Char(string='Nom de la pièce')
    justification_attachment_ids = fields.Many2many('ir.attachment', string='Pièces justificatives')
    justification_date = fields.Date(string='Date de justification', tracking=True)
    company_id = fields.Many2one('res.company', string='Établissement', default=lambda self: self.env.company)

    _sql_constraints = [
        ('student_date_session_type_unique', 'UNIQUE(student_id, date, session, attendance_type)',
         "Un enregistrement d'assiduité existe déjà pour cet élève à cette date, ce créneau et ce type !")
    ]

    @api.depends('slot_id.course_id')
    def _compute_course_id(self):
        for att in self:
            if att.slot_id and att.slot_id.course_id:
                att.course_id = att.slot_id.course_id

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

    @api.constrains('date')
    def _check_date_not_future(self):
        today = fields.Date.context_today(self)
        for att in self:
            if att.date and att.date > today:
                raise ValidationError("La date d'assiduité ne peut pas être dans le futur.")

    @api.constrains('student_id', 'date', 'session', 'attendance_type')
    def _check_unique_attendance(self):
        for att in self:
            dup = self.search([
                ('id', '!=', att.id),
                ('student_id', '=', att.student_id.id),
                ('date', '=', att.date),
                ('session', '=', att.session),
                ('attendance_type', '=', att.attendance_type),
            ], limit=1)
            if dup:
                raise ValidationError(
                    f"Un enregistrement d'assiduité existe déjà pour l'élève {att.student_id.name} "
                    f"le {att.date} ({att.session}, {att.attendance_type})."
                )

    @api.constrains('justified', 'reason')
    def _check_justified_reason(self):
        for att in self:
            if att.justified and not att.reason:
                raise ValidationError(
                    "Un motif est obligatoire lorsqu'une absence ou un retard est marqué(e) comme justifié(e)."
                )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'type' in vals and 'attendance_type' not in vals:
                vals['attendance_type'] = vals.pop('type')
            if vals.get('student_id') and vals.get('date') and vals.get('session') and vals.get('attendance_type'):
                dup = self.search([
                    ('student_id', '=', vals['student_id']),
                    ('date', '=', vals['date']),
                    ('session', '=', vals['session']),
                    ('attendance_type', '=', vals['attendance_type']),
                ], limit=1)
                if dup:
                    raise ValidationError(
                        "Un enregistrement d'assiduité existe déjà pour cet élève à cette date, ce créneau et ce type !"
                    )
        records = super().create(vals_list)
        records._check_and_create_absence_alert()
        return records

    def write(self, vals):
        if 'type' in vals and 'attendance_type' not in vals:
            vals['attendance_type'] = vals.pop('type')
        res = super().write(vals)
        if any(k in vals for k in ('attendance_type', 'justified', 'student_id', 'date')):
            self._check_and_create_absence_alert()
        return res

    def _check_and_create_absence_alert(self):
        ICP = self.env['ir.config_parameter'].sudo()
        threshold = int(ICP.get_param('eacta_school.unjustified_absence_threshold', 3))
        send_email = ICP.get_param('eacta_school.send_absence_parent_email', 'True') in ('True', '1', True)

        for att in self:
            if att.attendance_type == 'absent' and not att.justified and att.student_id and att.date:
                d_from = att.date.replace(day=1)
                next_month = (d_from.replace(day=28) + relativedelta(days=4)).replace(day=1)
                d_to = next_month - relativedelta(days=1)

                count = self.search_count([
                    ('student_id', '=', att.student_id.id),
                    ('attendance_type', '=', 'absent'),
                    ('justified', '=', False),
                    ('date', '>=', d_from),
                    ('date', '<=', d_to),
                ])

                if count >= threshold:
                    student = att.student_id
                    teacher = att.class_id.teacher_id or student.current_class_id.teacher_id

                    alert_msg = (
                        f"<p><strong>Alerte Assiduité :</strong> L'élève a accumulé "
                        f"<strong>{count} absences non justifiées</strong> au cours du mois ({att.date.strftime('%B %Y')}).</p>"
                    )
                    student.message_post(body=alert_msg, message_type='notification')

                    if teacher:
                        activity_type = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
                        existing_act = self.env['mail.activity'].search([
                            ('res_model', '=', 'eacta.student'),
                            ('res_id', '=', student.id),
                            ('user_id', '=', teacher.id),
                            ('summary', 'like', 'Alerte absences'),
                            ('date_deadline', '>=', d_from),
                        ], limit=1)
                        if not existing_act and activity_type:
                            self.env['mail.activity'].create({
                                'activity_type_id': activity_type.id,
                                'res_model_id': self.env['ir.model']._get_id('eacta.student'),
                                'res_id': student.id,
                                'user_id': teacher.id,
                                'summary': f"Alerte absences : {count} non justifiées pour {student.name}",
                                'note': f"L'élève {student.name} ({att.class_id.name or ''}) a dépassé le seuil d'absences non justifiées ({count} absences ce mois-ci).",
                                'date_deadline': fields.Date.today(),
                            })

                    if send_email and student.parent_ids:
                        for p in student.parent_ids.filtered('email'):
                            student.message_post(
                                body=f"Notification d'absence non justifiée envoyée au parent : {p.name} ({p.email}).",
                                partner_ids=[p.id],
                                subtype_xmlid='mail.mt_note'
                            )

    def action_mark_justified(self):
        """Marque l'absence ou le retard comme justifié(e)."""
        for att in self:
            vals = {
                'justified': True,
                'justification_date': fields.Date.context_today(self),
            }
            if not att.reason:
                vals['reason'] = 'other'
            att.write(vals)

    def action_mark_unjustified(self):
        """Réinitialise la justification de l'absence ou du retard."""
        self.write({
            'justified': False,
            'justification_date': False,
        })

