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
    _order = 'academic_year_id desc, name'

    name = fields.Char(string='Nom', required=True, tracking=True)
    academic_year_id = fields.Many2one(
        'eacta.academic.year', string='Année académique', required=True, tracking=True,
        default=lambda self: self.env['eacta.academic.year'].get_current_year(), index=True)

    @property
    def year_id(self):
        return self.academic_year_id
    year = fields.Char(
        string='Année', compute='_compute_year_text', inverse='_inverse_year_text',
        store=True, tracking=True)
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
    absence_count = fields.Integer(string='Absences totales', compute='_compute_attendance_stats')
    unjustified_absence_count = fields.Integer(string='Absences non justifiées', compute='_compute_attendance_stats')
    late_count = fields.Integer(string='Retards', compute='_compute_attendance_stats')
    attendance_rate = fields.Float(string="Taux d'assiduité (%)", compute='_compute_attendance_stats', digits=(5, 1))

    _sql_constraints = [
        ('name_academic_year_unique', 'unique(name, academic_year_id)', 'Une classe avec le même nom existe déjà pour cette année académique !'),
        ('capacity_positive', 'CHECK(capacity >= 0)', 'La capacité doit être positive.'),
    ]

    @api.depends('academic_year_id.name')
    def _compute_year_text(self):
        for class_ in self:
            class_.year = class_.academic_year_id.name or ''

    def _inverse_year_text(self):
        for class_ in self:
            if class_.year:
                y_str = class_.year.split('-')[0] if '-' in class_.year else class_.year
                name = class_.year
                try:
                    y_int = int(y_str)
                    start_d = f"{y_int}-09-01"
                    end_d = f"{y_int + 1}-06-30"
                    name = f"{y_int}-{y_int + 1}"
                except Exception:
                    start_d = fields.Date.today()
                    end_d = fields.Date.today()

                # Search both original and normalized name
                year_rec = self.env['eacta.academic.year'].sudo().search([
                    '|', ('name', '=', class_.year), ('name', '=', name)
                ], limit=1)
                if not year_rec:
                    has_open = self.env['eacta.academic.year'].sudo().search_count([('state', '=', 'open')])
                    today = fields.Date.today()
                    is_past = fields.Date.from_string(end_d) < today if end_d else False
                    initial_state = 'closed' if is_past else ('draft' if has_open else 'open')
                    year_rec = self.env['eacta.academic.year'].sudo().create({
                        'name': name,
                        'date_start': start_d,
                        'date_end': end_d,
                        'state': initial_state,
                    })
                class_.academic_year_id = year_rec

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

    def _compute_attendance_stats(self):
        Attendance = self.env['eacta.attendance']
        for class_ in self:
            records = Attendance.search([('class_id', '=', class_.id)])
            absences = records.filtered(lambda a: a.attendance_type == 'absent')
            lates = records.filtered(lambda a: a.attendance_type == 'late')
            presents = records.filtered(lambda a: a.attendance_type == 'present')
            total = len(records)
            class_.absence_count = len(absences)
            class_.unjustified_absence_count = len(absences.filtered(lambda a: not a.justified))
            class_.late_count = len(lates)
            class_.attendance_rate = round(100.0 * (len(presents) / total), 1) if total else 100.0


    @api.depends('name', 'academic_year_id.name', 'year')
    def _compute_display_name(self):
        for class_ in self:
            y_name = class_.academic_year_id.name or class_.year
            class_.display_name = f"{class_.name} ({y_name})" if y_name else class_.name

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

    @api.model
    def _name_search(self, name, domain=None, operator='ilike', limit=None, order=None):
        domain = domain or []
        if name:
            domain = ['|', '|', ('name', operator, name), ('academic_year_id.name', operator, name), ('level', operator, name)] + list(domain)
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

    @api.constrains('student_ids', 'academic_year_id')
    def _check_student_year_uniqueness(self):
        """Un élève ne peut appartenir qu'à une seule classe par année académique (requête groupée unique)."""
        if not self:
            return
        self.flush_model(['student_ids', 'academic_year_id'])
        self.env.cr.execute("""
            SELECT rel.eacta_student_id, c.academic_year_id, count(DISTINCT c.id)
            FROM eacta_class_eacta_student_rel rel
            JOIN eacta_class c ON c.id = rel.eacta_class_id
            WHERE c.active = true
              AND rel.eacta_student_id IN (
                  SELECT rel2.eacta_student_id
                  FROM eacta_class_eacta_student_rel rel2
                  WHERE rel2.eacta_class_id IN %s
              )
            GROUP BY rel.eacta_student_id, c.academic_year_id
            HAVING count(DISTINCT c.id) > 1
            LIMIT 1
        """, (tuple(self.ids),))
        row = self.env.cr.fetchone()
        if row:
            student = self.env['eacta.student'].browse(row[0])
            year = self.env['eacta.academic.year'].browse(row[1])
            raise ValidationError(
                f"L'élève {student.name} est inscrit dans plus d'une classe pour l'année académique "
                f"{year.name}. Un élève ne peut être que dans une classe par année."
            )

    def write(self, vals):
        res = super().write(vals)
        if 'course_ids' in vals or 'student_ids' in vals:
            for class_ in self:
                if class_.course_ids and class_.student_ids:
                    for student in class_.student_ids:
                        missing = class_.course_ids - student.course_ids
                        if missing:
                            student.write({'course_ids': [(4, c.id) for c in missing]})
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

    def action_open_deliberation_wizard(self):
        """Ouvre l'assistant de délibération du conseil de classe."""
        self.ensure_one()
        return {
            'name': f"PV de délibération - {self.name}",
            'type': 'ir.actions.act_window',
            'res_model': 'eacta.class.deliberation.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_class_id': self.id,
                'default_academic_year_id': self.academic_year_id.id,
            },
        }

