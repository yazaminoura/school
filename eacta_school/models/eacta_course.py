from odoo import api, fields, models


class EactaCourse(models.Model):
    _name = 'eacta.course'
    _description = 'Cours'
    _inherit = ['mail.thread']
    _order = 'name'

    name = fields.Char(string='Nom du cours', required=True, tracking=True)
    code = fields.Char(string='Code du cours', required=True, tracking=True)
    description = fields.Text(string='Description')
    comment = fields.Text(string='Commentaire')
    teacher_id = fields.Many2one('res.users', string='Enseignant', tracking=True,
                                 domain="[('is_teacher', '=', True)]")
    class_ids = fields.Many2many('eacta.class', string='Classes')
    student_ids = fields.Many2many('eacta.student', string='Élèves inscrits')
    credits = fields.Float(string='Crédits', default=3.0, required=True)
    duration = fields.Float(string='Volume horaire (h)', default=30)
    coefficient = fields.Float(string='Coefficient', default=1.0, required=True)
    start_datetime = fields.Datetime("Début du cours")
    end_datetime = fields.Datetime("Fin du cours")
    category_id = fields.Many2one('eacta.course.category', string='Catégorie')
    image_128 = fields.Image(string="Image du cours", max_width=128, max_height=128)
    color = fields.Integer(string='Couleur')
    active = fields.Boolean(default=True)

    exam_ids = fields.One2many('eacta.exam', 'course_id', string='Examens')
    grade_ids = fields.One2many('eacta.course.grade', 'course_id', string='Notes des élèves')
    grade = fields.Float(string='Moyenne générale', compute='_compute_results', store=True, digits=(4, 2),
                         aggregator='avg')
    success_rate = fields.Float(string='Taux de réussite (%)', compute='_compute_results', store=True,
                                digits=(5, 1), aggregator='avg')
    student_count = fields.Integer(string='Inscrits', compute='_compute_counts')
    class_count = fields.Integer(string='Nombre de classes', compute='_compute_counts')
    exam_count = fields.Integer(string="Nombre d'examens", compute='_compute_counts')

    _sql_constraints = [
        ('code_unique', 'UNIQUE(code)', "Le code du cours doit être unique."),
        ('coefficient_positive', 'CHECK(coefficient > 0)', "Le coefficient doit être strictement positif."),
    ]

    @api.depends('grade_ids.grade', 'grade_ids.status')
    def _compute_results(self):
        for course in self:
            grades = course.grade_ids.filtered(lambda g: g.status == 'graded').mapped('grade')
            course.grade = round(sum(grades) / len(grades), 2) if grades else 0.0
            course.success_rate = (
                round(100.0 * len([g for g in grades if g >= 10]) / len(grades), 1) if grades else 0.0)

    @api.depends('student_ids', 'class_ids', 'exam_ids')
    def _compute_counts(self):
        for course in self:
            course.student_count = len(course.student_ids)
            course.class_count = len(course.class_ids)
            course.exam_count = len(course.exam_ids)

    @api.depends('name', 'code')
    def _compute_display_name(self):
        for course in self:
            course.display_name = f"[{course.code}] {course.name}" if course.code else course.name

    @api.model
    def _name_search(self, name, domain=None, operator='ilike', limit=None, order=None):
        domain = domain or []
        if name:
            domain = ['|', ('code', operator, name), ('name', operator, name)] + list(domain)
        return self._search(domain, limit=limit, order=order)

    def action_view_students(self):
        self.ensure_one()
        return {
            'name': f"Élèves - {self.name}",
            'type': 'ir.actions.act_window',
            'res_model': 'eacta.student',
            'view_mode': 'kanban,list,form',
            'domain': [('id', 'in', self.student_ids.ids)],
            'context': {'create': False},
        }

    def action_view_exams(self):
        self.ensure_one()
        return {
            'name': f"Examens - {self.name}",
            'type': 'ir.actions.act_window',
            'res_model': 'eacta.exam',
            'view_mode': 'list,kanban,calendar,form',
            'domain': [('course_id', '=', self.id)],
            'context': {'default_course_id': self.id},
        }

    def action_view_grades(self):
        self.ensure_one()
        return {
            'name': f"Notes - {self.name}",
            'type': 'ir.actions.act_window',
            'res_model': 'eacta.course.grade',
            'view_mode': 'list,pivot,graph,form',
            'domain': [('course_id', '=', self.id)],
            'context': {'search_default_group_by_exam': 1},
        }
