from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from .eacta_course_grade import APPRECIATIONS, appreciation_for


class EactaStudent(models.Model):
    _name = 'eacta.student'
    _description = 'Élève'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    # ------------------------------------------------------------------
    # Identité
    # ------------------------------------------------------------------
    code = fields.Char(string='Matricule', readonly=True, copy=False, index=True, tracking=True)
    name = fields.Char(string='Nom', required=True, tracking=True)
    image_128 = fields.Image("Photo", max_width=128, max_height=128)
    date_of_birth = fields.Date(string='Date de naissance')
    age = fields.Integer(string='Âge', compute='_compute_age')
    gender = fields.Selection([
        ('male', 'Masculin'),
        ('female', 'Féminin'),
        ('other', 'Autre'),
    ], string='Genre')
    email = fields.Char(string='E-mail')
    phone = fields.Char(string="Téléphone")
    address = fields.Text(string='Adresse')
    parent_ids = fields.Many2many(
        'res.partner', relation='eacta_partner_student_rel', column1='student_id', column2='partner_id',
        string='Parents / Tuteurs')
    user_id = fields.Many2one('res.users', string='Compte utilisateur élève', copy=False, tracking=True)
    partner_id = fields.Many2one('res.partner', string='Contact / Partenaire élève', copy=False, tracking=True)
    enrollment_date = fields.Date(string="Date d'inscription", default=fields.Date.context_today)
    student_comment = fields.Text(string='Commentaire')
    color = fields.Integer(string='Couleur')
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', string='Établissement', default=lambda self: self.env.company,
                                 readonly=True)

    # ------------------------------------------------------------------
    # Scolarité
    # ------------------------------------------------------------------
    state = fields.Selection([
        ('draft', 'Pré-inscription'),
        ('enrolled', 'Inscrit'),
        ('graduated', 'Diplômé'),
        ('alumni', 'Ancien élève'),
    ], string='État', default='draft', required=True, tracking=True, group_expand='_group_expand_states')
    is_graduated = fields.Boolean(string="Diplômé", compute='_compute_is_graduated', store=True)
    class_ids = fields.Many2many('eacta.class', string='Classes', tracking=True)
    current_class_id = fields.Many2one('eacta.class', string='Classe actuelle',
                                       compute='_compute_current_class', inverse='_inverse_current_class',
                                       store=True, readonly=False, tracking=True,
                                       domain="[('active', '=', True)]",
                                       help="Classe principale de l'élève pour l'année scolaire en cours. Affecte automatiquement tous les cours de la classe.")
    academic_year_id = fields.Many2one('eacta.academic.year', string='Année académique actuelle',
                                       compute='_compute_current_class', store=True)
    current_year = fields.Char(string='Année en cours', compute='_compute_current_class', store=True)
    course_ids = fields.Many2many('eacta.course', string='Cours suivis', tracking=True)
    course_count = fields.Integer(string='Nombre de cours', compute='_compute_course_count')
    class_course_count = fields.Integer(string='Cours de la classe', compute='_compute_course_count')
    elective_course_count = fields.Integer(string='Cours optionnels', compute='_compute_course_count')

    # ------------------------------------------------------------------
    # Résultats
    # ------------------------------------------------------------------
    course_grade_ids = fields.One2many('eacta.course.grade', 'student_id', string='Notes')
    result_ids = fields.One2many('eacta.student.result', 'student_id', string='Bulletins et résultats')
    average = fields.Float(string='Moyenne générale (année en cours)', compute='_compute_results', store=True, digits=(4, 2),
                           aggregator='avg', help="Moyenne pondérée par les coefficients des matières pour l'année en cours")
    gpa = fields.Float(string='GPA', compute='_compute_results', store=True, digits=(4, 2), aggregator='avg',
                       help="Moyenne pondérée par les crédits des matières")
    appreciation = fields.Selection(APPRECIATIONS, string='Appréciation', compute='_compute_results', store=True)
    grade_count = fields.Integer(string='Nombre de notes', compute='_compute_results', store=True)
    class_rank = fields.Integer(string='Rang dans la classe', compute='_compute_class_rank', store=True)
    class_size = fields.Integer(string='Effectif de la classe', compute='_compute_class_rank', store=True)

    # Filtre par année dans la fiche
    selected_year = fields.Selection(selection='_get_selection_year', string='Année affichée',
                                     help="Sélectionnez l'année académique à afficher")
    display_year = fields.Char(string='Année', compute='_compute_selected_year_info')
    selected_year_class = fields.Many2one('eacta.class', string="Classe de l'année",
                                          compute='_compute_selected_year_info')
    selected_year_courses = fields.Many2many('eacta.course', string="Cours de l'année",
                                             compute='_compute_selected_year_info')
    selected_year_grades = fields.One2many('eacta.course.grade', string="Notes de l'année",
                                           compute='_compute_selected_year_info')
    selected_year_average = fields.Float(string="Moyenne de l'année", digits=(4, 2),
                                         compute='_compute_selected_year_info')

    # ------------------------------------------------------------------
    # Assiduité & Absences
    # ------------------------------------------------------------------
    attendance_ids = fields.One2many('eacta.attendance', 'student_id', string='Assiduité')
    absence_count = fields.Integer(string='Absences', compute='_compute_attendance_stats')
    unjustified_absence_count = fields.Integer(string='Absences non justifiées', compute='_compute_attendance_stats')
    late_count = fields.Integer(string='Retards', compute='_compute_attendance_stats')

    # ------------------------------------------------------------------
    # Santé, Urgence & Services
    # ------------------------------------------------------------------
    emergency_contact_name = fields.Char(string="Contact d'urgence")
    emergency_contact_phone = fields.Char(string="Tél. urgence")
    emergency_contact_relation = fields.Char(string="Lien de parenté")
    blood_group = fields.Selection([
        ('A+', 'A+'), ('A-', 'A-'),
        ('B+', 'B+'), ('B-', 'B-'),
        ('AB+', 'AB+'), ('AB-', 'AB-'),
        ('O+', 'O+'), ('O-', 'O-'),
    ], string='Groupe sanguin', groups="eacta_school.group_eacta_school_manager,eacta_school.group_eacta_school_secretary,eacta_school.group_eacta_school_nurse")
    allergies = fields.Text(string='Allergies & Intolérances', groups="eacta_school.group_eacta_school_manager,eacta_school.group_eacta_school_secretary,eacta_school.group_eacta_school_nurse")
    medical_notes = fields.Text(string='Suivi médical / PAI', groups="eacta_school.group_eacta_school_manager,eacta_school.group_eacta_school_secretary,eacta_school.group_eacta_school_nurse")
    transport_mode = fields.Selection([
        ('bus', 'Transport scolaire (Bus)'),
        ('parents', 'Déposé par les parents'),
        ('autonomous', 'Autonome (Pied / Vélo)'),
    ], string='Mode de transport', default='parents')
    transport_line_id = fields.Many2one('eacta.transport.line', string="Ligne de transport", tracking=True)
    transport_stop_id = fields.Many2one('eacta.transport.stop', string="Arrêt de bus",
                                        domain="[('line_id', '=', transport_line_id)]", tracking=True)
    qr_token = fields.Char(string="Jeton QR Code", copy=False, readonly=True, index=True)
    canteen = fields.Boolean(string='Demi-pensionnaire / Cantine', default=False)

    # ------------------------------------------------------------------
    # Distinctions & Mention du conseil
    # ------------------------------------------------------------------
    honor_mention = fields.Selection([
        ('felicitations', 'Félicitations'),
        ('tableau_honneur', "Tableau d'honneur"),
        ('compliments', 'Compliments'),
        ('encouragements', 'Encouragements'),
        ('avertissement', 'Avertissement'),
        ('blame', 'Blâme'),
        ('none', 'Sans distinction'),
    ], string='Distinction du conseil', compute='_compute_honor_mention', store=True)

    _sql_constraints = [
        ('code_unique', 'UNIQUE(code)', "Ce matricule est déjà attribué à un autre élève."),
    ]

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.model
    def _group_expand_states(self, states, domain):
        return [key for key, _label in self._fields['state'].selection]

    @api.model
    def _get_selection_year(self):
        years = sorted({y for y in self.env['eacta.class'].sudo().search([]).mapped('year') if y}, reverse=True)
        if not years:
            years = [str(fields.Date.today().year)]
        return [(year, year) for year in years]

    @api.depends('date_of_birth')
    def _compute_age(self):
        today = fields.Date.context_today(self)
        for student in self:
            student.age = relativedelta(today, student.date_of_birth).years if student.date_of_birth else 0

    @api.depends('state')
    def _compute_is_graduated(self):
        for student in self:
            student.is_graduated = student.state in ('graduated', 'alumni')

    @api.depends('class_ids', 'class_ids.academic_year_id', 'class_ids.year')
    def _compute_current_class(self):
        for student in self:
            if student.class_ids:
                latest = student.class_ids.sorted(
                    lambda c: (c.academic_year_id.date_start if c.academic_year_id else False, c.year or '', c.id),
                    reverse=True)[:1]
                student.current_class_id = latest
                student.academic_year_id = latest.academic_year_id if latest else False
                student.current_year = latest.year if latest else False
            elif not student.current_class_id:
                student.current_class_id = False
                student.academic_year_id = False
                student.current_year = False

    def _inverse_current_class(self):
        for student in self:
            if student.current_class_id:
                same_year = student.class_ids.filtered(
                    lambda c: c.id != student.current_class_id.id and c.academic_year_id == student.current_class_id.academic_year_id
                )
                commands = [(3, c.id) for c in same_year]
                if student.current_class_id not in student.class_ids:
                    commands.append((4, student.current_class_id.id))
                if commands:
                    student.class_ids = commands
                student.academic_year_id = student.current_class_id.academic_year_id
                student.current_year = student.current_class_id.year or str(fields.Date.today().year)
            elif student.class_ids:
                curr_classes = student.class_ids.filtered(lambda c: c.academic_year_id == student.academic_year_id)
                if curr_classes:
                    student.class_ids = [(3, c.id) for c in curr_classes]
                student.academic_year_id = False
                student.current_year = False

    @api.onchange('current_class_id')
    def _onchange_current_class_id(self):
        if self.current_class_id:
            self.academic_year_id = self.current_class_id.academic_year_id
            self.current_year = self.current_class_id.year or str(fields.Date.today().year)
            prev_class = self._origin.current_class_id if (self._origin and self._origin.current_class_id) else False
            if prev_class:
                old_class_courses = prev_class.course_ids
            else:
                old_class_courses = self.course_ids.filtered(
                    lambda c: c.class_ids and self.current_class_id not in c.class_ids
                )
            extra_courses = self.course_ids - old_class_courses
            self.course_ids = self.current_class_id.course_ids | extra_courses
        elif not self.current_class_id:
            if self._origin and self._origin.current_class_id:
                self.course_ids = self.course_ids - self._origin.current_class_id.course_ids
            self.academic_year_id = False
            self.current_year = False

    def _is_eldest_sibling(self):
        """
        Détermine si l'élève est l'aîné parmi ses frères et sœurs inscrits (même parent).
        L'aîné est identifié par sa date de naissance la plus ancienne (date_of_birth asc).
        En cas d'absence de date ou d'égalité, l'ordre de création (id asc) sert de départage.
        """
        self.ensure_one()
        if not self.parent_ids:
            return True
        siblings = self.search([
            ('parent_ids', 'in', self.parent_ids.ids),
            ('state', 'in', ('draft', 'enrolled')),
        ])
        if len(siblings) <= 1:
            return True
        far_future = fields.Date.to_date('9999-12-31')
        sorted_siblings = sorted(
            siblings,
            key=lambda s: (s.date_of_birth or far_future, s.id)
        )
        return self.id == sorted_siblings[0].id

    @api.depends('course_ids', 'current_class_id.course_ids')
    def _compute_course_count(self):
        for student in self:
            class_courses = student.current_class_id.course_ids if student.current_class_id else self.env['eacta.course']
            in_class = student.course_ids & class_courses
            student.course_count = len(student.course_ids)
            student.class_course_count = len(in_class)
            student.elective_course_count = len(student.course_ids - in_class)

    @api.model
    def _get_weighted_average(self, grades, weight='coefficient'):
        """Moyenne pondérée des notes « notées ». Retourne None si aucune note."""
        total = weights = 0.0
        for grade in grades.filtered(lambda g: g.status == 'graded'):
            w = grade.course_id[weight] or 1.0
            total += grade.grade * w
            weights += w
        return round(total / weights, 2) if weights else None

    @api.depends('course_grade_ids.grade', 'course_grade_ids.status', 'course_grade_ids.coefficient',
                 'course_grade_ids.course_id.credits', 'current_class_id', 'current_class_id.academic_year_id')
    def _compute_results(self):
        for student in self:
            curr_year = student.current_class_id.academic_year_id if student.current_class_id else False
            if curr_year:
                grades = student.course_grade_ids.filtered(lambda g: g.academic_year_id == curr_year)
            else:
                grades = student.course_grade_ids
            average = self._get_weighted_average(grades)
            gpa = self._get_weighted_average(grades, weight='credits')
            student.average = average or 0.0
            student.gpa = gpa or 0.0
            student.appreciation = appreciation_for(average) if average is not None else False
            student.grade_count = len(grades.filtered(lambda g: g.status == 'graded'))

    @api.depends('current_class_id', 'average')
    def _compute_class_rank(self):
        cache = {}
        for student in self:
            klass = student.current_class_id
            if not klass:
                student.class_rank = student.class_size = 0
                continue
            if klass.id not in cache:
                ranking = []
                for mate in klass.student_ids:
                    avg = self._get_weighted_average(mate.course_grade_ids.filtered(lambda g: g.class_id == klass))
                    if avg is not None:
                        ranking.append((avg, mate.id))
                ranking.sort(reverse=True)
                cache[klass.id] = ([sid for _avg, sid in ranking], len(klass.student_ids))
            ordered, size = cache[klass.id]
            student.class_rank = ordered.index(student.id) + 1 if student.id in ordered else 0
            student.class_size = size

    @api.depends('attendance_ids.attendance_type', 'attendance_ids.justified')
    def _compute_attendance_stats(self):
        for student in self:
            absences = student.attendance_ids.filtered(lambda a: a.attendance_type == 'absent')
            student.absence_count = len(absences)
            student.unjustified_absence_count = len(absences.filtered(lambda a: not a.justified))
            student.late_count = len(student.attendance_ids.filtered(lambda a: a.attendance_type == 'late'))

    @api.depends('average', 'grade_count')
    def _compute_honor_mention(self):
        for student in self:
            if not student.grade_count:
                student.honor_mention = 'none'
            elif student.average >= 16:
                student.honor_mention = 'felicitations'
            elif student.average >= 14:
                student.honor_mention = 'tableau_honneur'
            elif student.average >= 13:
                student.honor_mention = 'compliments'
            elif student.average >= 12:
                student.honor_mention = 'encouragements'
            elif student.average >= 10:
                student.honor_mention = 'none'
            elif student.average >= 8:
                student.honor_mention = 'avertissement'
            else:
                student.honor_mention = 'blame'

    @api.depends('selected_year', 'current_year', 'class_ids', 'course_ids', 'course_grade_ids')
    def _compute_selected_year_info(self):
        for student in self:
            year = student.selected_year or student.current_year
            klass = student.class_ids.filtered(lambda c: c.year == year)[:1] if year else self.env['eacta.class']
            grades = student.course_grade_ids.filtered(lambda g: g.year == year) if year else student.course_grade_ids
            student.display_year = year or False
            student.selected_year_class = klass
            student.selected_year_courses = klass.course_ids if klass else student.course_ids
            student.selected_year_grades = grades
            student.selected_year_average = self._get_weighted_average(grades) or 0.0

    @api.depends('name', 'code', 'current_class_id')
    def _compute_display_name(self):
        for student in self:
            label = student.name or ''
            if student.code:
                label = f"[{student.code}] {label}"
            student.display_name = label

    @api.model
    def _name_search(self, name, domain=None, operator='ilike', limit=None, order=None):
        domain = domain or []
        if name:
            domain = ['|', ('code', operator, name), ('name', operator, name)] + list(domain)
        return self._search(domain, limit=limit, order=order)

    @api.constrains('transport_line_id', 'transport_stop_id')
    def _check_transport_line_stop(self):
        for student in self:
            if student.transport_stop_id and student.transport_line_id:
                if student.transport_stop_id.line_id != student.transport_line_id:
                    raise ValidationError(
                        f"L'arrêt « {student.transport_stop_id.name} » n'appartient pas à la ligne « {student.transport_line_id.name} »."
                    )
            if student.transport_line_id and student.transport_line_id.capacity:
                line = student.transport_line_id
                passengers = self.search([('transport_line_id', '=', line.id)])
                if len(passengers) > line.capacity:
                    raise ValidationError(
                        f"Capacité dépassée pour la ligne « {line.name} » : "
                        f"{len(passengers)} passager(s) pour {line.capacity} place(s) disponible(s)."
                    )

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        import secrets
        sequence = self.env['ir.sequence']
        for vals in vals_list:
            if not vals.get('code'):
                vals['code'] = sequence.next_by_code('eacta.student.code') or False
            if not vals.get('qr_token'):
                vals['qr_token'] = secrets.token_urlsafe(32)
            class_id = vals.get('current_class_id')
            if class_id:
                class_ids = vals.get('class_ids') or []
                if not any(cmd[0] in (4, 6) and (class_id in (cmd[2] if cmd[0] == 6 else [cmd[1]])) for cmd in class_ids):
                    class_ids.append((4, class_id))
                    vals['class_ids'] = class_ids
                if 'course_ids' not in vals:
                    klass = self.env['eacta.class'].browse(class_id)
                    if klass.course_ids:
                        vals['course_ids'] = [(6, 0, klass.course_ids.ids)]
        students = super().create(vals_list)
        students._sync_class_courses()
        for student in students:
            if student.parent_ids:
                student.parent_ids.filtered(lambda p: not p.is_school_parent).write({'is_school_parent': True})
        return students

    def action_regenerate_qr_token(self):
        """Régénère un jeton cryptographique sécurisé pour le QR code de la carte d'élève."""
        import secrets
        for student in self:
            student.qr_token = secrets.token_urlsafe(32)
        return True

    def action_print_student_badge(self):
        """Lance l'impression de la carte d'élève officielle avec QR code."""
        self.ensure_one()
        return self.env.ref('eacta_school.action_report_student_card_badge').report_action(self, config=False)

    def write(self, vals):
        if 'current_class_id' in vals:
            new_class_id = vals['current_class_id']
            if new_class_id and 'course_ids' not in vals:
                new_class = self.env['eacta.class'].browse(new_class_id)
                for student in self:
                    if student.current_class_id and student.current_class_id.id != new_class_id:
                        old_courses = student.current_class_id.course_ids
                        extra_courses = student.course_ids - old_courses
                        target_courses = new_class.course_ids | extra_courses
                        super(EactaStudent, student).write({'course_ids': [(6, 0, target_courses.ids)]})
                    elif not student.current_class_id:
                        target_courses = new_class.course_ids | student.course_ids
                        super(EactaStudent, student).write({'course_ids': [(6, 0, target_courses.ids)]})
            elif not new_class_id and 'course_ids' not in vals:
                for student in self:
                    if student.current_class_id:
                        remaining_courses = student.course_ids - student.current_class_id.course_ids
                        super(EactaStudent, student).write({'course_ids': [(6, 0, remaining_courses.ids)]})
        res = super().write(vals)
        if 'class_ids' in vals or 'current_class_id' in vals:
            self._sync_class_courses()
        if 'parent_ids' in vals:
            for student in self:
                if student.parent_ids:
                    student.parent_ids.filtered(lambda p: not p.is_school_parent).write({'is_school_parent': True})
        return res

    def _sync_class_courses(self):
        """Inscrit automatiquement l'élève aux cours de sa classe actuelle sans écraser ses cours optionnels."""
        for student in self:
            if student.current_class_id and student.current_class_id.course_ids:
                missing = student.current_class_id.course_ids - student.course_ids
                if missing:
                    super(EactaStudent, student).write({'course_ids': [(4, c.id) for c in missing]})

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------
    def action_enroll(self):
        for student in self:
            if student.state != 'draft':
                raise UserError(f"Seule une pré-inscription peut être validée ({student.name}).")
            if not student.current_class_id and not student.class_ids:
                raise UserError(f"Affectez une classe à {student.name} avant de valider son inscription.")
        self.write({'state': 'enrolled'})

    # Compatibilité avec l'ancien bouton
    action_validate_enrollment = action_enroll

    def action_graduate(self):
        for student in self:
            if student.state != 'enrolled':
                raise UserError(f"{student.name} doit être inscrit pour être diplômé.")
            if student.average < 10:
                raise UserError(
                    f"{student.name} ne peut pas être diplômé : sa moyenne générale est de "
                    f"{student.average:.2f}/20 (10/20 minimum requis).")
        self.write({'state': 'graduated'})

    def action_set_alumni(self):
        self.write({'state': 'alumni'})

    def action_draft(self):
        self.write({'state': 'draft'})

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------
    def action_view_courses(self):
        self.ensure_one()
        return {
            'name': f"Cours de {self.name}",
            'type': 'ir.actions.act_window',
            'res_model': 'eacta.course',
            'view_mode': 'kanban,list,form',
            'domain': [('id', 'in', self.course_ids.ids)],
            'context': {'create': False},
        }

    def action_view_grades(self):
        self.ensure_one()
        return {
            'name': f"Notes de {self.name}",
            'type': 'ir.actions.act_window',
            'res_model': 'eacta.course.grade',
            'view_mode': 'list,pivot,graph,form',
            'domain': [('student_id', '=', self.id)],
            'context': {'default_student_id': self.id, 'search_default_group_by_year': 1},
        }

    def action_print_report_card(self):
        return self.env.ref('eacta_school.action_report_student_card').report_action(self)

    def action_view_attendances(self):
        self.ensure_one()
        return {
            'name': f"Assiduité - {self.name}",
            'type': 'ir.actions.act_window',
            'res_model': 'eacta.attendance',
            'view_mode': 'list,calendar,pivot,form',
            'domain': [('student_id', '=', self.id)],
            'context': {
                'default_student_id': self.id,
                'default_class_id': self.current_class_id.id if self.current_class_id else False,
            },
        }

    def action_print_certificate(self):
        return self.env.ref('eacta_school.action_report_student_certificate').report_action(self)

    def action_register_fee_payment(self):
        """Ouvre l'assistant de paiement pour le premier frais impayé de l'élève."""
        self.ensure_one()
        unpaid = self.fee_ids.filtered(lambda f: f.state in ('unpaid', 'partial'))
        if not unpaid:
            raise UserError(f"Aucun frais en attente de paiement pour {self.name}.")
        fee = unpaid.sorted('due_date')[:1]
        return {
            'name': f"Encaisser un paiement - {self.name}",
            'type': 'ir.actions.act_window',
            'res_model': 'eacta.fee.payment',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_fee_id': fee.id,
                'default_amount': fee.amount_due,
            },
        }

    def action_declare_attendance(self):
        """Déclare rapidement une absence ou un retard pour cet élève."""
        self.ensure_one()
        return {
            'name': f"Signaler une absence / retard - {self.name}",
            'type': 'ir.actions.act_window',
            'res_model': 'eacta.attendance',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_student_id': self.id,
                'default_class_id': self.current_class_id.id if self.current_class_id else False,
                'default_date': fields.Date.context_today(self),
                'default_attendance_type': 'absent',
            },
        }

    def action_generate_student_fees(self):
        """Ouvre l'assistant de facturation pré-rempli pour cet élève."""
        self.ensure_one()
        return {
            'name': f"Générer les frais - {self.name}",
            'type': 'ir.actions.act_window',
            'res_model': 'eacta.fee.generate.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_class_ids': [(6, 0, [self.current_class_id.id])] if self.current_class_id else False,
                'default_student_ids': [(6, 0, [self.id])],
            },
        }

    # ------------------------------------------------------------------
    # Bulletin
    # ------------------------------------------------------------------
    def _get_report_card(self, year=None):
        """Données du bulletin scolaire pour une année (par défaut l'année affichée)."""
        self.ensure_one()
        year = year or self.selected_year or self.current_year
        klass = self.class_ids.filtered(lambda c: c.year == year)[:1]
        grades = self.course_grade_ids.filtered(lambda g: g.year == year and g.status == 'graded')
        appreciation_labels = dict(APPRECIATIONS)
        lines = []
        for course in grades.mapped('course_id').sorted('name'):
            course_grades = grades.filtered(lambda g: g.course_id == course)
            values = course_grades.mapped('grade')
            avg = round(sum(values) / len(values), 2)
            class_values = klass.grade_ids.filtered(
                lambda g: g.course_id == course and g.status == 'graded').mapped('grade') if klass else []
            lines.append({
                'course': course,
                'coefficient': course.coefficient,
                'count': len(values),
                'average': avg,
                'weighted': round(avg * course.coefficient, 2),
                'class_average': round(sum(class_values) / len(class_values), 2) if class_values else False,
                'min': min(class_values) if class_values else False,
                'max': max(class_values) if class_values else False,
                'appreciation': appreciation_labels.get(appreciation_for(avg)),
            })
        total_coef = sum(line['coefficient'] for line in lines)
        average = round(sum(line['weighted'] for line in lines) / total_coef, 2) if total_coef else 0.0
        return {
            'year': year,
            'class': klass,
            'lines': lines,
            'total_coefficient': total_coef,
            'average': average,
            'appreciation': appreciation_labels.get(appreciation_for(average)) if lines else False,
            'honor_mention': dict(self._fields['honor_mention'].selection).get(self.honor_mention) if self.honor_mention != 'none' else False,
            'absence_count': self.absence_count,
            'unjustified_absence_count': self.unjustified_absence_count,
            'late_count': self.late_count,
            'rank': self.class_rank if klass == self.current_class_id else False,
            'class_size': len(klass.student_ids) if klass else 0,
            'class_average': klass.average if klass else False,
        }

    # ------------------------------------------------------------------
    # Tableau de bord
    # ------------------------------------------------------------------
    @api.model
    def _get_dashboard_finance(self):
        Fee = self.env['eacta.student.fee']
        if not Fee.has_access('read'):
            return {'finance': False}
        today = fields.Date.context_today(self)
        open_fees = Fee.search([('state', 'in', ('unpaid', 'partial'))])
        month_start = today.replace(day=1)
        month_payments = self.env['eacta.fee.payment'].search([('date', '>=', month_start)])
        collected = sum(month_payments.filtered(lambda p: p.payment_type == 'payment').mapped('amount')) \
            - sum(month_payments.filtered(lambda p: p.payment_type == 'refund').mapped('amount'))
        return {
            'finance': True,
            'fees_due': round(sum(open_fees.mapped('amount_due')), 2),
            'fees_overdue': round(sum(open_fees.filtered(lambda f: f.due_date and f.due_date < today)
                                      .mapped('amount_due')), 2),
            'fees_collected_month': round(collected, 2),
            'currency': open_fees[:1].currency_id.symbol or self.env.company.currency_id.symbol or '',
        }

    @api.model
    def get_school_dashboard_data(self):
        Student = self.env['eacta.student']
        Class = self.env['eacta.class']
        Exam = self.env['eacta.exam']
        Grade = self.env['eacta.course.grade']
        today = fields.Date.context_today(self)

        state_labels = dict(self._fields['state'].selection)
        by_state = {state: count for state, count in Student._read_group([], ['state'], ['__count'])}
        by_gender = {gender: count for gender, count in Student._read_group([], ['gender'], ['__count'])}

        graded = Grade.search([('status', '=', 'graded')])
        values = graded.mapped('grade')
        buckets = [
            ('0 - 5', 0, 5), ('5 - 8', 5, 8), ('8 - 10', 8, 10), ('10 - 12', 10, 12),
            ('12 - 14', 12, 14), ('14 - 16', 14, 16), ('16 - 20', 16, 20.01),
        ]
        distribution = [
            {'label': label, 'count': len([v for v in values if low <= v < high]), 'passed': low >= 10}
            for label, low, high in buckets
        ]

        classes = Class.search([], order='year desc, fill_rate desc', limit=8)
        upcoming = Exam.search([('date', '>=', today), ('state', '!=', 'cancel')], order='date asc', limit=6)
        to_grade = Exam.search_count([('state', '=', 'grading')])
        top = Student.search([('grade_count', '>', 0)], order='average desc', limit=6)
        courses = self.env['eacta.course'].search([('grade', '>', 0)], order='grade desc')
        Attendance = self.env['eacta.attendance']
        today_absences = Attendance.search_count([('date', '=', today), ('attendance_type', '=', 'absent')])
        unjustified_total = Attendance.search_count([('attendance_type', '=', 'absent'), ('justified', '=', False)])

        return {
            'kpis': {
                'students': sum(by_state.values()),
                'enrolled': by_state.get('enrolled', 0),
                'drafts': by_state.get('draft', 0),
                'classes': Class.search_count([]),
                'courses': self.env['eacta.course'].search_count([]),
                'teachers': self.env['res.users'].search_count([('is_teacher', '=', True)]),
                'exams_upcoming': Exam.search_count([('date', '>=', today), ('state', '!=', 'cancel')]),
                'exams_to_grade': to_grade,
                'average': round(sum(values) / len(values), 2) if values else 0.0,
                'success_rate': round(100.0 * len([v for v in values if v >= 10]) / len(values), 1) if values else 0.0,
                'grades': len(values),
                'today_absences': today_absences,
                'unjustified_absences': unjustified_total,
                **self._get_dashboard_finance(),
            },
            'states': [
                {'key': key, 'label': state_labels[key], 'count': by_state.get(key, 0)}
                for key in state_labels
            ],
            'gender': {
                'male': by_gender.get('male', 0),
                'female': by_gender.get('female', 0),
                'other': by_gender.get('other', 0) + by_gender.get(False, 0),
            },
            'distribution': distribution,
            'classes': [{
                'id': c.id, 'name': c.display_name, 'count': c.student_count, 'capacity': c.capacity,
                'fill': min(c.fill_rate, 100), 'average': c.average,
            } for c in classes],
            'upcoming_exams': [{
                'id': e.id, 'name': e.name, 'course': e.course_id.name,
                'date': fields.Date.to_string(e.date), 'days': (e.date - today).days,
                'type': dict(e._fields['exam_type'].selection).get(e.exam_type),
                'classes': ', '.join(e.class_ids.mapped('name')),
            } for e in upcoming],
            'top_students': [{
                'id': s.id, 'name': s.name, 'code': s.code or '', 'class': s.current_class_id.display_name or '',
                'average': s.average, 'has_image': bool(s.image_128),
            } for s in top],
            'best_courses': [{'id': c.id, 'name': c.name, 'average': c.grade, 'success': c.success_rate}
                             for c in courses[:5]],
            'worst_courses': [{'id': c.id, 'name': c.name, 'average': c.grade, 'success': c.success_rate}
                              for c in courses.sorted('grade')[:5]],
        }


class ResPartner(models.Model):
    _inherit = 'res.partner'

    notify_attendance_email = fields.Boolean(
        string="Alertes d'assiduité par email", default=True,
        help="Recevoir une notification automatique par email en cas d'absence ou retard d'un enfant."
    )
    notify_attendance_sms = fields.Boolean(
        string="Alertes d'assiduité par SMS", default=False,
        help="Recevoir une notification automatique par SMS (extension multicanale)."
    )
    notify_attendance_whatsapp = fields.Boolean(
        string="Alertes d'assiduité par WhatsApp", default=False,
        help="Recevoir une notification automatique par WhatsApp (extension multicanale)."
    )

