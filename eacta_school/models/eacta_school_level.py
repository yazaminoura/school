from odoo import api, fields, models


class EactaSchoolLevel(models.Model):
    _name = 'eacta.school.level'
    _description = 'Niveau scolaire'
    _order = 'sequence, name'

    name = fields.Char(string='Nom', required=True, translate=True)
    code = fields.Char(string='Code', size=6, required=True)
    sequence = fields.Integer(string='Séquence', default=10)
    active = fields.Boolean(default=True)
    color = fields.Integer(string='Couleur')
    class_ids = fields.One2many('eacta.class', 'level_id', string='Classes')
    class_count = fields.Integer(string='Nombre de classes', compute='_compute_class_count')

    _sql_constraints = [
        ('name_unique', 'UNIQUE(name)', "Le nom du niveau scolaire doit être unique."),
        ('code_unique', 'UNIQUE(code)', "Le code du niveau scolaire doit être unique."),
    ]

    @api.depends('class_ids')
    def _compute_class_count(self):
        for level in self:
            level.class_count = len(level.class_ids)
