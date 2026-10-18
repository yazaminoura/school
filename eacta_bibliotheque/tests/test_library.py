from datetime import date, timedelta
from odoo.tests import common
from odoo.exceptions import ValidationError, UserError, AccessError
from odoo import fields


class TestLibraryPhase4(common.TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Groupes
        cls.group_librarian = cls.env.ref('eacta_bibliotheque.group_eacta_library_user')
        cls.group_manager = cls.env.ref('eacta_bibliotheque.group_eacta_library_manager')
        cls.group_teacher = cls.env.ref('eacta_school.group_eacta_school_teacher')
        cls.group_portal = cls.env.ref('base.group_portal')

        # Utilisateur Bibliothécaire
        cls.user_librarian = cls.env['res.users'].create({
            'name': 'Bibliothécaire Test',
            'login': 'librarian_test',
            'email': 'librarian@example.com',
            'groups_id': [(6, 0, [cls.group_librarian.id])],
        })

        # Utilisateur Enseignant
        cls.user_teacher = cls.env['res.users'].create({
            'name': 'Professeur Test',
            'login': 'teacher_test',
            'email': 'teacher@example.com',
            'is_teacher': True,
            'groups_id': [(6, 0, [cls.group_teacher.id])],
        })

        # Parent et Élève
        cls.partner_parent = cls.env['res.partner'].create({
            'name': 'Parent Lecteur',
            'email': 'parent.lecteur@example.com',
            'is_school_parent': True,
        })
        cls.user_parent = cls.env['res.users'].create({
            'name': 'Parent Lecteur User',
            'login': 'parent_lecteur_user',
            'email': 'parent.lecteur@example.com',
            'partner_id': cls.partner_parent.id,
            'groups_id': [(6, 0, [cls.group_portal.id])],
        })

        cls.student_1 = cls.env['eacta.student'].create({
            'name': 'Élève Emprunteur',
            'gender': 'female',
            'date_of_birth': date(2013, 6, 15),
            'parent_ids': [(6, 0, [cls.partner_parent.id])],
            'state': 'enrolled',
        })

        # Autre élève sans lien de parenté
        cls.student_other = cls.env['eacta.student'].create({
            'name': 'Élève Tiers',
            'gender': 'male',
            'state': 'enrolled',
        })

        # Création d'un livre et exemplaire
        cls.book_1 = cls.env['library.book'].create({
            'name': 'Le Petit Prince',
            'author': 'Antoine de Saint-Exupéry',
            'loan_duration_days': 14,
            'replacement_cost': 80.0,
        })
        cls.copy_1 = cls.env['library.book.barcode'].create({
            'book_id': cls.book_1.id,
            'barcode': 'BC-TEST-001',
            'state': 'available',
        })
        cls.copy_2 = cls.env['library.book.barcode'].create({
            'book_id': cls.book_1.id,
            'barcode': 'BC-TEST-002',
            'state': 'available',
        })

    def test_01_borrow_and_due_date_computation(self):
        """Emprunt de livre, calcul de la date de retour prévue et contrôle de disponibilité."""
        today = fields.Date.today()
        loan = self.env['library.loan'].create({
            'borrower_type': 'student',
            'student_id': self.student_1.id,
            'book_id': self.book_1.id,
            'barcode_id': self.copy_1.id,
            'checkout_date': today,
        })

        self.assertEqual(loan.state, 'ongoing')
        self.assertEqual(loan.due_date, today + timedelta(days=14))
        self.assertEqual(loan.days_late, 0)
        self.assertEqual(loan.fine_amount, 0.0)

        # Tentative d'emprunter le même exemplaire déjà emprunté -> ValidationError
        with self.assertRaises(ValidationError):
            self.env['library.loan'].create({
                'borrower_type': 'student',
                'student_id': self.student_other.id,
                'book_id': self.book_1.id,
                'barcode_id': self.copy_1.id,
                'checkout_date': today,
            })

    def test_02_opt_in_overdue_fines(self):
        """Amendes de retard : désactivées par défaut (opt-in), et appliquées uniquement si activées."""
        ICP = self.env['ir.config_parameter'].sudo()
        today = fields.Date.today()

        # 1. PAR DÉFAUT : amendes désactivées (enable_overdue_fines = False)
        ICP.set_param('library.enable_overdue_fines', 'False')
        ICP.set_param('library.fine_per_day', '2.0')

        loan_no_fine = self.env['library.loan'].create({
            'borrower_type': 'student',
            'student_id': self.student_1.id,
            'book_id': self.book_1.id,
            'barcode_id': self.copy_1.id,
            'checkout_date': today - timedelta(days=30),
            'due_date': today - timedelta(days=16),  # 16 jours de retard
        })
        loan_no_fine._compute_state()

        self.assertEqual(loan_no_fine.state, 'overdue')
        self.assertEqual(loan_no_fine.days_late, 16)
        # Comme l'option est opt-in et désactivée, fine_amount doit être 0.0 !
        self.assertEqual(loan_no_fine.fine_amount, 0.0)

        # Retour du livre : aucun frais créé
        fee_count_before = self.env['eacta.student.fee'].search_count([('student_id', '=', self.student_1.id)])
        loan_no_fine.action_return_book()
        self.assertEqual(loan_no_fine.state, 'returned')
        fee_count_after = self.env['eacta.student.fee'].search_count([('student_id', '=', self.student_1.id)])
        self.assertEqual(fee_count_before, fee_count_after, "Aucun frais ne doit être créé quand les amendes sont inactives")

        # 2. ACTIVATION DE L'OPTION (opt-in = True)
        ICP.set_param('library.enable_overdue_fines', 'True')

        loan_with_fine = self.env['library.loan'].create({
            'borrower_type': 'student',
            'student_id': self.student_1.id,
            'book_id': self.book_1.id,
            'barcode_id': self.copy_2.id,
            'checkout_date': today - timedelta(days=20),
            'due_date': today - timedelta(days=6),  # 6 jours de retard
        })
        loan_with_fine._compute_state()

        self.assertEqual(loan_with_fine.state, 'overdue')
        self.assertEqual(loan_with_fine.days_late, 6)
        # 6 jours * 2.0 = 12.0 DH
        self.assertAlmostEqual(loan_with_fine.fine_amount, 12.0, places=2)

        # Retour du livre : un frais d'amende doit être généré pour l'élève
        loan_with_fine.action_return_book()
        self.assertEqual(loan_with_fine.state, 'returned')
        fee = self.env['eacta.student.fee'].search([
            ('student_id', '=', self.student_1.id),
            ('amount', '=', 12.0),
        ], limit=1)
        self.assertTrue(fee, "Un frais de 12.0 DH doit être créé pour le retard de bibliothèque")

    def test_03_overdue_reminder_cron_and_minimum_interval(self):
        """Action planifiée de relance pour retard d'emprunt avec intervalle anti-doublon."""
        today = fields.Date.today()
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('library.send_overdue_reminder_email', 'True')
        ICP.set_param('library.overdue_reminder_interval_days', '7')

        overdue_loan = self.env['library.loan'].create({
            'borrower_type': 'student',
            'student_id': self.student_1.id,
            'book_id': self.book_1.id,
            'barcode_id': self.copy_1.id,
            'checkout_date': today - timedelta(days=25),
            'due_date': today - timedelta(days=11),
        })
        overdue_loan._compute_state()
        self.assertEqual(overdue_loan.state, 'overdue')
        self.assertEqual(overdue_loan.reminder_count, 0)
        self.assertFalse(overdue_loan.last_reminder_date)

        # 1. Premier passage du cron : la relance doit être émise
        self.env['library.loan']._cron_check_overdue()
        self.assertEqual(overdue_loan.reminder_count, 1)
        self.assertEqual(overdue_loan.last_reminder_date, today)

        # 2. Deuxième passage immédiat du cron : PAS de doublon grâce à l'intervalle minimum (7 jours)
        self.env['library.loan']._cron_check_overdue()
        self.assertEqual(overdue_loan.reminder_count, 1, "Le cron ne doit pas réémettre une relance avant l'intervalle minimum")

    def test_04_library_security_and_portal_isolation(self):
        """Contrôle d'accès et règles d'enregistrement sur les emprunts de bibliothèque."""
        today = fields.Date.today()

        # Emprunt pour l'élève de Parent Lecteur
        loan_parent = self.env['library.loan'].create({
            'borrower_type': 'student',
            'student_id': self.student_1.id,
            'book_id': self.book_1.id,
            'barcode_id': self.copy_1.id,
            'checkout_date': today,
        })

        # Emprunt pour un élève étranger
        loan_stranger = self.env['library.loan'].create({
            'borrower_type': 'student',
            'student_id': self.student_other.id,
            'book_id': self.book_1.id,
            'barcode_id': self.copy_2.id,
            'checkout_date': today,
        })

        # 1. Parent Lecteur ne doit voir que les emprunts de son enfant
        loans_parent = self.env['library.loan'].with_user(self.user_parent).search([])
        self.assertIn(loan_parent, loans_parent)
        self.assertNotIn(loan_stranger, loans_parent, "Le parent ne doit pas voir les emprunts des autres élèves")

        # 2. Tentative d'accès direct par ID à l'emprunt d'un tiers
        env_parent = self.env(user=self.user_parent)
        with self.assertRaises(AccessError):
            foreign_loan = env_parent['library.loan'].browse(loan_stranger.id)
            foreign_loan.check_access('read')
            _ = foreign_loan.name
