from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_school_parent = fields.Boolean(string="Est un parent d'élève")
    student_ids = fields.Many2many(
        'eacta.student',
        relation='eacta_partner_student_rel',
        column1='partner_id',
        column2='student_id',
        string="Élèves associés",
    )
    school_student_count = fields.Integer(string="Nombre d'enfants", compute='_compute_school_student_count')
    school_photo = fields.Binary(string="Photo de l'école")

    @api.depends('student_ids')
    def _compute_school_student_count(self):
        for partner in self:
            partner.school_student_count = len(partner.student_ids)

    def action_view_school_students(self):
        self.ensure_one()
        return {
            'name': f"Enfants de {self.name}",
            'type': 'ir.actions.act_window',
            'res_model': 'eacta.student',
            'view_mode': 'kanban,list,form',
            'domain': [('id', 'in', self.student_ids.ids)],
            'context': {'default_parent_ids': [self.id]},
        }
