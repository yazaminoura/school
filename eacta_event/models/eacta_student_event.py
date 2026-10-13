from odoo import models, fields

class EactaStudent(models.Model):
   _inherit = 'eacta.student'

   name = fields.Char(string="Nom complet", required=True, help="Entrez le nom complet de l'élève")