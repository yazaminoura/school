from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

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
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, student_id'
    _rec_name = 'student_id'

    exam_id = fields.Many2one('eacta.exam', string="Examen", required=True, ondelete='cascade', index=True)
    student_id = fields.Many2one('eacta.student', string='Élève', required=True, ondelete='cascade', index=True)
    course_id = fields.Many2one(related='exam_id.course_id', store=True, string='Matière', index=True)
    class_id = fields.Many2one('eacta.class', string='Classe', compute='_compute_class_id', store=True,
                               readonly=False, index=True)
    academic_year_id = fields.Many2one(
        'eacta.academic.year', string='Année académique', compute='_compute_academic_year_id',
        store=True, readonly=False, index=True)

    @property
    def year_id(self):
        return self.academic_year_id
    term_id = fields.Many2one('eacta.term', string='Trimestre', related='exam_id.term_id', store=True, index=True)
    year = fields.Char(related='academic_year_id.name', store=True, string='Année')
    date = fields.Date(related='exam_id.date', store=True, string='Date')
    exam_type = fields.Selection(related='exam_id.exam_type', store=True)
    teacher_id = fields.Many2one(related='exam_id.teacher_id', store=True, string='Enseignant')
    coefficient = fields.Float(related='course_id.coefficient', store=True, string='Coeff.')
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('submitted', 'Soumis'),
        ('validated', 'Validé'),
        ('published', 'Publié'),
    ], string='État', default='draft', required=True, tracking=True, index=True)
    status = fields.Selection([
        ('pending', 'À noter'),
        ('graded', 'Noté'),
        ('absent', 'Absent'),
        ('exempt', 'Dispensé'),
    ], string='Statut', default='graded', required=True, tracking=True)
    grade = fields.Float(string="Note", digits=(4, 2), aggregator='avg', tracking=True)
    is_justified = fields.Boolean(string="Absence justifiée", default=False, tracking=True)
    appreciation = fields.Selection(APPRECIATIONS, string='Appréciation', compute='_compute_appreciation',
                                    store=True)
    is_passed = fields.Boolean(string='Validé', compute='_compute_appreciation', store=True)
    comment = fields.Char(string='Observation', tracking=True)

    @api.depends('exam_id.academic_year_id', 'class_id.academic_year_id')
    def _compute_academic_year_id(self):
        for record in self:
            record.academic_year_id = record.exam_id.academic_year_id or record.class_id.academic_year_id or False

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

    def action_submit(self):
        """Passe la note à l'état Soumis."""
        for grade in self:
            if grade.state != 'draft':
                raise UserError("Seule une note en brouillon peut être soumise.")
            grade.state = 'submitted'

    def action_validate(self):
        """Valide la note (Direction ou Administration requise)."""
        if not (self.env.user.has_group('eacta_school.group_eacta_school_direction') or
                self.env.user.has_group('eacta_school.group_eacta_school_manager')):
            raise UserError("Seule la direction ou l'administration peut valider les notes.")
        for grade in self:
            if grade.state not in ('draft', 'submitted'):
                raise UserError("Seule une note soumise ou en brouillon peut être validée.")
            grade.state = 'validated'

    def action_publish(self):
        """Publie la note (Direction ou Administration requise)."""
        if not (self.env.user.has_group('eacta_school.group_eacta_school_direction') or
                self.env.user.has_group('eacta_school.group_eacta_school_manager')):
            raise UserError("Seule la direction ou l'administration peut publier les notes.")
        for grade in self:
            if grade.state != 'validated':
                raise UserError("Seule une note préalablement validée peut être publiée.")
            grade.state = 'published'

    def action_draft(self):
        """Réinitialise la note en brouillon."""
        is_dir_mgr = (self.env.user.has_group('eacta_school.group_eacta_school_direction') or
                      self.env.user.has_group('eacta_school.group_eacta_school_manager'))
        for grade in self:
            if grade.state in ('validated', 'published') and not is_dir_mgr:
                raise UserError("Seule la direction ou l'administration peut repasser une note validée ou publiée en brouillon.")
            grade.state = 'draft'

    def action_reject(self, reason=None):
        """Rejette une note soumise pour révision par l'enseignant."""
        self.action_draft()
        if reason:
            for grade in self:
                grade.message_post(body=f"Note rejetée pour révision : {reason}")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('grade') and 'status' not in vals:
                vals['status'] = 'graded'
            if 'state' not in vals:
                vals['state'] = 'draft'
        return super().create(vals_list)

    def write(self, vals):
        is_mgr = self.env.user.has_group('eacta_school.group_eacta_school_manager')
        is_dir = self.env.user.has_group('eacta_school.group_eacta_school_direction')

        # Restriction: impossible de modifier les notes si l'examen ou l'année est clôturé(e)
        if not is_mgr:
            for record in self:
                if record.exam_id and record.exam_id.state == 'done':
                    raise UserError(f"L'examen « {record.exam_id.name} » est clôturé. Seul un administrateur peut modifier les notes.")
                if record.academic_year_id and record.academic_year_id.state == 'closed':
                    raise UserError(f"L'année académique « {record.academic_year_id.name} » est clôturée. Les notes sont verrouillées.")

        # Permissions basées sur l'état
        critical_fields = {'grade', 'status', 'exam_id', 'student_id', 'is_justified'}
        if any(f in vals for f in critical_fields):
            for record in self:
                if record.state == 'published' and not is_mgr:
                    raise UserError("La note est publiée. Seul un administrateur peut la modifier.")
                if record.state == 'validated' and not (is_dir or is_mgr):
                    raise UserError("La note est validée. Seule la direction ou l'administration peut la modifier.")

        if 'grade' in vals and 'status' not in vals:
            pending = self.filtered(lambda g: g.status == 'pending')
            if pending:
                super(CourseGrade, pending).write(dict(vals, status='graded'))
                others = self - pending
                return super(CourseGrade, others).write(vals) if others else True
        return super().write(vals)

    def unlink(self):
        is_mgr = self.env.user.has_group('eacta_school.group_eacta_school_manager')
        if not is_mgr:
            for record in self:
                if record.state in ('validated', 'published'):
                    raise UserError("Impossible de supprimer une note validée ou publiée. Repassez-la d'abord en brouillon.")
        return super().unlink()

    def action_send_whatsapp_grade(self):
        """Ouvre l'assistant WhatsApp pour notifier les parents de la note."""
        self.ensure_one()
        return {
            'name': _("Notification WhatsApp - %s") % (self.student_id.name or 'Élève'),
            'type': 'ir.actions.act_window',
            'res_model': 'eacta.whatsapp.composer',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'active_model': 'eacta.course.grade',
                'active_id': self.id,
            },
        }
