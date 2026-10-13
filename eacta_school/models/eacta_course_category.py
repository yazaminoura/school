from odoo import models, fields


class EactaCourseCategory(models.Model):
    _name = 'eacta.course.category'

    _description = 'Catégorie de cours E-ACTA'

    name = fields.Char(string='Nom', required=True, tracking=True)  # Corrected this line

    code = fields.Char(string='Code', size=5)

    description = fields.Text(string='Description')

    course_ids = fields.One2many('eacta.course', 'category_id', string='Cours')

    _sql_constraints = [

        ('name_unique', 'UNIQUE(name)', "Le nom de la catégorie doit être unique"),

        ('code_unique', 'UNIQUE(code)', "Le code de la catégorie doit être unique"),

    ]

