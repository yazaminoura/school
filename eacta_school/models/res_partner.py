from odoo import models, fields


class ResPartner(models.Model):
   _inherit = 'res.partner'


   is_school_parent = fields.Boolean(string="Est un parent d'élève")
   student_ids = fields.Many2many(
       'eacta.student',
       relation='eacta_partner_student_rel',
       column1='partner_id',
       column2='student_id',
       string="Élèves associés"
   )
   school_photo = fields.Binary(string="Photo de l'école")  # Field for uploading school photo


