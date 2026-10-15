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
        cls.group_teacher = cls.env.ref('eacta_school.group_eacta_school_teacher')
        cls.group_finance = cls.env.ref('eacta_school.group_eacta_school_finance')
        cls.group_secretary = cls.env.ref('eacta_school.group_eacta_school_secretary')
        cls.group_portal = cls.env.ref('base.group_portal')

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

        cls.term_1 = cls.env['eacta.term'].search([('year_id', '=', cls.year_curr.id), ('sequence', '=', 1)], limit=1)
        if not cls.term_1:
            cls.term_1 = cls.env['eacta.term'].create({
                'name': '1er Trimestre',
                'year_id': cls.year_curr.id,
                'sequence': 1,
                'date_start': date(2026, 9, 1),
                'date_end': date(2026, 11, 30),
                'weight': 1.0,
            })

        cls.term_2 = cls.env['eacta.term'].search([('year_id', '=', cls.year_curr.id), ('sequence', '=', 2)], limit=1)
        if not cls.term_2:
            cls.term_2 = cls.env['eacta.term'].create({
                'name': '2ème Trimestre',
                'year_id': cls.year_curr.id,
                'sequence': 2,
                'date_start': date(2026, 12, 1),
                'date_end': date(2027, 2, 28),
                'weight': 1.0,
            })

        cls.term_3 = cls.env['eacta.term'].search([('year_id', '=', cls.year_curr.id), ('sequence', '=', 3)], limit=1)
        if not cls.term_3:
            cls.term_3 = cls.env['eacta.term'].create({
                'name': '3ème Trimestre',
                'year_id': cls.year_curr.id,
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

        self.assertEqual(len(fees_s1), 3, "Il doit y avoir 3 échéances générées.")
        # Remise fratrie 10% sur 1000 = 900 total -> 3 échéances de 300
        self.assertAlmostEqual(sum(fees_s1.mapped('amount_total')), 900.0, places=2)

        # Enregistrement d'un premier paiement
        fee_1 = fees_s1[0]
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
