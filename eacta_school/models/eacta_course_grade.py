from odoo import api, fields, models
from odoo.exceptions import ValidationError

MAX_GRADE = 20.0

APPRECIATIONS = [
    ('insufficient', 'Insuffisant'),
    ('fair', 'Passable'),
    ('quite_good', 'Assez bien'),
    ('good', 'Bien'),
    ('very_good', 'Très bien'),
    ('excellent', 'Excellent'),
]


def appreciation_for(grade):
    """Retourne la clé d'appréciation (barème marocain / français sur 20)."""
    if grade is None:
        return False
    if grade < 10:
        return 'insufficient'
    if grade < 12:
        return 'fair'
    if grade < 14:
        return 'quite_good'
    if grade < 16:
        return 'good'
    if grade < 18:
        return 'very_good'
    return 'excellent'


class CourseGrade(models.Model):
    _name = 'eacta.course.grade'
    _description = 'Note'
    _order = 'date desc, student_id'
    _rec_name = 'student_id'

    exam_id = fields.Many2one('eacta.exam', string="Examen", required=True, ondelete='cascade', index=True)
    student_id = fields.Many2one('eacta.student', string='Élève', required=True, ondelete='cascade', index=True)
    course_id = fields.Many2one(related='exam_id.course_id', store=True, string='Matière', index=True)
    class_id = fields.Many2one('eacta.class', string='Classe', compute='_compute_class_id', store=True,
                               readonly=False, index=True)
    year = fields.Char(related='class_id.year', store=True, string='Année')
    date = fields.Date(related='exam_id.date', store=True, string='Date')
    exam_type = fields.Selection(related='exam_id.exam_type', store=True)
    teacher_id = fields.Many2one(related='exam_id.teacher_id', store=True, string='Enseignant')
    coefficient = fields.Float(related='course_id.coefficient', store=True, string='Coeff.')
    status = fields.Selection([
        ('pending', 'À noter'),
        ('graded', 'Noté'),
        ('absent', 'Absent'),
        ('exempt', 'Dispensé'),
    ], string='Statut', default='graded', required=True)
    grade = fields.Float(string="Note", digits=(4, 2), aggregator='avg')
    appreciation = fields.Selection(APPRECIATIONS, string='Appréciation', compute='_compute_appreciation',
                                    store=True)
    is_passed = fields.Boolean(string='Validé', compute='_compute_appreciation', store=True)
    comment = fields.Char(string='Observation')

    _sql_constraints = [
        ('student_exam_unique', 'UNIQUE(student_id, exam_id)', "Cet élève a déjà une note pour cet examen."),
    ]

    @api.depends('student_id', 'exam_id')
    def _compute_class_id(self):
        for record in self:
            if record.class_id and record.class_id in record.student_id.class_ids:
                continue
            record.class_id = record._guess_class()

    def _guess_class(self):
        self.ensure_one()
        student_classes = self.student_id.class_ids
        if not student_classes:
            return False
        exam = self.exam_id
        candidates = student_classes & exam.class_ids
        if not candidates and exam.date:
            candidates = student_classes.filtered(lambda c: c.year == str(exam.date.year))
        if not candidates:
            candidates = self.student_id.current_class_id
        return candidates[:1]

    @api.depends('grade', 'status')
    def _compute_appreciation(self):
        for record in self:
            graded = record.status == 'graded'
            record.appreciation = appreciation_for(record.grade) if graded else False
            record.is_passed = graded and record.grade >= 10

    @api.depends('student_id', 'exam_id')
    def _compute_display_name(self):
        for record in self:
            record.display_name = f"{record.student_id.name or ''} - {record.exam_id.name or ''}"

    @api.constrains('grade')
    def _check_grade_range(self):
        for record in self:
            if not (0.0 <= record.grade <= MAX_GRADE):
                raise ValidationError(f"La note doit être comprise entre 0 et {MAX_GRADE:g}.")

    @api.constrains('status', 'exam_id')
    def _check_exam_date_in_past(self):
        today = fields.Date.context_today(self)
        for record in self:
            if record.status == 'graded' and record.exam_id.date and record.exam_id.date > today:
                raise ValidationError(
                    f"L'examen « {record.exam_id.name} » n'a pas encore eu lieu : "
                    "impossible d'enregistrer une note.")

    @api.constrains('student_id', 'class_id')
    def _check_class_belongs_to_student(self):
        for record in self:
            if record.class_id and record.class_id not in record.student_id.class_ids:
                raise ValidationError(
                    f"La classe {record.class_id.display_name} ne fait pas partie des classes "
                    f"de l'élève {record.student_id.name}.")

    @api.onchange('grade')
    def _onchange_grade(self):
        if self.status == 'pending' and self.grade:
            self.status = 'graded'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('grade') and 'status' not in vals:
                vals['status'] = 'graded'
        return super().create(vals_list)

    def write(self, vals):
        if 'grade' in vals and 'status' not in vals:
            pending = self.filtered(lambda g: g.status == 'pending')
            if pending:
                super(CourseGrade, pending).write(dict(vals, status='graded'))
                others = self - pending
                return super(CourseGrade, others).write(vals) if others else True
        return super().write(vals)
