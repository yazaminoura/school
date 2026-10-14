from odoo import api, fields, models
from odoo.exceptions import ValidationError

LEVELS = [
    ('primary', 'Primaire'),
    ('secondary', 'Secondaire'),
    ('higher', 'Supérieur'),
]


class EactaClass(models.Model):
    _name = 'eacta.class'
    _description = 'Classe'
    _inherit = ['mail.thread']
    _order = 'year desc, name'

    name = fields.Char(string='Nom', required=True, tracking=True)
    year = fields.Char(
        string='Année académique', required=True, tracking=True,
        default=lambda self: str(fields.Date.today().year))
    level = fields.Selection(LEVELS, string='Cycle', required=True, default='primary', tracking=True)
    level_id = fields.Many2one('eacta.school.level', string='Niveau scolaire')
    start_date = fields.Date("Date de début")
    end_date = fields.Date("Date de fin")
    teacher_id = fields.Many2one(
        'res.users', string='Enseignant principal', tracking=True,
        domain="[('is_teacher', '=', True)]")
    student_ids = fields.Many2many('eacta.student', string='Élèves')
    course_ids = fields.Many2many('eacta.course', string='Cours')
    capacity = fields.Integer(string='Capacité', default=30, tracking=True)
    color = fields.Integer(string='Couleur')
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)

    student_count = fields.Integer(string='Effectif', compute='_compute_counts', store=True)
    course_count = fields.Integer(string='Nombre de cours', compute='_compute_counts', store=True)
    fill_rate = fields.Float(string='Taux de remplissage (%)', compute='_compute_counts', store=True,
                             aggregator='avg')
    available_seats = fields.Integer(string='Places disponibles', compute='_compute_counts', store=True)
    grade_ids = fields.One2many('eacta.course.grade', 'class_id', string='Notes')
    average = fields.Float(string='Moyenne de la classe', compute='_compute_results', digits=(4, 2))
    success_rate = fields.Float(string='Taux de réussite (%)', compute='_compute_results', digits=(5, 1))
    exam_count = fields.Integer(string='Examens', compute='_compute_exam_count')
    has_draft_students = fields.Boolean(string='Inscriptions en attente', compute='_compute_has_draft_students')

    _sql_constraints = [
        ('name_year_unique', 'unique(name, year)', 'Une classe avec le même nom existe déjà pour cette année !'),
        ('capacity_positive', 'CHECK(capacity >= 0)', 'La capacité doit être positive.'),
    ]

    @api.depends('student_ids', 'course_ids', 'capacity')
    def _compute_counts(self):
        for class_ in self:
            count = len(class_.student_ids)
            class_.student_count = count
            class_.course_count = len(class_.course_ids)
            class_.fill_rate = round(100.0 * count / class_.capacity, 1) if class_.capacity else 0.0
            class_.available_seats = max(class_.capacity - count, 0)

    @api.depends('student_ids', 'grade_ids.grade', 'grade_ids.status', 'grade_ids.coefficient')
    def _compute_results(self):
        Student = self.env['eacta.student']
        for class_ in self:
            averages = [Student._get_weighted_average(class_.grade_ids.filtered(lambda g: g.student_id == s))
                        for s in class_.student_ids]
            averages = [a for a in averages if a is not None]
            class_.average = round(sum(averages) / len(averages), 2) if averages else 0.0
            class_.success_rate = (
                round(100.0 * len([a for a in averages if a >= 10]) / len(averages), 1) if averages else 0.0)

    def _compute_exam_count(self):
        data = self.env['eacta.exam']._read_group([('class_ids', 'in', self.ids)], ['class_ids'], ['__count'])
        counts = {cls.id: count for cls, count in data}
        for class_ in self:
            class_.exam_count = counts.get(class_.id, 0)

    @api.depends('name', 'year')
    def _compute_display_name(self):
        for class_ in self:
            class_.display_name = f"{class_.name} ({class_.year})" if class_.year else class_.name

    @api.model
    def _name_search(self, name, domain=None, operator='ilike', limit=None, order=None):
        domain = domain or []
        if name:
            domain = ['|', '|', ('name', operator, name), ('year', operator, name), ('level', operator, name)] + list(domain)
        return self._search(domain, limit=limit, order=order)

    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for class_ in self:
            if class_.start_date and class_.end_date and class_.end_date < class_.start_date:
                raise ValidationError("La date de fin doit être postérieure à la date de début.")

    @api.constrains('student_ids', 'capacity')
    def _check_capacity(self):
        for class_ in self:
            if class_.capacity and len(class_.student_ids) > class_.capacity:
                raise ValidationError(
                    f"La classe {class_.display_name} est complète : "
                    f"{len(class_.student_ids)} élèves pour une capacité de {class_.capacity}.")

    @api.constrains('student_ids', 'year')
    def _check_student_year_uniqueness(self):
        """Un élève ne peut appartenir qu'à une seule classe par année."""
        for class_ in self:
            if not class_.student_ids:
                continue
            duplicate = self.search([
                ('id', '!=', class_.id),
                ('year', '=', class_.year),
                ('student_ids', 'in', class_.student_ids.ids),
            ], limit=1)
            if duplicate:
                student = (class_.student_ids & duplicate.student_ids)[:1]
                raise ValidationError(
                    f"L'élève {student.name} est déjà dans la classe {duplicate.name} pour l'année "
                    f"{class_.year}. Un élève ne peut être que dans une classe par année.")

    def write(self, vals):
        res = super().write(vals)
        if 'course_ids' in vals or 'student_ids' in vals:
            for class_ in self:
                if class_.course_ids and class_.student_ids:
                    for student in class_.student_ids:
                        missing = class_.course_ids - student.course_ids
                        if missing:
                            super(models.Model, student).write({'course_ids': [(4, c.id) for c in missing]})
        return res

    def _action_open(self, name, model, domain, context=None, view_mode='list,form'):
        return {
            'name': name,
            'type': 'ir.actions.act_window',
            'res_model': model,
            'view_mode': view_mode,
            'domain': domain,
            'context': context or {},
        }

    def action_view_students(self):
        self.ensure_one()
        return self._action_open(f"Élèves - {self.display_name}", 'eacta.student',
                                 [('class_ids', 'in', self.id)],
                                 {'default_class_ids': [self.id]}, 'kanban,list,form')

    def action_view_courses(self):
        self.ensure_one()
        return self._action_open(f"Cours - {self.display_name}", 'eacta.course',
                                 [('id', 'in', self.course_ids.ids)],
                                 {'default_class_ids': [self.id]}, 'kanban,list,form')

    def action_view_exams(self):
        self.ensure_one()
        return self._action_open(f"Examens - {self.display_name}", 'eacta.exam',
                                 [('class_ids', 'in', self.id)],
                                 {'default_class_ids': [self.id]}, 'list,kanban,calendar,form')

    def action_view_grades(self):
        self.ensure_one()
        return self._action_open(f"Notes - {self.display_name}", 'eacta.course.grade',
                                 [('class_id', '=', self.id)], {'default_class_id': self.id},
                                 'list,pivot,graph,form')

    def action_sync_courses_to_students(self):
        """Inscrit tous les élèves de la classe aux cours de la classe."""
        for class_ in self:
            class_.student_ids.write({'course_ids': [(4, c.id) for c in class_.course_ids]})
        return True

    @api.depends('student_ids.state')
    def _compute_has_draft_students(self):
        for class_ in self:
            class_.has_draft_students = any(s.state == 'draft' for s in class_.student_ids)

    def action_enroll_all_students(self):
        """Valide l'inscription de tous les élèves en pré-inscription de la classe."""
        enrolled_count = 0
        for class_ in self:
            drafts = class_.student_ids.filtered(lambda s: s.state == 'draft')
            enrolled_count += len(drafts)
            drafts.write({'state': 'enrolled'})
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': "Inscriptions validées",
                'message': f"{enrolled_count} élève(s) inscrit(s) avec succès.",
                'type': 'success',
                'sticky': False,
            }
        }

    def action_take_attendance(self):
        """Ouvre la feuille d'appel rapide pour cette classe."""
        self.ensure_one()
        return {
            'name': f"Feuille d'appel - {self.name}",
            'type': 'ir.actions.act_window',
            'res_model': 'eacta.attendance.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_class_id': self.id},
        }

    def action_generate_class_fees(self):
        """Ouvre l'assistant de facturation pré-rempli pour cette classe."""
        self.ensure_one()
        return {
            'name': f"Facturation - {self.name}",
            'type': 'ir.actions.act_window',
            'res_model': 'eacta.fee.generate.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_class_ids': [(6, 0, [self.id])]},
        }

    def action_view_attendances(self):
        """Affiche le registre d'assiduité de la classe."""
        self.ensure_one()
        return self._action_open(
            f"Assiduité - {self.display_name}", 'eacta.attendance',
            [('class_id', '=', self.id)],
            {'default_class_id': self.id, 'search_default_group_date': 1},
            'list,pivot,graph,form'
        )

    def action_promote_class(self):
        """Ouvre l'assistant de passage de fin d'année pour cette classe."""
        self.ensure_one()
        return {
            'name': f"Passage de classe - {self.name}",
            'type': 'ir.actions.act_window',
            'res_model': 'eacta.promotion.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'active_model': 'eacta.class',
                'active_id': self.id,
                'default_from_class_id': self.id,
            },
        }
