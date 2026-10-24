import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from ..models.eacta_course_grade import APPRECIATIONS, appreciation_for

_logger = logging.getLogger(__name__)


class EactaGradeSheetWizard(models.TransientModel):
    _name = 'eacta.grade.sheet.wizard'
    _description = 'Grille de saisie rapide des notes'

    academic_year_id = fields.Many2one(
        'eacta.academic.year', string='Année académique',
        default=lambda self: self.env['eacta.academic.year'].get_current_year())
    term_id = fields.Many2one(
        'eacta.term', string='Trimestre / Semestre',
        domain="[('academic_year_id', '=', academic_year_id)]")
    class_id = fields.Many2one('eacta.class', string='Classe', required=True)
    course_id = fields.Many2one('eacta.course', string='Matière', required=True)

    exam_id = fields.Many2one(
        'eacta.exam', string='Examen existant',
        domain="[('course_id', '=', course_id), ('class_ids', 'in', [class_id])]")
    create_new_exam = fields.Boolean(string='Créer une nouvelle évaluation', default=False)
    new_exam_name = fields.Char(string="Nom de l'évaluation", default="Évaluation continue")
    exam_type = fields.Selection([
        ('quiz', 'Contrôle continu'),
        ('homework', 'Devoir surveillé'),
        ('oral', 'Oral'),
        ('practical', 'Travaux pratiques'),
        ('midterm', 'Examen partiel'),
        ('final', 'Examen final'),
    ], string="Type d'épreuve", default='quiz', required=True)
    exam_date = fields.Date(string="Date de l'évaluation", default=fields.Date.context_today, required=True)

    line_ids = fields.One2many('eacta.grade.sheet.wizard.line', 'wizard_id', string='Élèves & Notes')

    # Statistiques temps réel
    student_count = fields.Integer(string='Effectif', compute='_compute_live_stats')
    graded_count = fields.Integer(string='Copies notées', compute='_compute_live_stats')
    absent_count = fields.Integer(string='Absents', compute='_compute_live_stats')
    exempt_count = fields.Integer(string='Dispensés', compute='_compute_live_stats')
    pending_count = fields.Integer(string='En attente', compute='_compute_live_stats')
    class_average = fields.Float(string='Moyenne (/20)', compute='_compute_live_stats', digits=(4, 2))
    max_grade = fields.Float(string='Note Max', compute='_compute_live_stats', digits=(4, 2))
    min_grade = fields.Float(string='Note Min', compute='_compute_live_stats', digits=(4, 2))
    success_rate = fields.Float(string='Taux de réussite (≥10)', compute='_compute_live_stats', digits=(5, 1))

    @api.depends('line_ids.grade', 'line_ids.status')
    def _compute_live_stats(self):
        for wiz in self:
            lines = wiz.line_ids
            wiz.student_count = len(lines)
            wiz.absent_count = len(lines.filtered(lambda l: l.status == 'absent'))
            wiz.exempt_count = len(lines.filtered(lambda l: l.status == 'exempt'))
            wiz.pending_count = len(lines.filtered(lambda l: l.status == 'pending'))
            graded_lines = lines.filtered(lambda l: l.status == 'graded')
            wiz.graded_count = len(graded_lines)

            grades = graded_lines.mapped('grade')
            if grades:
                wiz.class_average = round(sum(grades) / len(grades), 2)
                wiz.max_grade = max(grades)
                wiz.min_grade = min(grades)
                wiz.success_rate = round(100.0 * len([g for g in grades if g >= 10.0]) / len(grades), 1)
            else:
                wiz.class_average = 0.0
                wiz.max_grade = 0.0
                wiz.min_grade = 0.0
                wiz.success_rate = 0.0

    @api.onchange('class_id')
    def _onchange_class_id(self):
        if self.class_id:
            # Suggérer les cours de cette classe
            if self.class_id.course_ids and self.course_id not in self.class_id.course_ids:
                self.course_id = self.class_id.course_ids[:1]
            if self.class_id.academic_year_id:
                self.academic_year_id = self.class_id.academic_year_id
            self._reload_student_lines()

    @api.onchange('course_id', 'exam_id')
    def _onchange_course_or_exam(self):
        if self.exam_id:
            self.create_new_exam = False
            self.new_exam_name = self.exam_id.name
            self.exam_type = self.exam_id.exam_type
            self.exam_date = self.exam_id.date or fields.Date.context_today(self)
            if self.exam_id.term_id:
                self.term_id = self.exam_id.term_id
        self._reload_student_lines()

    def _reload_student_lines(self):
        if not self.class_id:
            self.line_ids = [(5, 0, 0)]
            return

        students = self.class_id.student_ids.filtered(lambda s: s.state in ('draft', 'enrolled'))
        existing_grades_by_student = {}

        if self.exam_id:
            grades = self.env['eacta.course.grade'].search([('exam_id', '=', self.exam_id.id)])
            for g in grades:
                existing_grades_by_student[g.student_id.id] = g

        new_lines = []
        for s in students.sorted('name'):
            grade_rec = existing_grades_by_student.get(s.id)
            if grade_rec:
                new_lines.append((0, 0, {
                    'student_id': s.id,
                    'status': grade_rec.status,
                    'grade': grade_rec.grade,
                    'appreciation': grade_rec.appreciation,
                    'comment': grade_rec.comment or '',
                    'existing_grade_id': grade_rec.id,
                }))
            else:
                new_lines.append((0, 0, {
                    'student_id': s.id,
                    'status': 'graded',
                    'grade': 0.0,
                    'appreciation': False,
                    'comment': '',
                    'existing_grade_id': False,
                }))

        self.line_ids = [(5, 0, 0)] + new_lines

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_model = self.env.context.get('active_model')
        active_id = self.env.context.get('active_id')

        if active_model == 'eacta.exam' and active_id:
            exam = self.env['eacta.exam'].browse(active_id)
            res['exam_id'] = exam.id
            res['course_id'] = exam.course_id.id
            res['class_id'] = exam.class_ids[:1].id if exam.class_ids else False
            res['new_exam_name'] = exam.name
            res['exam_type'] = exam.exam_type
            res['exam_date'] = exam.date
            res['academic_year_id'] = exam.academic_year_id.id if exam.academic_year_id else False
            res['term_id'] = exam.term_id.id if exam.term_id else False

            # Précharger les lignes de notes existantes
            lines = []
            expected_students = exam._get_expected_students()
            existing_grades = {g.student_id.id: g for g in exam.grade_ids}

            for s in expected_students.sorted('name'):
                grade_rec = existing_grades.get(s.id)
                if grade_rec:
                    lines.append((0, 0, {
                        'student_id': s.id,
                        'status': grade_rec.status,
                        'grade': grade_rec.grade,
                        'appreciation': grade_rec.appreciation,
                        'comment': grade_rec.comment or '',
                        'existing_grade_id': grade_rec.id,
                    }))
                else:
                    lines.append((0, 0, {
                        'student_id': s.id,
                        'status': 'graded',
                        'grade': 0.0,
                        'appreciation': False,
                        'comment': '',
                        'existing_grade_id': False,
                    }))
            res['line_ids'] = lines

        return res

    def action_load_students(self):
        """Bouton pour forcer le rafraîchissement des élèves."""
        self.ensure_one()
        self._reload_student_lines()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'eacta.grade.sheet.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _get_or_create_exam(self):
        self.ensure_one()
        Exam = self.env['eacta.exam']
        if self.exam_id:
            exam = self.exam_id
            if self.class_id not in exam.class_ids:
                exam.class_ids = [(4, self.class_id.id)]
            return exam

        exam_name = self.new_exam_name or f"{self.course_id.name} - Évaluation du {self.exam_date}"
        exam_vals = {
            'name': exam_name,
            'course_id': self.course_id.id,
            'class_ids': [(4, self.class_id.id)],
            'date': self.exam_date,
            'exam_type': self.exam_type,
            'state': 'grading',
            'academic_year_id': self.academic_year_id.id if self.academic_year_id else False,
            'term_id': self.term_id.id if self.term_id else False,
        }
        return Exam.create(exam_vals)

    def action_save_grades(self):
        """Enregistre toutes les notes saisies dans eacta.course.grade."""
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_("Aucun élève dans la grille de saisie."))

        exam = self._get_or_create_exam()
        Grade = self.env['eacta.course.grade']

        for line in self.line_ids:
            if not (0.0 <= line.grade <= 20.0):
                raise ValidationError(_("La note de %s (%s) doit être comprise entre 0 et 20.") % (line.student_id.name, line.grade))

            grade_vals = {
                'exam_id': exam.id,
                'student_id': line.student_id.id,
                'class_id': self.class_id.id,
                'status': line.status,
                'grade': line.grade if line.status == 'graded' else 0.0,
                'comment': line.comment or False,
            }

            if line.existing_grade_id:
                line.existing_grade_id.write(grade_vals)
            else:
                existing = Grade.search([('exam_id', '=', exam.id), ('student_id', '=', line.student_id.id)], limit=1)
                if existing:
                    existing.write(grade_vals)
                    line.existing_grade_id = existing.id
                else:
                    new_grade = Grade.create(grade_vals)
                    line.existing_grade_id = new_grade.id

        if exam.state == 'draft':
            exam.state = 'grading'

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Grille de notes enregistrée"),
                'message': _("Les notes pour « %s » ont été enregistrées avec succès (%s copies).") % (exam.name, len(self.line_ids)),
                'type': 'success',
                'sticky': False,
            }
        }

    def action_submit_grades(self):
        """Enregistre puis soumet l'ensemble des notes de l'examen."""
        self.action_save_grades()
        exam = self._get_or_create_exam()
        exam.action_submit_grades()
        return {
            'name': exam.name,
            'type': 'ir.actions.act_window',
            'res_model': 'eacta.exam',
            'res_id': exam.id,
            'view_mode': 'form',
            'target': 'current',
        }


