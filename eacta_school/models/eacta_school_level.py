from odoo import models, fields


class EactaSchoolLevel(models.Model):
    _name = 'eacta.school.level'

    _description = 'Niveau scolaire E-ACTA'

    name = fields.Char(string='Nom', required=True)

    code = fields.Char(string='Code', size=3, required=True)

    sequence = fields.Integer(string='Séquence', default=10)


class_ids = fields.One2many('eacta.class', 'level_id', string='Classes')

_sql_constraints = [

    ('name_unique', 'UNIQUE(name)', "Le nom du niveau scolaire doit être unique"),

    ('code_unique', 'UNIQUE(code)', "Le code du niveau scolaire doit être unique"),

]

