from odoo import api, fields, models
from odoo.exceptions import UserError


class EactaAttendanceWizard(models.TransientModel):
    _name = 'eacta.attendance.wizard'
    _description = "Feuille d'appel rapide par classe"

    class_id = fields.Many2one('eacta.class', string='Classe', required=True)
    date = fields.Date(string='Date', default=fields.Date.context_today, required=True)
    session = fields.Selection([
        ('morning', 'Matin'),
        ('afternoon', 'Après-midi'),
        ('all_day', 'Journée entière'),
    ], string='Créneau', default='morning', required=True)
    
    line_ids = fields.One2many('eacta.attendance.wizard.line', 'wizard_id', string='Élèves')
    
    total_students = fields.Integer(string='Effectif', compute='_compute_counts')
    present_count = fields.Integer(string='Présents', compute='_compute_counts')
    absent_count = fields.Integer(string='Absents', compute='_compute_counts')
    late_count = fields.Integer(string='Retards', compute='_compute_counts')

    @api.depends('line_ids.attendance_type')
    def _compute_counts(self):
        for wiz in self:
            wiz.total_students = len(wiz.line_ids)
            wiz.present_count = len(wiz.line_ids.filtered(lambda l: l.attendance_type == 'present'))
            wiz.absent_count = len(wiz.line_ids.filtered(lambda l: l.attendance_type == 'absent'))
            wiz.late_count = len(wiz.line_ids.filtered(lambda l: l.attendance_type == 'late'))

    def _prepare_lines_for(self, class_id, date, session):
        klass = self.env['eacta.class'].browse(class_id)
        if not klass:
            return []
        Attendance = self.env['eacta.attendance']
        existing_records = Attendance.search([
            ('class_id', '=', klass.id),
            ('date', '=', date),
            ('session', '=', session),
        ])
        existing_by_student = {att.student_id.id: att for att in existing_records}

        lines = []
        students = klass.student_ids.filtered(lambda s: s.state in ('draft', 'enrolled'))
        for student in students.sorted('name'):
            att = existing_by_student.get(student.id)
            lines.append((0, 0, {
                'student_id': student.id,
                'student_code': student.code,
                'attendance_type': att.attendance_type if att else 'present',
                'justified': att.justified if att else False,
                'reason': att.reason if att else False,
                'note': att.justification_note if att else False,
            }))
        return lines

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        class_id = res.get('class_id') or self.env.context.get('default_class_id')
        date = res.get('date') or fields.Date.context_today(self)
        session = res.get('session') or 'morning'
        if class_id:
            res['class_id'] = class_id
            res['line_ids'] = self._prepare_lines_for(class_id, date, session)
        return res

    @api.onchange('class_id', 'date', 'session')
    def _onchange_class_id(self):
        if not self.class_id:
            self.line_ids = [(5, 0, 0)]
            return
        self.line_ids = [(5, 0, 0)] + self._prepare_lines_for(self.class_id.id, self.date, self.session)

    def action_mark_all_present(self):
        self.line_ids.write({'attendance_type': 'present', 'justified': False, 'reason': False})
        return {'type': 'ir.actions.do_nothing'}

    def action_mark_all_absent(self):
        self.line_ids.write({'attendance_type': 'absent'})
        return {'type': 'ir.actions.do_nothing'}

    def action_confirm(self):
        self.ensure_one()
        Attendance = self.env['eacta.attendance']
        
        # Existing records for this class/date/session
        existing_records = Attendance.search([
            ('class_id', '=', self.class_id.id),
            ('date', '=', self.date),
            ('session', '=', self.session),
        ])
        existing_by_student = {att.student_id.id: att for att in existing_records}

        created_count = 0
        updated_count = 0
        deleted_count = 0

        for line in self.line_ids:
            att = existing_by_student.get(line.student_id.id)
            if line.attendance_type in ('absent', 'late'):
                vals = {
                    'student_id': line.student_id.id,
                    'class_id': self.class_id.id,
                    'date': self.date,
                    'session': self.session,
                    'attendance_type': line.attendance_type,
                    'justified': line.justified,
                    'reason': line.reason if line.justified else False,
                    'justification_note': line.note,
                }
                if att:
                    att.write(vals)
                    updated_count += 1
                else:
                    Attendance.create(vals)
                    created_count += 1
            elif att:
                # Student is marked present, remove prior absence record
                att.unlink()
                deleted_count += 1

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': "Appel enregistré avec succès",
                'message': (
                    f"Classe {self.class_id.name} ({self.date}) : "
                    f"{self.present_count} présent(s), {self.absent_count} absent(s), {self.late_count} retard(s)."
                ),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }


class EactaAttendanceWizardLine(models.TransientModel):
    _name = 'eacta.attendance.wizard.line'
    _description = "Ligne de feuille d'appel"
    _order = 'student_id'

    wizard_id = fields.Many2one('eacta.attendance.wizard', required=True, ondelete='cascade')
    student_id = fields.Many2one('eacta.student', string='Élève', required=True)
    student_code = fields.Char(string='Matricule')
    attendance_type = fields.Selection([
        ('present', 'Présent'),
        ('absent', 'Absent'),
        ('late', 'Retard'),
    ], string='Statut', default='present', required=True)
    justified = fields.Boolean(string='Justifié')
    reason = fields.Selection([
        ('illness', 'Maladie'),
        ('family', 'Raison familiale'),
        ('transport', 'Problème de transport'),
        ('appointment', 'Rendez-vous médical'),
        ('convocation', 'Convocation administrative'),
        ('other', 'Autre motif'),
    ], string='Motif')
    note = fields.Char(string='Remarque')
