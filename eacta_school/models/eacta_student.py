from odoo import models, fields, api
from odoo.exceptions import UserError


class EactaStudent(models.Model):
    _name = 'eacta.student'
    _description = 'Élève E-ACTA'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Nom', required=True, tracking=True)
    date_of_birth = fields.Date(string='Date de naissance')
    gender = fields.Selection([
        ('male', 'Masculin'),
        ('female', 'Féminin'),
        ('other', 'Autre')
    ], string='Genre')
    address = fields.Text(string='Adresse')
    class_ids = fields.Many2many('eacta.class', string='Classes', tracking=True)
    image_128 = fields.Image("Photo", max_width=128, max_height=128)
    phone = fields.Char(string="Téléphone")
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('enrolled', 'Inscrit'),
        ('graduated', 'Diplômer'),
        ('alumni', 'Ancien élève'),
    ], string='État', default='draft', required=True)
    student_comment = fields.Text(string='Commentaire', help="Comment for the student")
    is_graduated = fields.Boolean(string="Graduated", default=False)
    course_ids = fields.Many2many('eacta.course', string='Cours', tracking=True)
    course_count = fields.Integer(string='Nombre de cours', compute='_compute_course_count')
    course_grade_ids = fields.One2many('eacta.course.grade', 'student_id', string='Notes des Cours')
    average = fields.Float(string='Moyenne', compute='_compute_average', store=True, digits=(3, 2))
    gpa = fields.Float(string='GPA', compute='_compute_gpa', store=True, digits=(3, 2))
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        readonly=True
    )

    selected_class_id = fields.Many2one(
        'eacta.class',
        string='Classe sélectionnée',
        compute='_compute_selected_class',
        store=False
    )

    selected_year_courses = fields.Many2many(
        'eacta.course',
        string='Cours de l\'année sélectionnée',
        compute='_compute_selected_year_info'
    )


    selected_year_class = fields.Many2one(
        'eacta.class',
        string='Classe de l\'année sélectionnée',
        compute='_compute_selected_year_info'
    )

    @api.depends('selected_year', 'class_ids', 'course_ids', 'course_grade_ids')
    def _compute_selected_year_info(self):
        for student in self:
            if student.selected_year:
                selected_class = student.class_ids.filtered(
                    lambda c: c.year == student.selected_year
                )
                student.selected_year_class = selected_class[0] if selected_class else False

                if selected_class:
                    student.selected_year_courses = selected_class.course_ids
                else:
                    student.selected_year_courses = False

                # Filter grades for the selected year - FIXED FILTER
                student.selected_year_grades = student.course_grade_ids.filtered(
                    lambda g: g.class_id and g.class_id.year == student.selected_year
                )
            else:
                student.selected_year_class = False
                student.selected_year_courses = False
                student.selected_year_grades = False

    @api.depends('selected_year', 'class_ids')
    def _compute_selected_class(self):
        for student in self:
            if student.selected_year:
                selected_class = student.class_ids.filtered(
                    lambda c: c.year == student.selected_year
                )
                student.selected_class_id = selected_class[0] if selected_class else False
            else:
                student.selected_class_id = False

    # FIXED: Better method to get available years
    @api.model
    def _get_selection_year(self):
        """Get available years for selection"""
        # Get all years from all classes in the system
        all_years = self.env['eacta.class'].search([]).mapped('year')
        # Remove duplicates and sort
        unique_years = sorted(set(all_years))

        # If no classes exist, provide current and next year as fallback
        if not unique_years:
            current_year = str(fields.Date.today().year)
            next_year = str(int(current_year) + 1)
            unique_years = [current_year, next_year]

        return [(year, year) for year in unique_years if year]

    # Update the selected_year field definition with dynamic selection
    selected_year = fields.Selection(
        selection='_get_selection_year',
        string='Année sélectionnée',
        default=lambda self: str(fields.Date.today().year),
        help="Sélectionnez l'année académique à afficher"
    )

    # Add available years as computed field for the dropdown
    available_years = fields.Char(
        compute='_compute_available_years',
        store=False
    )

    @api.depends('class_ids.year')
    def _compute_available_years(self):
        for student in self:
            years = student.class_ids.mapped('year')
            student.available_years = ','.join(sorted(set(years))) if years else ''

    @api.onchange('class_id')
    def _onchange_class_id(self):
        """Synchronise automatiquement les cours quand la classe change"""
        if self.class_id:
            class_courses = self.class_id.course_ids
            self.course_ids = [(6, 0, class_courses.ids)]
        else:
            self.course_ids = [(5, 0, 0)]

    def write(self, vals):
        """Override write pour synchroniser les cours lors de la sauvegarde"""
        result = super(EactaStudent, self).write(vals)
        if 'class_id' in vals:
            for student in self:
                if student.class_id:
                    student.course_ids = [(6, 0, student.class_id.course_ids.ids)]
                else:
                    student.course_ids = [(5, 0, 0)]
        return result

    @api.depends('course_ids')
    def _compute_course_count(self):
        for student in self:
            student.course_count = len(student.course_ids)

    @api.depends('course_grade_ids.grade')
    def _compute_average(self):
        for student in self:
            grades = [grade.grade for grade in student.course_grade_ids if grade.grade is not None]
            student.average = round(sum(grades) / len(grades), 2) if grades else 0.0

    def debug_student_grades(self):
        for student in self:
            print(f"Student: {student.name}")
            print(f"Grade count: {len(student.course_grade_ids)}")
            for grade in student.course_grade_ids:
                print(f"  Course: {grade.course_id.name if grade.course_id else 'None'}")
                print(f"  Grade: {grade.grade}")
                print(f"  Class: {grade.class_id.name if grade.class_id else 'None'}")
                print(f"  Exam: {grade.exam_id.name if grade.exam_id else 'None'}")
            print(f"Average: {student.average}")
            print(f"GPA: {student.gpa}")
            print("---")

    # In eacta_student.py - add these methods

    selected_year_grades = fields.One2many(
        'eacta.course.grade',
        string='Notes de l\'année sélectionnée',
        compute='_compute_selected_year_info',
        inverse='_inverse_selected_year_grades'  # Add this line
    )


    def _inverse_selected_year_grades(self):
        """Allow writing to the computed field"""
        for student in self:
            # This method allows the field to be written to
            pass

    @api.depends('selected_year', 'class_ids', 'course_ids', 'course_grade_ids')
    def _compute_selected_year_info(self):
        for student in self:
            if student.selected_year:
                selected_class = student.class_ids.filtered(
                    lambda c: c.year == student.selected_year
                )
                student.selected_year_class = selected_class[0] if selected_class else False

                if selected_class:
                    student.selected_year_courses = selected_class.course_ids
                else:
                    student.selected_year_courses = False

                # Filter grades for the selected year
                student.selected_year_grades = student.course_grade_ids.filtered(
                    lambda g: g.class_id and g.class_id.year == student.selected_year
                )
            else:
                student.selected_year_class = False
                student.selected_year_courses = False
                student.selected_year_grades = False


    @api.depends('course_grade_ids.grade', 'course_grade_ids.course_id.credits')
    def _compute_gpa(self):
        for student in self:
            total_weighted = 0.0
            total_credits = 0.0

            for grade in student.course_grade_ids:
                if grade.course_id and grade.course_id.credits and grade.grade:
                    total_weighted += grade.grade * grade.course_id.credits
                    total_credits += grade.course_id.credits

            student.gpa = round(total_weighted / total_credits, 2) if total_credits > 0 else 0.0
    current_year_class_id = fields.Many2one(
        'eacta.class',
        string='Classe actuelle',
        compute='_compute_current_year_info',
        store=True
    )

    current_year = fields.Char(
        string='Année actuelle',
        compute='_compute_current_year_info',
        store=True
    )

    @api.depends('class_ids', 'class_ids.year')
    def _compute_current_year_info(self):
        current_year = str(fields.Date.today().year)
        for student in self:
            current_class = student.class_ids.filtered(lambda c: c.year == current_year)
            student.current_year_class_id = current_class[0] if current_class else False
            student.current_year = current_year if current_class else False

    @api.depends('name', 'class_ids')
    def _compute_display_name(self):
        current_year = str(fields.Date.today().year)
        for student in self:
            current_class = student.class_ids.filtered(lambda c: c.year == current_year)
            if current_class:
                student.display_name = f"{student.name} - {current_class[0].name} ({current_year})"
            else:
                student.display_name = student.name

    def name_get(self):
        return [(s.id, s.display_name) for s in self]

    def action_validate_enrollment(self):
        for student in self:
            if student.state != 'draft':
                raise UserError("L'inscription ne peut être validée que pour les étudiants en état de brouillon.")
            student.state = 'enrolled'

    def action_graduate(self):
        """Mark the student as graduated based on GPA or just change state."""
        for student in self:
            if student.state == 'graduated':
                raise UserError(f"{student.name} est déjà diplômé.")
            student.state = 'graduated'
            if student.gpa <= 10:
                raise UserError(
                    f"{student.name} a été diplômé, mais sa note est {student.gpa}. "
                    "Il faut une note supérieure à 10 pour un diplôme valide."
                )

    def action_draft(self):
        return self.write({'state': 'draft'})

    def action_enroll(self):
        return self.write({'state': 'enrolled'})

    def action_confirm_edit(self):
        """Confirme avant d'éditer l'élève."""
        return {
            'name': 'Confirm Edit',
            'type': 'ir.actions.act_window',
            'res_model': 'eacta.student',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
            'context': {
                'default_title': 'Confirmer la modification',
                'default_message': 'Êtes-vous sûr de vouloir modifier cet enregistrement ?',
                'confirm_callback': 'action_edit'
            }
        }

    def action_save(self):
        """Action de sauvegarde personnalisée avec logique additionnelle."""
        self.ensure_one()
        if not self.name:
            raise UserError("Le nom est requis pour enregistrer l'élève.")
        self.write({})
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    def action_view_courses(self):
        self.ensure_one()
        return {
            'name': "Cours de l'étudiant",
            'view_mode': 'list,form',
            'res_model': 'eacta.course',
            'domain': [('id', 'in', self.course_ids.ids)],
            'type': 'ir.actions.act_window',
            'context': {'create': False}
        }

    def get_average_grade(self, student):
        grades = student.course_ids.mapped('grade')
        filtered_grades = [float(grade) for grade in grades]
        return filtered_grades and round(sum(filtered_grades) / len(filtered_grades), 2) or 0.0

    @api.model
    def _get_class_average(self, class_id):
        students = self.env['eacta.student'].search([('class_id', '=', class_id)])
        total_grades = 0
        total_students = 0
        for student in students:
            student_avg = self._get_average_grade(student)
            if student_avg:
                total_grades += student_avg
                total_students += 1
        return round(total_grades / total_students, 2) if total_students else 0.0

    borrowed_book_ids = fields.One2many(
        'library.loan',
        compute='_compute_borrowed_book_ids',
        string="Livres empruntés"
    )

    @api.depends()
    def _compute_borrowed_book_ids(self):
        for student in self:
            emprunt_ids = self.env['library.loan'].search([('borrower_id', '=', student.id)])
            student.borrowed_book_ids = [(6, 0, emprunt_ids.ids)]

    def action_view_borrowed_books(self):
        self.ensure_one()
        return {
            'name': "Livres empruntés",
            'view_mode': 'list,form',
            'res_model': 'library.loan',
            'domain': [('borrower_ref', '=', self.id)],
            'type': 'ir.actions.act_window',
            'context': {'create': False}
        }

    borrowed_book_count = fields.Integer(
        string="Nombre de livres empruntés",
        compute='_compute_borrowed_book_count'
    )

    @api.depends('borrowed_book_ids')
    def _compute_borrowed_book_count(self):
        for student in self:
            student.borrowed_book_count = len(student.borrowed_book_ids)

    event_ids = fields.Many2many(
        'eacta.school.event',
        relation='eacta_event_student_rel',
        column1='student_id',
        column2='event_id',
        string="Événements participés",
        compute='_compute_event_ids',
        store=False
    )

    event_count = fields.Integer(
        string="Nombre d'événements",
        compute='_compute_event_count'
    )

    @api.depends()
    def _compute_event_ids(self):
        for student in self:
            event_ids = self.env['eacta.school.event'].search([('participant_ids', 'in', student.id)])
            student.event_ids = [(6, 0, event_ids.ids)]

    @api.depends('event_ids')
    def _compute_event_count(self):
        for student in self:
            student.event_count = len(student.event_ids)

    def action_view_events(self):
        self.ensure_one()
        return {
            'name': "Événements participés",
            'view_mode': 'list,form',
            'res_model': 'eacta.school.event',
            'domain': [('participant_ids', 'in', self.id)],
            'type': 'ir.actions.act_window',
            'context': {'create': False}
        }