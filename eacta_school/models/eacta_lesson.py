from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

HOMEWORK_TYPES = [
    ('exercise', 'Exercices'),
    ('reading', 'Lecture'),
    ('revision', 'Révision / Contrôle à préparer'),
    ('project', 'Exposé / Projet'),
    ('other', 'Autre'),
]


class EactaLesson(models.Model):
    _name = 'eacta.lesson'
    _description = 'Cahier de textes : séance'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(string='Objet de la séance', required=True, tracking=True)
    date = fields.Date(string='Date', required=True, default=fields.Date.context_today, index=True, tracking=True)
    class_id = fields.Many2one('eacta.class', string='Classe', required=True, index=True, tracking=True)
    academic_year_id = fields.Many2one(related='class_id.academic_year_id', store=True, string='Année académique')
    course_id = fields.Many2one('eacta.course', string='Matière', required=True, index=True,
                                domain="[('id', 'in', class_course_ids)]")
    class_course_ids = fields.Many2many(related='class_id.course_ids', string='Matières de la classe')
    teacher_id = fields.Many2one('res.users', string='Enseignant', default=lambda self: self.env.user, index=True,
                                 domain="[('is_teacher', '=', True)]")
    slot_id = fields.Many2one('eacta.timetable.slot', string='Créneau', ondelete='set null',
                              domain="[('class_id', '=', class_id), ('course_id', '=', course_id)]")
    content = fields.Html(string='Contenu de la séance', sanitize_style=True)
    attachment_ids = fields.Many2many('ir.attachment', 'eacta_lesson_attachment_rel', 'lesson_id', 'attachment_id',
                                      string='Documents')
    homework_ids = fields.One2many('eacta.homework', 'lesson_id', string='Devoirs donnés')
    homework_count = fields.Integer(string='Devoirs', compute='_compute_homework_count')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)

    @api.depends('homework_ids')
    def _compute_homework_count(self):
        for lesson in self:
            lesson.homework_count = len(lesson.homework_ids)

    @api.onchange('course_id')
    def _onchange_course_id(self):
        if self.course_id.teacher_id:
            self.teacher_id = self.course_id.teacher_id

    def action_add_homework(self):
        self.ensure_one()
        return {
            'name': 'Nouveau devoir',
            'type': 'ir.actions.act_window',
            'res_model': 'eacta.homework',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_lesson_id': self.id,
                'default_class_id': self.class_id.id,
                'default_course_id': self.course_id.id,
                'default_teacher_id': self.teacher_id.id,
                'default_date_assigned': self.date,
            },
        }


class EactaHomework(models.Model):
    _name = 'eacta.homework'
    _description = 'Devoir à la maison'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'due_date desc, id desc'

    name = fields.Char(string='Intitulé', required=True, tracking=True)
    homework_type = fields.Selection(HOMEWORK_TYPES, string='Type', default='exercise', required=True)
    class_id = fields.Many2one('eacta.class', string='Classe', required=True, index=True, tracking=True)
    academic_year_id = fields.Many2one(related='class_id.academic_year_id', store=True, string='Année académique')
    course_id = fields.Many2one('eacta.course', string='Matière', required=True, index=True,
                                domain="[('id', 'in', class_course_ids)]")
    class_course_ids = fields.Many2many(related='class_id.course_ids', string='Matières de la classe')
    teacher_id = fields.Many2one('res.users', string='Enseignant', default=lambda self: self.env.user, index=True,
                                 domain="[('is_teacher', '=', True)]")
    lesson_id = fields.Many2one('eacta.lesson', string='Séance', ondelete='set null')
    date_assigned = fields.Date(string='Donné le', required=True, default=fields.Date.context_today)
    due_date = fields.Date(string='À rendre le', required=True, index=True, tracking=True)
    estimated_minutes = fields.Integer(string='Durée estimée (min)', default=30)
    description = fields.Html(string='Consignes', sanitize_style=True)
    attachment_ids = fields.Many2many('ir.attachment', 'eacta_homework_attachment_rel', 'homework_id',
                                      'attachment_id', string='Documents')
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('published', 'Publié'),
    ], string='État', default='draft', required=True, tracking=True, index=True)
    days_left = fields.Integer(string='Jours restants', compute='_compute_days_left')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)

    @api.depends('due_date')
    def _compute_days_left(self):
        today = fields.Date.context_today(self)
        for homework in self:
            homework.days_left = (homework.due_date - today).days if homework.due_date else 0

    @api.constrains('date_assigned', 'due_date')
    def _check_dates(self):
        for homework in self:
            if homework.due_date and homework.date_assigned and homework.due_date < homework.date_assigned:
                raise ValidationError("La date de remise doit être postérieure à la date où le devoir est donné.")

    @api.onchange('course_id')
    def _onchange_course_id(self):
        if self.course_id.teacher_id:
            self.teacher_id = self.course_id.teacher_id

    def action_publish(self):
        for homework in self:
            if homework.state == 'published':
                raise UserError(f"« {homework.name} » est déjà publié.")
        self.write({'state': 'published'})

    def action_draft(self):
        self.write({'state': 'draft'})


class EactaClassLessons(models.Model):
    _inherit = 'eacta.class'

    lesson_ids = fields.One2many('eacta.lesson', 'class_id', string='Cahier de textes')
    homework_ids = fields.One2many('eacta.homework', 'class_id', string='Devoirs')

    def action_view_lessons(self):
        self.ensure_one()
        return {
            'name': f"Cahier de textes - {self.display_name}",
            'type': 'ir.actions.act_window',
            'res_model': 'eacta.lesson',
            'view_mode': 'list,form,calendar',
            'domain': [('class_id', '=', self.id)],
            'context': {'default_class_id': self.id},
        }
