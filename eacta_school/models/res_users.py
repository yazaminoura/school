from odoo import api, fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    is_teacher = fields.Boolean(string="Est un enseignant")
    subject_ids = fields.Many2many('eacta.course.category',
                                   relation='eacta_users_cours_category_rel',
                                   column1='user_id',
                                   column2='category_id',
                                   string="Disciplines")
    taught_course_ids = fields.One2many('eacta.course', 'teacher_id', string='Cours enseignés')
    taught_course_count = fields.Integer(string='Nombre de cours enseignés', compute='_compute_taught_course_count')

    @api.depends('taught_course_ids')
    def _compute_taught_course_count(self):
        for user in self:
            user.taught_course_count = len(user.taught_course_ids)
