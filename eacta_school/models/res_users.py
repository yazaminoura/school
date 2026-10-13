from odoo import models, fields


class ResUsers(models.Model):
   _inherit = 'res.users'


   is_teacher = fields.Boolean(string="Est un enseignant")
   subject_ids = fields.Many2many('eacta.course.category',
                                  relation='eacta_users_cours_category_rel',
                                  column1='user_id',
                                  column2='category_id',
                                  string="Categories")
