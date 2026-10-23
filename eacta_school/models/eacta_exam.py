import random
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError
from .sample_data import sample_data_step

EXAM_TYPES = [
    ('quiz', 'Contrôle continu'),
    ('homework', 'Devoir'),
    ('oral', 'Oral'),
    ('practical', 'Travaux pratiques'),
    ('midterm', 'Examen partiel'),
    ('final', 'Examen final'),
]


class EactaExam(models.Model):
    _name = 'eacta.exam'
    _description = 'Examen'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(string="Nom de l'examen", required=True, tracking=True)
    course_id = fields.Many2one('eacta.course', string="Matière", required=True, tracking=True)
    teacher_id = fields.Many2one(related='course_id.teacher_id', store=True, string='Enseignant')
    date = fields.Date(string="Date de l'examen", required=True, tracking=True,
                       default=fields.Date.context_today)
    exam_type = fields.Selection(EXAM_TYPES, string="Type", default='quiz', required=True, tracking=True)
    state = fields.Selection([
        ('draft', 'Planifié'),
        ('grading', 'Correction'),
        ('done', 'Clôturé'),
        ('cancel', 'Annulé'),
    ], string='État', default='draft', required=True, tracking=True)
    duration = fields.Float(string='Durée (h)', default=1.0)
    room = fields.Char(string='Salle')
    description = fields.Text(string='Consignes')
    term_id = fields.Many2one(
        'eacta.term', string='Trimestre / Semestre', compute='_compute_term_id',
        store=True, readonly=False, tracking=True, index=True)
    academic_year_id = fields.Many2one(
        'eacta.academic.year', string='Année académique', compute='_compute_academic_year_id',
        store=True, readonly=False, index=True)

    @property
    def year_id(self):
        return self.academic_year_id
    class_ids = fields.Many2many(
        'eacta.class', 'eacta_exam_class_rel', 'exam_id', 'class_ids', string="Classes",
        compute='_compute_class_ids', store=True, readonly=False)
    color = fields.Integer(string='Couleur')

    @api.depends('date')
    def _compute_term_id(self):
        for exam in self:
            if exam.date:
                term = self.env['eacta.term'].search([
                    ('date_start', '<=', exam.date),
                    ('date_end', '>=', exam.date),
                ], limit=1)
                if term:
                    exam.term_id = term
            elif not exam.term_id:
                exam.term_id = False

    @api.depends('term_id', 'term_id.academic_year_id', 'date')
    def _compute_academic_year_id(self):
        for exam in self:
            if exam.term_id and exam.term_id.academic_year_id:
                exam.academic_year_id = exam.term_id.academic_year_id
            elif exam.date:
                year = self.env['eacta.academic.year'].search([
                    ('date_start', '<=', exam.date),
                    ('date_end', '>=', exam.date),
                ], limit=1)
                exam.academic_year_id = year or False
            elif not exam.academic_year_id:
                exam.academic_year_id = False

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

    grade_ids = fields.One2many('eacta.course.grade', 'exam_id', string='Notes')
    grade_count = fields.Integer(string='Copies', compute='_compute_stats', store=True)
    graded_count = fields.Integer(string='Copies notées', compute='_compute_stats', store=True)
    average = fields.Float(string='Moyenne', compute='_compute_stats', store=True, digits=(4, 2), aggregator='avg')
    max_grade = fields.Float(string='Meilleure note', compute='_compute_stats', store=True, digits=(4, 2),
                             aggregator='max')
    min_grade = fields.Float(string='Note la plus basse', compute='_compute_stats', store=True, digits=(4, 2),
                             aggregator='min')
    success_rate = fields.Float(string='Taux de réussite (%)', compute='_compute_stats', store=True,
                                digits=(5, 1), aggregator='avg')
    progress = fields.Float(string='Avancement correction (%)', compute='_compute_stats', store=True)

    @api.depends('course_id')
    def _compute_class_ids(self):
        for exam in self:
            if exam.course_id and not exam.class_ids:
                exam.class_ids = exam.course_id.class_ids

    @api.depends('grade_ids.grade', 'grade_ids.status')
    def _compute_stats(self):
        for exam in self:
            graded = exam.grade_ids.filtered(lambda g: g.status == 'graded')
            values = graded.mapped('grade')
            relevant = exam.grade_ids.filtered(lambda g: g.status != 'exempt')
            exam.grade_count = len(exam.grade_ids)
            exam.graded_count = len(graded)
            exam.average = round(sum(values) / len(values), 2) if values else 0.0
            exam.max_grade = max(values) if values else 0.0
            exam.min_grade = min(values) if values else 0.0
            exam.success_rate = round(100.0 * len([v for v in values if v >= 10]) / len(values), 1) if values else 0.0
            done = relevant.filtered(lambda g: g.status in ('graded', 'absent'))
            exam.progress = round(100.0 * len(done) / len(relevant), 1) if relevant else 0.0

    def _get_expected_students(self):
        self.ensure_one()
        students = self.class_ids.student_ids
        if self.course_id.student_ids:
            # Restreindre aux élèves inscrits au cours lorsque des inscriptions existent
            enrolled = students & self.course_id.student_ids
            students = enrolled or students
        return students.filtered(lambda s: s.state in ('draft', 'enrolled'))

    def action_generate_grade_sheet(self):
        """Crée une ligne de note « À noter » pour chaque élève attendu."""
        Grade = self.env['eacta.course.grade']
        for exam in self:
            if not exam.class_ids:
                raise UserError(f"Veuillez sélectionner au moins une classe pour l'examen « {exam.name} ».")
            existing = exam.grade_ids.mapped('student_id')
            vals_list = []
            for student in exam._get_expected_students() - existing:
                student_class = (student.class_ids & exam.class_ids)[:1]
                vals_list.append({
                    'exam_id': exam.id,
                    'student_id': student.id,
                    'class_id': student_class.id,
                    'status': 'pending',
                    'grade': 0.0,
                })
            Grade.create(vals_list)
            if exam.state == 'draft':
                exam.state = 'grading'
        return self.action_open_grade_sheet() if len(self) == 1 else True

    def action_open_grade_sheet(self):
        self.ensure_one()
        return {
            'name': f"Saisie des notes - {self.name}",
            'type': 'ir.actions.act_window',
            'res_model': 'eacta.course.grade',
            'view_mode': 'list,form',
            'views': [(self.env.ref('eacta_school.view_course_grade_entry_list').id, 'list'), (False, 'form')],
            'domain': [('exam_id', '=', self.id)],
            'context': {'default_exam_id': self.id, 'create': True},
        }

    def action_start_grading(self):
        self.write({'state': 'grading'})

    def action_done(self):
        for exam in self:
            pending = exam.grade_ids.filtered(lambda g: g.status == 'pending')
            if pending:
                raise UserError(
                    f"Impossible de clôturer « {exam.name} » : {len(pending)} copie(s) restent à noter.")
        self.write({'state': 'done'})

    def action_cancel(self):
        self.write({'state': 'cancel'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})

    def action_submit_grades(self):
        """Soumet toutes les notes en brouillon de cet examen."""
        for exam in self:
            draft_grades = exam.grade_ids.filtered(lambda g: g.state == 'draft')
            draft_grades.action_submit()

    def action_validate_grades(self):
        """Valide toutes les notes soumises ou brouillon de cet examen."""
        for exam in self:
            grades = exam.grade_ids.filtered(lambda g: g.state in ('draft', 'submitted'))
            grades.action_validate()

    def action_publish_grades(self):
        """Publie toutes les notes validées de cet examen."""
        for exam in self:
            grades = exam.grade_ids.filtered(lambda g: g.state == 'validated')
            grades.action_publish()


    # ------------------------------------------------------------------
    # Données de démonstration
    # ------------------------------------------------------------------
    @api.model
    def _eacta_generate_demo_results(self):
        """Lie cours et classes de démo, puis génère examens et notes (déterministe)."""
        if not sample_data_step(self.env, 'results', 'eacta.exam'):
            return
        self = self.with_context(tracking_disable=True, mail_create_nolog=True, mail_notrack=True)
        rng = random.Random(2026)
        ref = lambda xmlid: self.env.ref(f'eacta_school.{xmlid}', raise_if_not_found=False)
        teachers = [t for t in (ref('demo_teacher_amina'), ref('demo_teacher_youssef'), ref('demo_teacher_sara')) if t]
        courses = {code: ref(f'course_{code}') for code in
                   ('math', 'french', 'science', 'history', 'english', 'geography', 'art')}
        courses = {code: course for code, course in courses.items() if course}
        if not courses:
            return
        for i, course in enumerate(courses.values()):
            if teachers and not course.teacher_id:
                course.teacher_id = teachers[i % len(teachers)]
        coefficients = {'math': 4, 'french': 3, 'science': 3, 'english': 2, 'history': 2, 'geography': 2, 'art': 1}
        for code, course in courses.items():
            course.coefficient = coefficients.get(code, 1)

        program = {
            'primary': ['math', 'french', 'science', 'english', 'art'],
            'secondary': ['math', 'french', 'science', 'english', 'history', 'geography'],
        }
        classes = self.env['eacta.class'].search([('id', 'in', [
            c.id for c in (ref(x) for x in ('class_1a_2023', 'class_1b_2023', 'class_2a_2023', 'class_2b_2023',
                                            'class_3a_2024', 'class_3b_2024', 'class_4a_2024', 'class_4b_2024',
                                            'class_5a_2026', 'class_5b_2026', 'class_6a_2026',
                                            'class_6b_2026')) if c
        ])])
        today = fields.Date.context_today(self)
        for n, klass in enumerate(classes):
            y_str = (klass.year or '').split('-')[0]
            try:
                year = int(y_str)
            except Exception:
                year = 2023
            klass.write({
                'course_ids': [(6, 0, [courses[c].id for c in program.get(klass.level, []) if c in courses])],
                'teacher_id': teachers[n % len(teachers)].id if teachers else False,
                'start_date': fields.Date.to_date(f'{year}-09-01'),
                'end_date': fields.Date.to_date(f'{year + 1}-06-30'),
            })
            klass.action_sync_courses_to_students()
            klass.student_ids.write({'state': 'enrolled'})
            # Niveau de chaque élève : stable d'un examen à l'autre
            skill = {s.id: rng.gauss(12, 2.6) for s in klass.student_ids}
            sessions = [('Contrôle continu 1', 'quiz', f'{year}-10-20'),
                        ('Devoir surveillé', 'homework', f'{year}-12-12'),
                        ('Examen final', 'final', f'{year + 1}-05-28')]
            for course in klass.course_ids:
                difficulty = rng.uniform(-1.5, 1.2)
                for label, exam_type, date in sessions:
                    exam_date = fields.Date.to_date(date)
                    exam = self.create({
                        'name': f'{label} - {course.name}',
                        'course_id': course.id,
                        'class_ids': [(6, 0, klass.ids)],
                        'exam_type': exam_type,
                        'date': exam_date,
                        'state': 'done' if exam_date <= today else 'draft',
                    })
                    if exam_date > today:
                        continue  # examen à venir : planifié, sans notes
                    vals_list = []
                    for student in klass.student_ids:
                        if rng.random() < 0.03:
                            vals_list.append({'exam_id': exam.id, 'student_id': student.id,
                                              'class_id': klass.id, 'status': 'absent', 'grade': 0.0})
                            continue
                        grade = skill[student.id] + difficulty + rng.gauss(0, 1.8)
                        vals_list.append({'exam_id': exam.id, 'student_id': student.id, 'class_id': klass.id,
                                          'status': 'graded', 'grade': round(min(20.0, max(0.0, grade)) * 4) / 4})
                    self.env['eacta.course.grade'].create(vals_list)

        # Quelques examens à venir pour le tableau de bord
        latest = classes.sorted('year', reverse=True)[:2]
        for offset, klass in enumerate(latest, start=1):
            for course in klass.course_ids[:3]:
                self.create({
                    'name': f'Contrôle continu 2 - {course.name}',
                    'course_id': course.id,
                    'class_ids': [(6, 0, klass.ids)],
                    'exam_type': 'quiz',
                    'date': today + timedelta(days=offset * 3 + len(course.name) % 9),
                    'room': f'Salle {100 + offset}',
                })
        # Quelques pré-inscriptions
        for student in classes[:1].student_ids[:4]:
            student.state = 'draft'
