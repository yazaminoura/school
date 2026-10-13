from odoo import models,fields

class EactaExam(models.Model):
   _name = 'eacta.exam'
   _description = 'Exam'


   course_id = fields.Many2one('eacta.course', string="Matière", required=True)
   name = fields.Char(string="Nom de l'examen", required=True)
   date = fields.Date(string="Date de l'examen", required=True)
   # Exemple de champ lié pour récupérer le classe du cours
   class_ids = fields.Many2many(
       'eacta.class',
       'eacta_exam_class_rel',  # Nom de la table intermédiaire
       'exam_id',  # Champ local
       'class_ids',  # Champ distant
       string="Classes",
       related='course_id.class_ids',  # Liaison au champ `class_ids` du cours
       store=True
   )
