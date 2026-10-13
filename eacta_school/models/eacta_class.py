from odoo import models, fields, api
from odoo.exceptions import ValidationError  # CORRECTED IMPORT

class EactaClass(models.Model):
    _name = 'eacta.class'
    _description = 'Classe E-ACTA'
    _order = 'year desc, name'

    name = fields.Char(string='Nom', required=True)
    year = fields.Char(string='Année académique', required=True, default=lambda self: str(fields.Date.today().year))
    level = fields.Selection([
        ('primary', 'Primaire'),
        ('secondary', 'Secondaire'),
        ('higher', 'Supérieur')
    ], string='Niveau', required=True)
    start_date = fields.Date("Date de début")
    end_date = fields.Date("Date de fin")
    teacher_id = fields.Many2one('res.users', string='Enseignant principal',domain="[('is_teacher', '=', True)]")
    level_id = fields.Many2one('eacta.school.level', string='Niveau scolaire')
    student_ids = fields.Many2many('eacta.student', string='Élèves')
    course_ids = fields.Many2many('eacta.course', string='Cours')
    capacity = fields.Integer(string='Capacité', default=30)

    # Add unique constraint to prevent duplicate class names in same year
    _sql_constraints = [
        ('name_year_unique', 'unique(name, year)', 'Une classe avec le même nom existe déjà pour cette année!'),
    ]

    @api.depends('name', 'year', 'level')
    def _compute_display_name(self):
        for class_ in self:
            class_.display_name = f"{class_.name} ({class_.year}) - {class_.get_level_display()}"

    def name_get(self):
        return [(c.id, c.display_name) for c in self]

    def get_level_display(self):
        return dict(self._fields['level'].selection).get(self.level)

    def action_view_courses(self):
        self.ensure_one()
        return {
            'name': 'Cours',
            'type': 'ir.actions.act_window',
            'res_model': 'eacta.course',
            'view_mode': 'kanban,list,form,calendar',
            'domain': [('id', 'in', self.course_ids.ids)],
            'context': {'default_class_ids': [(4, self.id)]},
        }

    @api.constrains('student_ids')
    def _check_student_year_uniqueness(self):
        """Ensure a student is only in one class per year"""
        for class_ in self:
            for student in class_.student_ids:
                # Check if student is in any other class of the same year
                other_classes = self.search([
                    ('id', '!=', class_.id),
                    ('year', '=', class_.year),
                    ('student_ids', 'in', student.id)
                ])
                if other_classes:
                    raise ValidationError(
                        f"L'étudiant {student.name} est déjà dans la classe {other_classes[0].name} "
                        f"pour l'année {class_.year}. Un étudiant ne peut être que dans une classe par année."
                    )