class EactaGradeSheetWizardLine(models.TransientModel):
    _name = 'eacta.grade.sheet.wizard.line'
    _description = 'Ligne de saisie rapide de note'
    _order = 'student_name, id'

    wizard_id = fields.Many2one('eacta.grade.sheet.wizard', string='Assistant', ondelete='cascade', required=True)
    student_id = fields.Many2one('eacta.student', string='Élève', required=True)
    student_code = fields.Char(related='student_id.code', string='Matricule', readonly=True)
    student_name = fields.Char(related='student_id.name', string='Nom', readonly=True, store=True)

    status = fields.Selection([
        ('graded', 'Noté'),
        ('absent', 'Absent'),
        ('exempt', 'Dispensé'),
        ('pending', 'À noter'),
    ], string='Statut', default='graded', required=True)

    grade = fields.Float(string='Note / 20', digits=(4, 2), default=0.0)
    appreciation = fields.Selection(APPRECIATIONS, string='Appréciation', compute='_compute_appreciation', store=True)
    comment = fields.Char(string='Observation / Remarque')
    existing_grade_id = fields.Many2one('eacta.course.grade', string='Note existante')

    @api.depends('grade', 'status')
    def _compute_appreciation(self):
        for line in self:
            if line.status == 'graded' and line.grade is not None:
                line.appreciation = appreciation_for(line.grade)
            else:
                line.appreciation = False

    @api.onchange('grade')
    def _onchange_grade(self):
        if self.grade and self.status == 'pending':
            self.status = 'graded'
