from odoo import models, fields, api

class EactaCourse(models.Model):
    _name = 'eacta.course'
    _description = 'Cours E-ACTA'

    name = fields.Char(string='Nom du cours', required=True)
    comment = fields.Text(string="Comment")
    code = fields.Char(string='Code du cours', required=True)
    description = fields.Text(string='Description')
    teacher_id = fields.Many2one(
        'res.users',
        string='Enseignant',
        domain="[('is_teacher', '=', True)]"  # Add this domain
    )
    class_ids = fields.Many2many('eacta.class', string='Classes')
    student_ids = fields.Many2many('eacta.student', string='Élèves inscrits')
    credits = fields.Float(string='Crédits', default=3.0, required=True)
    duration = fields.Float(string='Durée (heures)', default=30)
    start_datetime = fields.Datetime("Début du cours")
    end_datetime = fields.Datetime("Fin du cours")
    category_id = fields.Many2one('eacta.course.category', string='Catégorie', required=False)
    image_128 = fields.Image(string="Image du cours", max_width=128, max_height=128)
    grade_ids = fields.One2many('eacta.course.grade', 'course_id', string='Notes des étudiants')
    grade = fields.Float(string="La moyenne générale des étudiants", compute="_compute_average_grade")
    coefficient = fields.Float(string='Coefficient', default=1.0, required=True)

    @api.depends('grade_ids.grade')
    def _compute_average_grade(self):
        for course in self:
            grades = course.grade_ids.mapped('grade')
            filtered_grades = [grade for grade in grades if isinstance(grade, (int, float))]
            course.grade = round(sum(filtered_grades) / len(filtered_grades), 2) if filtered_grades else 0