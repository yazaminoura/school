from odoo import api, fields, models


class EactaCourseCategory(models.Model):
    _name = 'eacta.course.category'
    _description = 'Catégorie de cours'
    _order = 'name'

    name = fields.Char(string='Nom', required=True, translate=True)
    code = fields.Char(string='Code', size=8)
    description = fields.Text(string='Description')
    color = fields.Integer(string='Couleur')
    course_ids = fields.One2many('eacta.course', 'category_id', string='Cours')
    course_count = fields.Integer(string='Nombre de cours', compute='_compute_course_count')

    _sql_constraints = [
        ('name_unique', 'UNIQUE(name)', "Le nom de la catégorie doit être unique."),
        ('code_unique', 'UNIQUE(code)', "Le code de la catégorie doit être unique."),
    ]

    @api.depends('course_ids')
    def _compute_course_count(self):
        for category in self:
            category.course_count = len(category.course_ids)
