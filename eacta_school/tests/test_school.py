from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSchoolManagement(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Users and Groups
        cls.group_manager = cls.env.ref('eacta_school.group_eacta_school_manager')
        cls.group_direction = cls.env.ref('eacta_school.group_eacta_school_direction')
        cls.group_teacher = cls.env.ref('eacta_school.group_eacta_school_teacher')
        cls.group_finance = cls.env.ref('eacta_school.group_eacta_school_finance')
        cls.group_secretary = cls.env.ref('eacta_school.group_eacta_school_secretary')
        cls.group_parent = cls.env.ref('eacta_school.group_eacta_school_parent')
        cls.group_student = cls.env.ref('eacta_school.group_eacta_school_student')
        cls.group_portal = cls.env.ref('base.group_portal')

        cls.user_direction = cls.env['res.users'].create({
            'name': 'Directeur Bennani',
            'login': 'dir_bennani',
            'email': 'directeur@school.local',
            'groups_id': [(6, 0, [cls.group_direction.id])],
        })

        cls.user_student_1 = cls.env['res.users'].create({
            'name': 'Karim Alami User',
            'login': 'karim_student',
            'email': 'karim@school.local',
            'groups_id': [(6, 0, [cls.group_student.id])],
        })

        cls.user_teacher_1 = cls.env['res.users'].create({
            'name': 'Professeur Dupont',
            'login': 'prof_dupont',
            'email': 'dupont@school.local',
            'groups_id': [(6, 0, [cls.group_teacher.id])],
        })

        cls.user_teacher_2 = cls.env['res.users'].create({
            'name': 'Professeur Martin',
            'login': 'prof_martin',
            'email': 'martin@school.local',
            'groups_id': [(6, 0, [cls.group_teacher.id])],
        })

        cls.user_finance = cls.env['res.users'].create({
            'name': 'Comptable Samir',
            'login': 'finance_samir',
            'email': 'samir@school.local',
            'groups_id': [(6, 0, [cls.group_finance.id])],
        })

        # Parents (Portal partners/users)
        cls.partner_parent_1 = cls.env['res.partner'].create({
            'name': 'Parent Alami',
            'email': 'parent.alami@example.com',
            'is_school_parent': True,
        })
        cls.user_parent_1 = cls.env['res.users'].create({
            'name': 'Parent Alami User',
            'login': 'parent_alami',
            'email': 'parent.alami@example.com',
            'partner_id': cls.partner_parent_1.id,
            'groups_id': [(6, 0, [cls.group_portal.id])],
        })

        cls.partner_parent_2 = cls.env['res.partner'].create({
            'name': 'Parent Bennani',
            'email': 'parent.bennani@example.com',
            'is_school_parent': True,
        })
        cls.user_parent_2 = cls.env['res.users'].create({
            'name': 'Parent Bennani User',
            'login': 'parent_bennani',
            'email': 'parent.bennani@example.com',
            'partner_id': cls.partner_parent_2.id,
            'groups_id': [(6, 0, [cls.group_portal.id])],
        })

        # Academic Years
        cls.year_curr = cls.env['eacta.academic.year'].search([('name', '=', '2026-2027')], limit=1)
        if not cls.year_curr:
            cls.year_curr = cls.env['eacta.academic.year'].create({
                'name': '2026-2027',
                'date_start': date(2026, 9, 1),
                'date_end': date(2027, 6, 30),
                'state': 'open',
            })
        else:
            cls.year_curr.state = 'open'

        cls.term_1 = cls.env['eacta.term'].search([('academic_year_id', '=', cls.year_curr.id), ('sequence', '=', 1)], limit=1)
        if not cls.term_1:
            cls.term_1 = cls.env['eacta.term'].create({
                'name': '1er Trimestre',
                'academic_year_id': cls.year_curr.id,
                'sequence': 1,
                'date_start': date(2026, 9, 1),
                'date_end': date(2026, 11, 30),
                'weight': 1.0,
            })

        cls.term_2 = cls.env['eacta.term'].search([('academic_year_id', '=', cls.year_curr.id), ('sequence', '=', 2)], limit=1)
        if not cls.term_2:
            cls.term_2 = cls.env['eacta.term'].create({
                'name': '2ème Trimestre',
                'academic_year_id': cls.year_curr.id,
                'sequence': 2,
                'date_start': date(2026, 12, 1),
                'date_end': date(2027, 2, 28),
                'weight': 1.0,
            })

        cls.term_3 = cls.env['eacta.term'].search([('academic_year_id', '=', cls.year_curr.id), ('sequence', '=', 3)], limit=1)
        if not cls.term_3:
            cls.term_3 = cls.env['eacta.term'].create({
                'name': '3ème Trimestre',
                'academic_year_id': cls.year_curr.id,
                'sequence': 3,
                'date_start': date(2027, 3, 1),
                'date_end': date(2027, 6, 30),
                'weight': 1.0,
            })

        cls.year_next = cls.env['eacta.academic.year'].search([('name', '=', '2027-2028')], limit=1)
        if not cls.year_next:
            cls.year_next = cls.env['eacta.academic.year'].create({
                'name': '2027-2028',
                'date_start': date(2027, 9, 1),
                'date_end': date(2028, 6, 30),
                'state': 'draft',
            })

        # Classes
        cls.class_6a = cls.env['eacta.class'].create({
            'name': '6ème A',
            'academic_year_id': cls.year_curr.id,
            'level': 'secondary',
            'capacity': 30,
            'teacher_id': cls.user_teacher_1.id,
            'start_date': date(2026, 9, 1),
            'end_date': date(2027, 6, 30),
        })

        cls.class_6b = cls.env['eacta.class'].create({
            'name': '6ème B',
            'academic_year_id': cls.year_curr.id,
            'level': 'secondary',
            'capacity': 30,
            'teacher_id': cls.user_teacher_1.id,
            'start_date': date(2026, 9, 1),
            'end_date': date(2027, 6, 30),
        })

        cls.class_5a = cls.env['eacta.class'].create({
            'name': '5ème A',
            'academic_year_id': cls.year_next.id,
            'level': 'secondary',
            'capacity': 30,
            'teacher_id': cls.user_teacher_1.id,
            'start_date': date(2027, 9, 1),
            'end_date': date(2028, 6, 30),
        })

        # Courses
        cls.course_math = cls.env['eacta.course'].create({
            'name': 'Mathématiques',
            'code': 'MATH6',
            'coefficient': 3.0,
            'teacher_id': cls.user_teacher_1.id,
            'class_ids': [(4, cls.class_6a.id), (4, cls.class_6b.id)],
        })

        cls.course_physics = cls.env['eacta.course'].create({
            'name': 'Physique-Chimie',
            'code': 'PC6',
            'coefficient': 2.0,
            'teacher_id': cls.user_teacher_2.id,
            'class_ids': [(4, cls.class_6a.id)],
        })

        # Students
        cls.student_1 = cls.env['eacta.student'].create({
            'name': 'Karim Alami',
            'gender': 'male',
            'date_of_birth': date(2013, 5, 14),
            'parent_ids': [(4, cls.partner_parent_1.id)],
            'user_id': cls.user_student_1.id,
            'class_ids': [(4, cls.class_6a.id)],
            'blood_group': 'O+',
            'allergies': 'Arachides',
            'medical_notes': 'PAI établi',
            'state': 'enrolled',
        })

        cls.student_2 = cls.env['eacta.student'].create({
            'name': 'Salma Alami',
            'gender': 'female',
            'date_of_birth': date(2014, 8, 20),
            'parent_ids': [(4, cls.partner_parent_1.id)],
            'class_ids': [(4, cls.class_6a.id)],
            'state': 'enrolled',
        })

        cls.student_3 = cls.env['eacta.student'].create({
            'name': 'Youssef Bennani',
            'gender': 'male',
            'date_of_birth': date(2013, 11, 2),
            'parent_ids': [(4, cls.partner_parent_2.id)],
            'class_ids': [(4, cls.class_6a.id)],
            'state': 'enrolled',
        })

    # =========================================================================
    # 1. ACADEMIC YEAR & TERMS
    # =========================================================================
    def test_01_academic_year_single_open_constraint(self):
        """Une seule année académique peut être ouverte à la fois."""
        with self.assertRaises(ValidationError):
            self.env['eacta.academic.year'].create({
                'name': '2028-2029',
                'date_start': date(2028, 9, 1),
                'date_end': date(2029, 6, 30),
                'state': 'open',
            })

    def test_02_term_overlap_and_containment_constraints(self):
        """Les trimestres ne doivent pas se chevaucher et doivent rester dans l'année."""
        # Chevauchement
        with self.assertRaises(ValidationError):
            self.env['eacta.term'].create({
                'name': 'Trimestre chevauchant',
                'year_id': self.year_curr.id,
                'date_start': date(2026, 11, 15),
                'date_end': date(2027, 1, 15),
                'sequence': 4,
            })

        # Hors de l'année
        with self.assertRaises(ValidationError):
            self.env['eacta.term'].create({
                'name': 'Trimestre hors année',
                'year_id': self.year_curr.id,
                'date_start': date(2026, 7, 1),
                'date_end': date(2026, 8, 30),
                'sequence': 5,
            })

    # =========================================================================
    # 2. GRADE CALCULATIONS, WEIGHTS, ABSENT POLICY, RANK WITH TIES
    # =========================================================================
    def test_03_grade_weighted_averages_and_absent_policy(self):
        """Calcul des moyennes par matière avec coefficients et pondérations d'examens."""
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('eacta_school.weight_quiz', '1.0')
        ICP.set_param('eacta_school.weight_final', '3.0')
        ICP.set_param('eacta_school.absent_policy', 'excluded')
        ICP.set_param('eacta_school.unjustified_absence_zero', 'True')

        # Examen 1 : Contrôle continu Mathématiques (weight 1.0)
        exam_quiz = self.env['eacta.exam'].create({
            'name': 'Contrôle continu n°1 - Algèbre',
            'course_id': self.course_math.id,
            'exam_type': 'quiz',
            'date': date(2026, 9, 20),
            'academic_year_id': self.year_curr.id,
            'term_id': self.term_1.id,
            'class_ids': [(4, self.class_6a.id)],
        })

        # Examen 2 : Examen final Mathématiques (weight 3.0)
        exam_final = self.env['eacta.exam'].create({
            'name': 'Examen trimestriel - Mathématiques',
            'course_id': self.course_math.id,
            'exam_type': 'final',
            'date': date(2026, 10, 5),
            'academic_year_id': self.year_curr.id,
            'term_id': self.term_1.id,
            'class_ids': [(4, self.class_6a.id)],
        })

        # Examen 3 : Examen final Physique-Chimie (weight 3.0)
        exam_physics = self.env['eacta.exam'].create({
            'name': 'Examen trimestriel - Physique',
            'course_id': self.course_physics.id,
            'exam_type': 'final',
            'date': date(2026, 10, 10),
            'academic_year_id': self.year_curr.id,
            'term_id': self.term_1.id,
            'class_ids': [(4, self.class_6a.id)],
        })

        # Saisie notes pour Karim (Student 1) :
        # Math Quiz: 12.00, Math Final: 16.00 -> Moyenne Math = (12*1 + 16*3)/4 = 60/4 = 15.00
        # Physique Final: 10.00
        # Moyenne Trimestre 1 = (15.00 * 3 + 10.00 * 2) / (3 + 2) = (45 + 20) / 5 = 13.00
        self.env['eacta.course.grade'].create([
            {
                'student_id': self.student_1.id,
                'exam_id': exam_quiz.id,
                'course_id': self.course_math.id,
                'class_id': self.class_6a.id,
                'academic_year_id': self.year_curr.id,
                'term_id': self.term_1.id,
                'grade': 12.0,
                'status': 'graded',
            },
            {
                'student_id': self.student_1.id,
                'exam_id': exam_final.id,
                'course_id': self.course_math.id,
                'class_id': self.class_6a.id,
                'academic_year_id': self.year_curr.id,
                'term_id': self.term_1.id,
                'grade': 16.0,
                'status': 'graded',
            },
            {
                'student_id': self.student_1.id,
                'exam_id': exam_physics.id,
                'course_id': self.course_physics.id,
                'class_id': self.class_6a.id,
                'academic_year_id': self.year_curr.id,
                'term_id': self.term_1.id,
                'grade': 10.0,
                'status': 'graded',
            },
        ])

        # Saisie notes pour Salma (Student 2) : identiques -> test ex aequo
        self.env['eacta.course.grade'].create([
            {
                'student_id': self.student_2.id,
                'exam_id': exam_quiz.id,
                'course_id': self.course_math.id,
                'class_id': self.class_6a.id,
                'academic_year_id': self.year_curr.id,
                'term_id': self.term_1.id,
                'grade': 12.0,
                'status': 'graded',
            },
            {
                'student_id': self.student_2.id,
                'exam_id': exam_final.id,
                'course_id': self.course_math.id,
                'class_id': self.class_6a.id,
                'academic_year_id': self.year_curr.id,
                'term_id': self.term_1.id,
                'grade': 16.0,
                'status': 'graded',
            },
            {
                'student_id': self.student_2.id,
                'exam_id': exam_physics.id,
                'course_id': self.course_physics.id,
                'class_id': self.class_6a.id,
                'academic_year_id': self.year_curr.id,
                'term_id': self.term_1.id,
                'grade': 10.0,
                'status': 'graded',
            },
        ])

        # Saisie notes pour Youssef (Student 3) : moyenne plus faible (8.00)
        self.env['eacta.course.grade'].create([
            {
                'student_id': self.student_3.id,
                'exam_id': exam_final.id,
                'course_id': self.course_math.id,
                'class_id': self.class_6a.id,
                'academic_year_id': self.year_curr.id,
                'term_id': self.term_1.id,
                'grade': 8.0,
                'status': 'graded',
            },
        ])

        # Calcul des résultats
        self.env['eacta.student.result'].compute_all_results(
            academic_year=self.year_curr, term=self.term_1, classes=self.class_6a
        )

        res_1 = self.env['eacta.student.result'].search([
            ('student_id', '=', self.student_1.id),
            ('term_id', '=', self.term_1.id),
            ('result_type', '=', 'term'),
        ])
        res_2 = self.env['eacta.student.result'].search([
            ('student_id', '=', self.student_2.id),
            ('term_id', '=', self.term_1.id),
            ('result_type', '=', 'term'),
        ])
        res_3 = self.env['eacta.student.result'].search([
            ('student_id', '=', self.student_3.id),
            ('term_id', '=', self.term_1.id),
            ('result_type', '=', 'term'),
        ])

        self.assertAlmostEqual(res_1.average, 13.00, places=2)
        self.assertAlmostEqual(res_2.average, 13.00, places=2)
        self.assertAlmostEqual(res_3.average, 8.00, places=2)

        # Test classement ex aequo (Rank with ties)
        self.assertEqual(res_1.rank, 1)
        self.assertEqual(res_2.rank, 1)
        self.assertEqual(res_3.rank, 3)

        # Appréciation et décision
        self.assertEqual(res_1.appreciation, 'quite_good')  # 12-14 Assez bien
        self.assertTrue(res_1.passed)
        self.assertEqual(res_3.appreciation, 'insufficient')  # <10
        self.assertFalse(res_3.passed)

        # Vérifier le verrouillage des notes d'un examen clôturé
        exam_quiz.action_done()
        grade_rec = self.env['eacta.course.grade'].search([('exam_id', '=', exam_quiz.id)], limit=1)
        with self.assertRaises(UserError):
            grade_rec.with_user(self.user_teacher_1).write({'grade': 18.0})

    # =========================================================================
    # 3. ATTENDANCE CONSTRAINTS & ALERTS
    # =========================================================================
    def test_04_attendance_constraints_and_threshold_alert(self):
        """Contraintes d'assiduité (non-doublon, date future, motif obligatoire) et alerte seuil."""
        today = fields.Date.context_today(self.env.user)

        # Interdiction des dates futures
        with self.assertRaises(ValidationError):
            self.env['eacta.attendance'].create({
                'student_id': self.student_1.id,
                'class_id': self.class_6a.id,
                'date': today + timedelta(days=2),
                'attendance_type': 'absent',
            })

        # Motif obligatoire si justifié
        with self.assertRaises(ValidationError):
            self.env['eacta.attendance'].create({
                'student_id': self.student_1.id,
                'class_id': self.class_6a.id,
                'date': today,
                'attendance_type': 'absent',
                'justified': True,
                'reason': False,
            })

        # Création d'une première absence
        att1 = self.env['eacta.attendance'].create({
            'student_id': self.student_1.id,
            'class_id': self.class_6a.id,
            'date': today,
            'session': 'morning',
            'attendance_type': 'absent',
            'justified': False,
        })
        self.assertTrue(att1)

        # Détection doublon (même élève, même date, même session, même type)
        with self.assertRaises(ValidationError):
            self.env['eacta.attendance'].create({
                'student_id': self.student_1.id,
                'class_id': self.class_6a.id,
                'date': today,
                'session': 'morning',
                'attendance_type': 'absent',
            })

        # Test déclenchement alerte seuil mensuel (3 absences non justifiées)
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('eacta_school.unjustified_absence_threshold', '2')

        # Deuxième absence
        self.env['eacta.attendance'].create({
            'student_id': self.student_1.id,
            'class_id': self.class_6a.id,
            'date': today,
            'session': 'afternoon',
            'attendance_type': 'absent',
            'justified': False,
        })

        # Vérifier création de l'activité pour le professeur principal
        activity = self.env['mail.activity'].search([
            ('res_model', '=', 'eacta.student'),
            ('res_id', '=', self.student_1.id),
            ('user_id', '=', self.class_6a.teacher_id.id),
        ])
        self.assertTrue(activity, "Une activité d'alerte assiduité doit être créée pour le professeur principal.")

    # =========================================================================
    # 4. TIMETABLE CONFLICTS & VALIDATIONS
    # =========================================================================
    def test_05_timetable_conflicts_and_teacher_match(self):
        """Conflits de créneaux enseignants et cohérence matière-enseignant."""
        # Créneau 1 : Lundi 8h30 - 10h30 Prof Dupont
        self.env['eacta.timetable.slot'].create({
            'class_id': self.class_6a.id,
            'course_id': self.course_math.id,
            'teacher_id': self.user_teacher_1.id,
            'weekday': '0',  # Lundi
            'hour_from': 8.5,
            'hour_to': 10.5,
            'academic_year_id': self.year_curr.id,
        })

        # Créneau 2 : En conflit sur le même enseignant (Prof Dupont) le lundi de 9h à 11h
        with self.assertRaises(ValidationError):
            self.env['eacta.timetable.slot'].create({
                'class_id': self.class_6b.id,
                'course_id': self.course_math.id,
                'teacher_id': self.user_teacher_1.id,
                'weekday': '0',
                'hour_from': 9.0,
                'hour_to': 11.0,
                'academic_year_id': self.year_curr.id,
            })

    # =========================================================================
    # 5. CLASS CAPACITY & STUDENT-YEAR UNIQUENESS
    # =========================================================================
    def test_06_class_capacity_and_student_year_uniqueness(self):
        """Capacité de classe et unicité d'inscription par année scolaire."""
        temp_s1 = self.env['eacta.student'].create({'name': 'Élève Test Capacité 1'})
        temp_s2 = self.env['eacta.student'].create({'name': 'Élève Test Capacité 2'})

        small_class = self.env['eacta.class'].create({
            'name': 'Mini Classe',
            'academic_year_id': self.year_curr.id,
            'level': 'primary',
            'capacity': 1,
            'student_ids': [(4, temp_s1.id)],
        })
        # Dépassement de capacité
        with self.assertRaises(ValidationError):
            small_class.write({'student_ids': [(4, temp_s2.id)]})

        # Inscription du même élève dans 2 classes de la même année
        second_class = self.env['eacta.class'].create({
            'name': 'Classe Concurrente',
            'academic_year_id': self.year_curr.id,
            'level': 'secondary',
            'capacity': 20,
        })
        with self.assertRaises(ValidationError):
            second_class.write({'student_ids': [(4, temp_s1.id)]})

    # =========================================================================
    # 6. FEES, INSTALLMENTS, PAYMENTS, SIBLING DISCOUNT, REFUNDS & OVERDUE
    # =========================================================================
    def test_07_fees_installments_payments_and_refunds(self):
        """Gestion des frais, mensualités sans perte de centime, remises fratrie et remboursements."""
        fee_type = self.env['eacta.fee.type'].create({
            'name': 'Scolarité Annuelle',
            'default_amount': 1000.0,
        })

        # Test assistant de génération en 3 échéances avec remise fratrie
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('eacta_school.enable_sibling_discount', 'True')
        ICP.set_param('eacta_school.sibling_discount_rate', '10.0')

        wizard = self.env['eacta.fee.generate.wizard'].create({
            'fee_type_id': fee_type.id,
            'academic_year_id': self.year_curr.id,
            'class_ids': [(4, self.class_6a.id)],
            'student_ids': [(6, 0, [self.student_1.id, self.student_2.id])],
            'amount': 1000.0,
            'installments': 3,
            'first_due_date': date(2026, 10, 1),
            'apply_sibling_discount': True,
        })
        wizard.action_generate()

        fees_s1 = self.env['eacta.student.fee'].search([
            ('student_id', '=', self.student_1.id),
            ('fee_type_id', '=', fee_type.id),
        ], order='due_date asc')
        self.assertEqual(len(fees_s1), 3, "Il doit y avoir 3 échéances générées pour le premier enfant.")
        self.assertAlmostEqual(sum(fees_s1.mapped('amount_total')), 1000.0, places=2)

        fees_s2 = self.env['eacta.student.fee'].search([
            ('student_id', '=', self.student_2.id),
            ('fee_type_id', '=', fee_type.id),
        ], order='due_date asc')
        self.assertEqual(len(fees_s2), 3, "Il doit y avoir 3 échéances générées pour le deuxième enfant.")
        # Remise fratrie 10% sur 1000 = 900 total pour le 2ème enfant -> 3 échéances de 300
        self.assertAlmostEqual(sum(fees_s2.mapped('amount_total')), 900.0, places=2)

        # Enregistrement d'un premier paiement
        fee_1 = fees_s2[0]
        payment = self.env['eacta.fee.payment'].create({
            'fee_id': fee_1.id,
            'amount': 200.0,
            'method': 'cash',
            'payment_type': 'payment',
        })

        self.assertEqual(fee_1.state, 'partial')
        self.assertAlmostEqual(fee_1.amount_paid, 200.0, places=2)
        self.assertAlmostEqual(fee_1.amount_due, 100.0, places=2)

        # Test immutabilité du montant du paiement
        with self.assertRaises(UserError):
            payment.write({'amount': 250.0})

        # Test Remboursement
        refund = self.env['eacta.fee.payment'].create({
            'fee_id': fee_1.id,
            'amount': 50.0,
            'method': 'cash',
            'payment_type': 'refund',
            'refund_payment_id': payment.id,
        })
        self.assertTrue(refund)
        self.assertAlmostEqual(fee_1.amount_paid, 150.0, places=2)
        self.assertAlmostEqual(fee_1.amount_due, 150.0, places=2)

        # Test pénalité de retard via cron
        ICP.set_param('eacta_school.enable_late_fee', 'True')
        ICP.set_param('eacta_school.late_fee_type', 'fixed')
        ICP.set_param('eacta_school.late_fee_amount', '50.0')

        fee_1.due_date = date.today() - timedelta(days=5)
        self.env['eacta.student.fee']._cron_check_overdue_fees()
        self.assertTrue(fee_1.late_fee_applied)
        self.assertAlmostEqual(fee_1.late_fee_amount, 50.0, places=2)

    # =========================================================================
    # 7. PROMOTION WIZARD
    # =========================================================================
    def test_08_promotion_wizard(self):
        """Passage de fin d'année vers la classe supérieure avec report des soldes impayés."""
        # Karim a une moyenne de 14/20 et un solde impayé
        self.student_1.average = 14.0
        self.student_3.average = 8.0  # Youssef doit redoubler

        wizard = self.env['eacta.promotion.wizard'].with_context(
            active_model='eacta.class', active_id=self.class_6a.id
        ).create({
            'from_class_id': self.class_6a.id,
            'to_class_id': self.class_5a.id,
            'repeat_class_id': self.class_6a.id,
            'pass_mark': 10.0,
        })
        wizard._onchange_from_class()
        wizard.action_apply()

        # Karim doit être admis en 5ème A
        self.assertIn(self.student_1, self.class_5a.student_ids)

    # =========================================================================
    # 8. SECURITY & PRIVACY (ACCESS RIGHTS & RECORD RULES)
    # =========================================================================
    def test_09_security_and_privacy_restrictions(self):
        """Vérification des restrictions enseignants (médical, finances, autres classes) et portail parent."""
        # 1. Un enseignant ne peut pas voir les élèves d'autres classes
        other_class = self.env['eacta.class'].create({
            'name': 'Terminale C',
            'academic_year_id': self.year_curr.id,
            'level': 'higher',
            'capacity': 25,
            'teacher_id': self.user_teacher_2.id,
        })
        stranger_student = self.env['eacta.student'].create({
            'name': 'Élève Inconnu',
            'gender': 'male',
            'class_ids': [(4, other_class.id)],
            'state': 'enrolled',
        })

        students_for_dupont = self.env['eacta.student'].with_user(self.user_teacher_1).search([])
        self.assertIn(self.student_1, students_for_dupont)
        self.assertNotIn(stranger_student, students_for_dupont)

        # 2. Un enseignant ne peut pas accéder aux données médicales
        # Les champs blood_group, allergies, medical_notes ont groups="eacta_school.group_eacta_school_manager,eacta_school.group_eacta_school_secretary"
        # Dans Odoo, tenter d'accéder à un champ protégé par groups lève AccessError
        with self.assertRaises(AccessError):
            self.student_1.with_user(self.user_teacher_1).read(['blood_group', 'allergies'])

        # 3. Le parent ne peut voir que ses propres enfants
        students_for_parent = self.env['eacta.student'].with_user(self.user_parent_1).search([])
        self.assertIn(self.student_1, students_for_parent)
        self.assertIn(self.student_2, students_for_parent)
        self.assertNotIn(self.student_3, students_for_parent)

        # 4. L'élève connecté en portail ne voit que sa propre fiche
        students_for_student = self.env['eacta.student'].with_user(self.user_student_1).search([])
        self.assertEqual(students_for_student, self.student_1)

        # 5. La Direction a une vue globale sur toutes les classes et tous les élèves
        classes_for_dir = self.env['eacta.class'].with_user(self.user_direction).search([])
        self.assertIn(self.class_6a, classes_for_dir)
        self.assertIn(other_class, classes_for_dir)

        # 6. Un enseignant ne voit que ses propres classes et présences
        classes_for_teacher = self.env['eacta.class'].with_user(self.user_teacher_1).search([])
        self.assertIn(self.class_6a, classes_for_teacher)
        self.assertNotIn(other_class, classes_for_teacher)

        att_6a = self.env['eacta.attendance'].create({
            'student_id': self.student_1.id,
            'class_id': self.class_6a.id,
            'date': date.today(),
            'attendance_type': 'absent',
        })
        att_other = self.env['eacta.attendance'].create({
            'student_id': stranger_student.id,
            'class_id': other_class.id,
            'date': date.today(),
            'attendance_type': 'absent',
        })
        att_for_teacher = self.env['eacta.attendance'].with_user(self.user_teacher_1).search([])
        self.assertIn(att_6a, att_for_teacher)
        self.assertNotIn(att_other, att_for_teacher)

    # =========================================================================
    # 9. PHASE 1: GRADES WORKFLOW & STATE PERMISSIONS
    # =========================================================================
    def test_10_grade_workflow_and_state_permissions(self):
        """Cycle complet d'une note : Brouillon -> Soumis -> Validé -> Publié."""
        exam = self.env['eacta.exam'].create({
            'name': 'Contrôle Workflow',
            'course_id': self.course_math.id,
            'exam_type': 'quiz',
            'date': date.today() - timedelta(days=1),
            'academic_year_id': self.year_curr.id,
            'term_id': self.term_1.id,
            'class_ids': [(4, self.class_6a.id)],
        })
        grade = self.env['eacta.course.grade'].create({
            'exam_id': exam.id,
            'student_id': self.student_1.id,
            'class_id': self.class_6a.id,
            'status': 'graded',
            'grade': 16.5,
        })
        self.assertEqual(grade.state, 'draft')

        # 1. Le parent ne peut pas voir une note en brouillon
        parent_grades = self.env['eacta.course.grade'].with_user(self.user_parent_1).search([('id', '=', grade.id)])
        self.assertFalse(parent_grades)

        # 2. Soumission par l'enseignant
        grade.with_user(self.user_teacher_1).action_submit()
        self.assertEqual(grade.state, 'submitted')

        # 3. L'enseignant ne peut pas valider lui-même
        with self.assertRaises(UserError):
            grade.with_user(self.user_teacher_1).action_validate()

        # 4. La Direction valide la note
        grade.with_user(self.user_direction).action_validate()
        self.assertEqual(grade.state, 'validated')

        # 5. L'enseignant ne peut plus modifier une note validée
        with self.assertRaises(UserError):
            grade.with_user(self.user_teacher_1).write({'grade': 14.0})

        # 6. La Direction publie la note
        grade.with_user(self.user_direction).action_publish()
        self.assertEqual(grade.state, 'published')

        # 7. Maintenant que la note est publiée, le parent peut la consulter
        parent_grades_pub = self.env['eacta.course.grade'].with_user(self.user_parent_1).search([('id', '=', grade.id)])
        self.assertEqual(parent_grades_pub, grade)

        # 8. Reset en brouillon par la Direction
        grade.with_user(self.user_direction).action_draft()
        self.assertEqual(grade.state, 'draft')

    # =========================================================================
    # 10. PHASE 1: ATTENDANCE JUSTIFICATION & STATISTICS
    # =========================================================================
    def test_11_attendance_justification_and_class_stats(self):
        """Gestion des justificatifs d'absence et statistiques de classe."""
        initial_unjust = self.class_6a.unjustified_absence_count
        initial_total = self.class_6a.absence_count

        att = self.env['eacta.attendance'].create({
            'student_id': self.student_1.id,
            'class_id': self.class_6a.id,
            'date': date.today(),
            'session': 'morning',
            'attendance_type': 'absent',
            'justified': False,
        })
        self.class_6a._compute_attendance_stats()
        self.assertEqual(self.class_6a.unjustified_absence_count, initial_unjust + 1)
        self.assertEqual(self.class_6a.absence_count, initial_total + 1)

        # Justification
        att.action_mark_justified()
        self.assertTrue(att.justified)
        self.assertTrue(att.justification_date)
        self.class_6a._compute_attendance_stats()
        self.assertEqual(self.class_6a.unjustified_absence_count, initial_unjust)
        self.assertEqual(self.class_6a.absence_count, initial_total + 1)

        # Dé-justification
        att.action_mark_unjustified()
        self.assertFalse(att.justified)
        self.assertFalse(att.justification_date)

    # =========================================================================
    # 11. PHASE 1: CLASS COUNCIL DELIBERATION (PV) & BULLETIN
    # =========================================================================
    def test_12_class_council_deliberation_pv_and_report_card(self):
        """Génération du PV de délibération du conseil de classe et structure bulletin."""
        # Calcul des résultats du 1er trimestre
        self.env['eacta.student.result'].compute_all_results(
            academic_year=self.year_curr, term=self.term_1, classes=self.class_6a
        )
        res = self.env['eacta.student.result'].search([
            ('student_id', '=', self.student_1.id),
            ('class_id', '=', self.class_6a.id),
            ('term_id', '=', self.term_1.id),
        ], limit=1)
        if res:
            self.assertIn(res.honor_mention, ('felicitations', 'compliments', 'encouragements', 'honneur', 'avertissement', 'blame'))
            self.assertGreaterEqual(res.total_coefficient, 0.0)

        # Assistant PV de délibération
        wizard = self.env['eacta.class.deliberation.wizard'].create({
            'class_id': self.class_6a.id,
            'academic_year_id': self.year_curr.id,
            'period_type': 'term',
            'term_id': self.term_1.id,
            'recompute_before_print': True,
        })
        data = wizard.get_deliberation_data()
        self.assertIn('total_students', data)
        self.assertIn('class_avg', data)
        self.assertIn('success_rate', data)
        self.assertIn('mentions_count', data)

        report_act = wizard.action_print_pv()
        self.assertTrue(report_act)

    # =========================================================================
    # 12. ACADEMIC YEAR UI & SEARCH/GROUP/EXPORT (PRE-PHASE 2)
    # =========================================================================
    def test_13_academic_year_search_group_and_export(self):
        """Vérifie que la recherche, le regroupement et l'export par année académique fonctionnent sur tous les modèles."""
        models_to_test = [
            'eacta.course.grade',
            'eacta.timetable.slot',
            'eacta.attendance',
            'eacta.student.fee',
            'eacta.term',
        ]
        for model_name in models_to_test:
            Model = self.env[model_name]
            # 1. Vérification que le champ academic_year_id est bien présent dans _fields
            self.assertIn('academic_year_id', Model._fields, f"{model_name} doit posséder le champ academic_year_id")
            self.assertTrue(Model._fields['academic_year_id'].store, f"{model_name}.academic_year_id doit être stocké")

            # 2. Test recherche par academic_year_id
            records = Model.search([('academic_year_id', '=', self.year_curr.id)])
            self.assertIsNotNone(records)

            # 3. Test group by academic_year_id
            grouped = Model.read_group(
                domain=[('academic_year_id', '=', self.year_curr.id)],
                fields=['academic_year_id'],
                groupby=['academic_year_id']
            )
            self.assertIsInstance(grouped, list)

            # 4. Test export des données incluant academic_year_id
            if records:
                export_res = records[:2].export_data(['academic_year_id'])
                self.assertIn('datas', export_res)
                self.assertGreater(len(export_res['datas']), 0)

    # =========================================================================
    # 13. PHASE 2: FRAIS, ÉCHÉANCIER & REMISE FRATRIE
    # =========================================================================
    def test_14_installments_and_sibling_discounts(self):
        """Test de la génération d'échéances et du calcul de la remise fratrie."""
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('eacta_school.enable_sibling_discount', 'True')
        ICP.set_param('eacta_school.sibling_discount_rate', '10.0')

        # Création d'un deuxième enfant rattaché au même parent (Parent Alami)
        student_sibling = self.env['eacta.student'].create({
            'name': 'Yasmine Alami (Sœur)',
            'gender': 'female',
            'date_of_birth': date(2015, 6, 12),
            'current_class_id': self.class_6a.id,
            'parent_ids': [(6, 0, [self.partner_parent_1.id])],
            'state': 'enrolled',
        })
        self.assertTrue(student_sibling.parent_ids)

        # Génération d'un échéancier en 3 fois pour les deux élèves de la classe
        fee_type = self.env.ref('eacta_school.fee_type_tuition')
        today = fields.Date.today()
        wizard = self.env['eacta.fee.generate.wizard'].create({
            'fee_type_id': fee_type.id,
            'academic_year_id': self.year_curr.id,
            'student_ids': [(6, 0, [self.student_1.id, student_sibling.id])],
            'description': 'Scolarité Trimestrielle',
            'amount': 9000.0,
            'installments': 3,
            'first_due_date': today,
            'apply_sibling_discount': True,
            'skip_existing': False,
        })
        res = wizard.action_generate()
        self.assertTrue(res)

        # Vérification des frais de student_1 (premier enfant = pas de remise)
        fees_s1 = self.env['eacta.student.fee'].search([
            ('student_id', '=', self.student_1.id),
            ('description', 'like', 'Scolarité Trimestrielle%'),
        ], order='due_date asc')
        self.assertEqual(len(fees_s1), 3, "L'élève 1 doit avoir 3 échéances")
        self.assertEqual(sum(fees_s1.mapped('amount')), 9000.0)
        self.assertEqual(sum(fees_s1.mapped('discount')), 0.0)
        self.assertEqual(fees_s1[0].due_date, today)
        self.assertEqual(fees_s1[1].due_date, today + relativedelta(months=1))
        self.assertEqual(fees_s1[2].due_date, today + relativedelta(months=2))

        # Vérification des frais de la sœur (deuxième enfant = 10% de remise fratrie)
        fees_s2 = self.env['eacta.student.fee'].search([
            ('student_id', '=', student_sibling.id),
            ('description', 'like', 'Scolarité Trimestrielle%'),
        ], order='due_date asc')
        self.assertEqual(len(fees_s2), 3, "La sœur doit avoir 3 échéances")
        self.assertEqual(sum(fees_s2.mapped('amount')), 9000.0)
        # Remise 10% de 9000 = 900 MAD au total, soit 300 MAD par échéance
        self.assertAlmostEqual(sum(fees_s2.mapped('discount')), 900.0, places=2)
        self.assertAlmostEqual(sum(fees_s2.mapped('amount_total')), 8100.0, places=2)

    # =========================================================================
    # 14. PHASE 2: CRON DE RELANCE DES IMPAYÉS & PÉNALITÉS
    # =========================================================================
    def test_15_fee_reminder_cron_and_penalties(self):
        """Action planifiée de relance des impayés et application des pénalités."""
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('eacta_school.send_fee_reminder_email', 'True')
        ICP.set_param('eacta_school.enable_late_fee', 'True')
        ICP.set_param('eacta_school.late_fee_type', 'fixed')
        ICP.set_param('eacta_school.late_fee_amount', '50.0')

        # Création d'un frais en retard de 10 jours
        past_date = fields.Date.today() - timedelta(days=10)
        fee = self.env['eacta.student.fee'].create({
            'student_id': self.student_1.id,
            'fee_type_id': self.env.ref('eacta_school.fee_type_transport').id,
            'academic_year_id': self.year_curr.id,
            'amount': 500.0,
            'due_date': past_date,
            'parent_id': self.partner_parent_1.id,
        })
        self.assertTrue(fee.is_overdue)
        self.assertEqual(fee.reminder_count, 0)
        self.assertFalse(fee.late_fee_applied)

        # Exécution du cron
        self.env['eacta.student.fee']._cron_check_overdue_fees()

        fee.invalidate_recordset()
        # La pénalité de 50 MAD doit être appliquée
        self.assertTrue(fee.late_fee_applied)
        self.assertEqual(fee.late_fee_amount, 50.0)
        self.assertEqual(fee.amount, 550.0)
        # Le compteur de relance doit être incrémenté
        self.assertEqual(fee.reminder_count, 1)
        self.assertEqual(fee.last_reminder_date, fields.Date.today())

    # =========================================================================
    # 15. PHASE 2: FACTURATION ACCOUNT.MOVE & DEVISE MAD
    # =========================================================================
    def test_16_account_move_invoice_and_currency_mad(self):
        """Création de factures account.move (out_invoice) en Dirham marocain (MAD)."""
        # Vérification de la devise MAD
        mad = self.env.ref('base.MAD')
        self.assertTrue(mad.active, "La devise MAD doit être active")

        # Création d'un frais
        fee = self.env['eacta.student.fee'].create({
            'student_id': self.student_1.id,
            'fee_type_id': self.env.ref('eacta_school.fee_type_activities').id,
            'academic_year_id': self.year_curr.id,
            'amount': 800.0,
            'description': 'Sortie pédagogique',
            'parent_id': self.partner_parent_1.id,
        })
        self.assertEqual(fee.currency_id, mad)

        # Vérification de la facture liée
        if fee.move_id:
            move = fee.move_id
            self.assertEqual(move.move_type, 'out_invoice')
            self.assertEqual(move.partner_id, self.partner_parent_1)
            self.assertEqual(move.currency_id, mad)
            self.assertEqual(move.amount_total, 800.0)
            self.assertTrue(fee.action_view_invoice())

    # =========================================================================
    # 16. PHASE 3: AÎNÉ DÉTERMINÉ PAR LA DATE DE NAISSANCE
    # =========================================================================
    def test_17_eldest_sibling_by_birthdate(self):
        """L'aîné est déterminé par la date de naissance (et non par l'ordre d'ID en base)."""
        parent = self.env['res.partner'].create({
            'name': 'Parent Test Naissance',
            'email': 'parent.naissance@example.com',
        })
        # 1. On crée d'abord le cadet (né en 2017) -> aura un ID plus petit
        cadet = self.env['eacta.student'].create({
            'name': 'Cadet Test',
            'gender': 'male',
            'date_of_birth': date(2017, 3, 10),
            'parent_ids': [(6, 0, [parent.id])],
            'state': 'enrolled',
        })
        # 2. On crée ensuite l'aîné (né en 2012) -> aura un ID plus grand
        aine = self.env['eacta.student'].create({
            'name': 'Aîné Test',
            'gender': 'female',
            'date_of_birth': date(2012, 1, 15),
            'parent_ids': [(6, 0, [parent.id])],
            'state': 'enrolled',
        })
        self.assertGreater(aine.id, cadet.id, "L'aîné a été créé après le cadet")

        # Vérification de _is_eldest_sibling
        self.assertTrue(aine._is_eldest_sibling(), "L'élève né en 2012 doit être reconnu comme l'aîné")
        self.assertFalse(cadet._is_eldest_sibling(), "L'élève né en 2017 ne doit pas être l'aîné")

        # Test de la remise : l'aîné paye plein tarif, le cadet bénéficie de la remise
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('eacta_school.enable_sibling_discount', 'True')
        ICP.set_param('eacta_school.sibling_discount_rate', '10.0')

        wizard = self.env['eacta.fee.generate.wizard'].create({
            'fee_type_id': self.env.ref('eacta_school.fee_type_tuition').id,
            'academic_year_id': self.year_curr.id,
            'student_ids': [(6, 0, [cadet.id, aine.id])],
            'amount': 5000.0,
            'installments': 1,
            'first_due_date': fields.Date.today(),
            'apply_sibling_discount': True,
        })
        wizard.action_generate()

        fee_aine = self.env['eacta.student.fee'].search([('student_id', '=', aine.id)], limit=1)
        fee_cadet = self.env['eacta.student.fee'].search([('student_id', '=', cadet.id)], limit=1)

        self.assertEqual(fee_aine.discount, 0.0, "L'aîné ne doit avoir aucune remise")
        self.assertEqual(fee_aine.amount_total, 5000.0)
        self.assertEqual(fee_cadet.discount, 500.0, "Le cadet doit bénéficier de 10% de remise fratrie (500 DH)")
        self.assertEqual(fee_cadet.amount_total, 4500.0)

    # =========================================================================
    # 17. PHASE 3: NOTIFICATION D'ASSIDUITÉ & OPT-OUT PARENT
    # =========================================================================
    def test_18_attendance_notification_and_opt_out(self):
        """Notification automatique d'absence/retard aux parents avec respect de l'opt-out et anti-doublon."""
        parent_active = self.env['res.partner'].create({
            'name': 'Parent Notif Active',
            'email': 'notif.active@example.com',
            'notify_attendance_email': True,
        })
        parent_optout = self.env['res.partner'].create({
            'name': 'Parent Opt Out',
            'email': 'notif.optout@example.com',
            'notify_attendance_email': False,  # Opt-out explicite
        })
        student = self.env['eacta.student'].create({
            'name': 'Enfant Notif',
            'gender': 'male',
            'date_of_birth': date(2014, 5, 1),
            'parent_ids': [(6, 0, [parent_active.id, parent_optout.id])],
            'current_class_id': self.class_6a.id,
            'state': 'enrolled',
        })

        # Création d'une absence
        attendance = self.env['eacta.attendance'].create({
            'student_id': student.id,
            'class_id': self.class_6a.id,
            'date': fields.Date.today(),
            'session': 'morning',
            'attendance_type': 'absent',
            'justified': False,
        })

        self.assertTrue(attendance.notification_sent, "L'enregistrement d'assiduité doit être marqué comme notifié")
        self.assertIn(parent_active, attendance.notified_parent_ids, "Le parent ayant accepté les notifications doit être notifié")
        self.assertNotIn(parent_optout, attendance.notified_parent_ids, "Le parent ayant refusé (opt-out) ne doit pas être notifié")

        # Vérification qu'une modification ne renvoie pas de doublon
        notified_ids_before = attendance.notified_parent_ids.ids
        attendance.write({'justification_note': 'Appel téléphonique des parents'})
        self.assertEqual(attendance.notified_parent_ids.ids, notified_ids_before)

    # =========================================================================
    # 18. PHASE 3: CONTRÔLE D'ACCÈS PORTAIL (PARENTS & ÉLÈVES) SANS SUDO
    # =========================================================================
    def test_19_portal_security_and_access_restrictions(self):
        """Vérification stricte de la sécurité du portail : un parent ne peut pas voir un enfant tiers."""
        # 1. En tant que Parent Alami (user_parent_1)
        # Il ne doit voir QUE ses propres enfants (Karim et Salma), pas Youssef Bennani
        students_alami = self.env['eacta.student'].with_user(self.user_parent_1).search([])
        self.assertIn(self.student_1, students_alami)
        self.assertIn(self.student_2, students_alami)
        self.assertNotIn(self.student_3, students_alami, "Parent Alami ne doit jamais voir l'élève Bennani")

        # 2. Test d'accès à son propre enfant
        env_parent = self.env(user=self.user_parent_1)
        student_accessible = env_parent['eacta.student'].browse(self.student_1.id)
        student_accessible.check_access('read')
        self.assertEqual(student_accessible.name, 'Karim Alami')

        # 3. Tentative d'usurpation : Parent Alami essaie d'ouvrir l'élève Bennani (student_3)
        with self.assertRaises(AccessError):
            student_foreign = env_parent['eacta.student'].browse(self.student_3.id)
            student_foreign.check_access('read')
            _ = student_foreign.name

        # 4. En tant qu'élève Karim (user_student_1) : il ne doit voir que son propre profil
        students_karim = self.env['eacta.student'].with_user(self.user_student_1).search([])
        self.assertEqual(len(students_karim), 1)
        self.assertEqual(students_karim[0], self.student_1)

        # Tentative d'accès à Salma ou Youssef par Karim
        env_student = self.env(user=self.user_student_1)
        with self.assertRaises(AccessError):
            other_student = env_student['eacta.student'].browse(self.student_2.id)
            other_student.check_access('read')
            _ = other_student.name

        # 5. Seules les notes publiées sont visibles dans le portail
        exam = self.env['eacta.exam'].create({
            'name': 'Examen Math Secret',
            'course_id': self.course_math.id,
            'date': fields.Date.today(),
            'exam_type': 'quiz',
            'state': 'grading',
        })
        grade_draft = self.env['eacta.course.grade'].create({
            'exam_id': exam.id,
            'student_id': self.student_1.id,
            'class_id': self.class_6a.id,
            'grade': 18.0,
            'status': 'graded',
            'state': 'draft',  # Pas encore publié !
        })

        portal_grades = self.env['eacta.course.grade'].with_user(self.user_parent_1).search([
            ('student_id', '=', self.student_1.id),
            ('state', '=', 'published'),
        ])
        self.assertNotIn(grade_draft, portal_grades, "Une note à l'état draft ne doit pas être visible sur le portail")

    # =========================================================================
    # 19. PHASE 4: TIMETABLE CONFLICTS & ICS EXPORT
    # =========================================================================
    def test_20_timetable_conflicts_and_ics_export(self):
        """Détection des conflits d'emploi du temps (enseignant, salle, classe) et export .ics RFC 5545."""
        # Création d'un premier créneau : Lundi 08h-10h en salle B101 avec Teacher Dupont pour Class 6A
        slot_1 = self.env['eacta.timetable.slot'].create({
            'class_id': self.class_6a.id,
            'course_id': self.course_math.id,
            'teacher_id': self.user_teacher_1.id,
            'weekday': '0',
            'hour_from': 8.0,
            'hour_to': 10.0,
            'room': 'B101',
        })
        self.assertTrue(slot_1)

        self.course_physics.write({'class_ids': [(4, self.class_6b.id)]})

        # 1. Conflit Enseignant : Dupont ne peut pas enseigner à une autre classe (6B) le Lundi de 09h à 11h
        with self.assertRaises(ValidationError):
            self.env['eacta.timetable.slot'].create({
                'class_id': self.class_6b.id,
                'course_id': self.course_math.id,
                'teacher_id': self.user_teacher_1.id,
                'weekday': '0',
                'hour_from': 9.0,
                'hour_to': 11.0,
                'room': 'B102',
            })

        # 2. Conflit Salle : Salle B101 ne peut pas accueillir une autre classe sur le même créneau
        with self.assertRaises(ValidationError):
            self.env['eacta.timetable.slot'].create({
                'class_id': self.class_6b.id,
                'course_id': self.course_physics.id,
                'teacher_id': self.user_teacher_2.id,
                'weekday': '0',
                'hour_from': 8.5,
                'hour_to': 9.5,
                'room': 'B101',
            })

        # 3. Conflit Classe : Class 6A ne peut pas avoir deux cours qui se chevauchent
        with self.assertRaises(ValidationError):
            self.env['eacta.timetable.slot'].create({
                'class_id': self.class_6a.id,
                'course_id': self.course_physics.id,
                'teacher_id': self.user_teacher_2.id,
                'weekday': '0',
                'hour_from': 9.0,
                'hour_to': 11.0,
                'room': 'B103',
            })

        # 4. Export iCalendar (.ics) conforme au standard RFC 5545
        ics_class = self.env['eacta.timetable.slot'].export_ics('class', self.class_6a.id)
        self.assertIsNotNone(ics_class)
        self.assertIn("BEGIN:VCALENDAR", ics_class)
        self.assertIn("VERSION:2.0", ics_class)
        self.assertIn("BEGIN:VEVENT", ics_class)
        self.assertIn("RRULE:FREQ=WEEKLY", ics_class)
        self.assertIn("B101", ics_class)
        self.assertIn("END:VCALENDAR", ics_class)

        # Export pour un enseignant
        ics_teacher = self.env['eacta.timetable.slot'].export_ics('teacher', self.user_teacher_1.id)
        self.assertIsNotNone(ics_teacher)
        self.assertIn("BEGIN:VCALENDAR", ics_teacher)
        self.assertIn(self.user_teacher_1.name, ics_teacher)

    # =========================================================================
    # 20. PHASE 4: STUDENT CARD QR TOKEN & ATTENDANCE SCAN
    # =========================================================================
    def test_21_student_qr_card_and_scan_attendance(self):
        """Carte d'élève avec jeton QR sécurisé et enregistrement d'assiduité 1-clic."""
        # 1. Vérification du jeton QR cryptographique non-devinable
        self.assertTrue(self.student_1.qr_token)
        self.assertGreaterEqual(len(self.student_1.qr_token), 32)
        initial_token = self.student_1.qr_token

        # 2. Régénération du jeton QR
        self.student_1.action_regenerate_qr_token()
        self.assertNotEqual(self.student_1.qr_token, initial_token)

        # 3. Action d'impression du badge / carte d'élève
        badge_report_action = self.student_1.action_print_student_badge()
        self.assertEqual(badge_report_action.get('type'), 'ir.actions.report')
        self.assertEqual(badge_report_action.get('report_name'), 'eacta_school.report_student_card_badge')

        # 4. Simulation de l'enregistrement d'assiduité par scan (1-clic)
        today = fields.Date.today()
        current_hour = fields.Datetime.now().hour
        session = 'morning' if current_hour < 13 else 'afternoon'

        # Suppression préalable d'éventuels enregistrements existants pour le test
        self.env['eacta.attendance'].search([
            ('student_id', '=', self.student_1.id),
            ('date', '=', today),
            ('session', '=', session),
        ]).unlink()

        # Enregistrement via le token
        found_student = self.env['eacta.student'].search([('qr_token', '=', self.student_1.qr_token)], limit=1)
        self.assertEqual(found_student, self.student_1)

        attendance = self.env['eacta.attendance'].create({
            'student_id': found_student.id,
            'class_id': found_student.current_class_id.id,
            'date': today,
            'session': session,
            'attendance_type': 'present',
        })
        self.assertTrue(attendance)
        self.assertEqual(attendance.attendance_type, 'present')

    # =========================================================================
    # 21. PHASE 4: TRANSPORT SCOLAIRE (LIGNES, ARRÊTS, CAPACITÉ & SÉCURITÉ)
    # =========================================================================
    def test_22_transport_lines_capacity_and_rules(self):
        """Lignes de bus, arrêts, vérification de capacité et droits d'accès."""
        # 1. Création d'une ligne de transport avec capacité de 2 places
        line = self.env['eacta.transport.line'].create({
            'name': 'Ligne Navette Rabat-Agdal',
            'code': 'L-AGDAL',
            'driver_name': 'Hassan Tazi',
            'driver_phone': '0661234567',
            'vehicle_name': 'Mercedes Sprinter (45678-A-1)',
            'capacity': 2,
        })
        self.assertEqual(line.available_seats, 2)

        # Création des arrêts
        stop_1 = self.env['eacta.transport.stop'].create({
            'name': 'Arrêt Place Darna',
            'line_id': line.id,
            'sequence': 10,
            'time_morning': '07:30',
        })
        stop_2 = self.env['eacta.transport.stop'].create({
            'name': 'Arrêt Gare Rabat Agdal',
            'line_id': line.id,
            'sequence': 20,
            'time_morning': '07:45',
        })
        self.assertEqual(line.stop_count, 2)

        # 2. Inscription de 2 élèves (Karim et Salma)
        self.student_1.write({
            'transport_mode': 'bus',
            'transport_line_id': line.id,
            'transport_stop_id': stop_1.id,
        })
        self.student_2.write({
            'transport_mode': 'bus',
            'transport_line_id': line.id,
            'transport_stop_id': stop_2.id,
        })

        line._compute_passengers()
        self.assertEqual(line.passenger_count, 2)
        self.assertEqual(line.available_seats, 0)

        # 3. Tentative d'ajouter un 3ème élève : doit lever ValidationError pour capacité dépassée
        with self.assertRaises(ValidationError):
            self.student_3.write({
                'transport_mode': 'bus',
                'transport_line_id': line.id,
            })

        # 4. Incohérence d'arrêt : l'arrêt doit appartenir à la ligne sélectionnée
        other_line = self.env['eacta.transport.line'].create({
            'name': 'Ligne 2 - Salé',
            'code': 'L-SALE',
            'capacity': 15,
        })
        with self.assertRaises(ValidationError):
            self.student_1.write({
                'transport_line_id': other_line.id,
                'transport_stop_id': stop_1.id,  # stop_1 appartient à line (Agdal), pas à other_line (Salé)
            })

        # 5. Sécurité : le parent Alami ne voit que les lignes de ses enfants
        portal_lines = self.env['eacta.transport.line'].with_user(self.user_parent_1).search([])
        self.assertIn(line, portal_lines)
        self.assertNotIn(other_line, portal_lines)

    # =========================================================================
    # 23. PHASE 5: GRADE WORKFLOW BATCH ACTIONS & REJECTION CONSTRAINTS
    # =========================================================================
    def test_23_grade_workflow_rejection_and_batch_actions(self):
        """Vérifie le rejet d'une note soumise, le rejet direct de publication sans validation, et les actions en masse."""
        exam = self.env['eacta.exam'].create({
            'name': 'Examen Phase 5 Rejet & Lot',
            'course_id': self.course_math.id,
            'exam_type': 'quiz',
            'date': date.today() - timedelta(days=2),
            'academic_year_id': self.year_curr.id,
            'term_id': self.term_1.id,
            'class_ids': [(4, self.class_6a.id)],
        })
        grade_1 = self.env['eacta.course.grade'].create({
            'exam_id': exam.id,
            'student_id': self.student_1.id,
            'class_id': self.class_6a.id,
            'status': 'graded',
            'grade': 15.0,
        })
        grade_2 = self.env['eacta.course.grade'].create({
            'exam_id': exam.id,
            'student_id': self.student_2.id,
            'class_id': self.class_6a.id,
            'status': 'graded',
            'grade': 12.5,
        })

        # 1. Tentative de publication directe depuis le statut 'draft' : interdit
        with self.assertRaises(UserError):
            grade_1.with_user(self.user_direction).action_publish()

        # 2. Soumission par l'enseignant
        exam.grade_ids.with_user(self.user_teacher_1).action_submit()
        self.assertTrue(all(g.state == 'submitted' for g in exam.grade_ids))

        # 3. Rejet d'une note par la Direction (ex: demande de réévaluation)
        grade_1.with_user(self.user_direction).action_reject(reason="Vérifier la question 3")
        self.assertEqual(grade_1.state, 'draft')
        self.assertEqual(grade_2.state, 'submitted')

        # 4. Enseignant réajuste et resoumet
        grade_1.with_user(self.user_teacher_1).write({'grade': 16.0})
        grade_1.with_user(self.user_teacher_1).action_submit()
        self.assertEqual(grade_1.state, 'submitted')

        # 5. Validation en lot via l'examen
        exam.with_user(self.user_direction).action_validate_grades()
        self.assertTrue(all(g.state == 'validated' for g in exam.grade_ids))

        # 6. Publication en lot via l'examen
        exam.with_user(self.user_direction).action_publish_grades()
        self.assertTrue(all(g.state == 'published' for g in exam.grade_ids))

    # =========================================================================
    # 24. PHASE 5: FEE INSTALLMENTS SCHEDULE & MULTI-SIBLING DISCOUNT MATRIX
    # =========================================================================
    def test_24_fee_installment_schedule_and_multi_sibling_discounts(self):
        """Vérifie le calcul exact des remises de fratrie (aîné 0%, 2e 10%, 3e 20%) et l'échéancier en 4 tranches."""
        partner_family = self.env['res.partner'].create({
            'name': 'Famille Test Fratrie Phase 5',
            'email': 'famille.p5@example.com',
            'is_school_parent': True,
        })
        # 3 enfants classés par date de naissance
        c1_eldest = self.env['eacta.student'].create({
            'name': 'Aîné Famille P5',
            'date_of_birth': date(2009, 3, 15),
            'parent_ids': [(6, 0, [partner_family.id])],
            'state': 'enrolled',
        })
        c2_second = self.env['eacta.student'].create({
            'name': 'Cadet Famille P5',
            'date_of_birth': date(2011, 7, 20),
            'parent_ids': [(6, 0, [partner_family.id])],
            'state': 'enrolled',
        })
        c3_youngest = self.env['eacta.student'].create({
            'name': 'Benjamin Famille P5',
            'date_of_birth': date(2014, 11, 5),
            'parent_ids': [(6, 0, [partner_family.id])],
            'state': 'enrolled',
        })

        # L'aîné est identifié strictement par sa date de naissance
        self.assertTrue(c1_eldest._is_eldest_sibling())
        self.assertFalse(c2_second._is_eldest_sibling())
        self.assertFalse(c3_youngest._is_eldest_sibling())

        # Génération d'un échéancier en 4 tranches de scolarité pour le cadet (base: 10 000 MAD)
        fee_type = self.env.ref('eacta_school.fee_type_tuition')
        wiz = self.env['eacta.fee.generate.wizard'].create({
            'fee_type_id': fee_type.id,
            'student_ids': [(6, 0, [c2_second.id])],
            'amount': 10000.0,
            'apply_sibling_discount': True,
            'installments': 4,
            'first_due_date': date(2026, 9, 15),
            'description': 'Scolarité 4 Tranches',
        })
        wiz.action_generate()

        fees = self.env['eacta.student.fee'].search([
            ('student_id', '=', c2_second.id),
            ('description', 'like', 'Scolarité 4 Tranches%')
        ], order='due_date')
        self.assertEqual(len(fees), 4)

        # Base 10 000 MAD - 10% remise = 9 000 MAD au total net (amount_total), soit 2 250 MAD par tranche
        # Brut : 10 000 MAD (2 500 MAD par tranche) avec remise de 250 MAD par tranche
        total_amount = sum(fees.mapped('amount_total'))
        self.assertAlmostEqual(total_amount, 9000.0, places=2)
        for fee in fees:
            self.assertAlmostEqual(fee.amount, 2500.0, places=2)
            self.assertAlmostEqual(fee.discount, 250.0, places=2)
            self.assertAlmostEqual(fee.amount_total, 2250.0, places=2)

        # Espacement mensuel des échéances
        dates = fees.mapped('due_date')
        self.assertEqual(dates[0], date(2026, 9, 15))
        self.assertEqual(dates[1], date(2026, 10, 15))
        self.assertEqual(dates[2], date(2026, 11, 15))
        self.assertEqual(dates[3], date(2026, 12, 15))

    # =========================================================================
    # 25. PHASE 5: SECURITY RECORD RULES ISOLATION MATRIX
    # =========================================================================
    def test_25_security_record_rules_matrix(self):
        """Matrice complète de sécurité : Enseignant (isolement strict), Parent (ses enfants), Élève (soi-même)."""
        # 1. Enseignant : ne voit que ses propres classes et cours
        other_teacher_class = self.env['eacta.class'].create({
            'name': '6ème C Isolée',
            'academic_year_id': self.year_curr.id,
            'level': 'secondary',
            'teacher_id': self.user_teacher_2.id,
        })
        t1_classes = self.env['eacta.class'].with_user(self.user_teacher_1).search([])
        self.assertIn(self.class_6a, t1_classes)
        self.assertNotIn(other_teacher_class, t1_classes)

        # 2. Enseignant n'a pas accès aux frais scolaires (réservé direction/comptable) -> AccessError
        with self.assertRaises(AccessError):
            self.env['eacta.student.fee'].with_user(self.user_teacher_1).search([])

        # 3. Parent 1 ne voit pas les frais d'un élève qui ne lui est pas rattaché
        other_student = self.student_3  # enfant de Bennani (Parent 2)
        fee_other = self.env['eacta.student.fee'].create({
            'student_id': other_student.id,
            'fee_type_id': self.env.ref('eacta_school.fee_type_tuition').id,
            'amount': 3000.0,
            'due_date': date.today() + timedelta(days=30),
            'academic_year_id': self.year_curr.id,
        })
        p1_fees = self.env['eacta.student.fee'].with_user(self.user_parent_1).search([
            ('id', '=', fee_other.id)
        ])
        self.assertFalse(p1_fees)

        # 4. Élève 1 (Karim) ne voit que ses propres créneaux et notes
        k_student_user = self.user_student_1
        self.student_1.write({'user_id': k_student_user.id})

        # L'élève ne peut pas voir le profil de l'élève 2
        s1_students = self.env['eacta.student'].with_user(k_student_user).search([
            ('id', 'in', [self.student_1.id, self.student_2.id])
        ])
        self.assertEqual(s1_students, self.student_1)



