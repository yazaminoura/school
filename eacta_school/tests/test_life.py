from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSchoolLife(TransactionCase):
    """Cahier de textes, vie scolaire, annonces, infirmerie, cantine, Massar et paie."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.today = fields.Date.today()
        # Une seule année peut être ouverte : réutiliser celle des données d'exemple si elle existe
        Year = cls.env['eacta.academic.year']
        cls.year = Year.search([('state', '=', 'open')], limit=1) or Year.create({
            'name': 'Année test vie scolaire',
            'date_start': cls.today - timedelta(days=60),
            'date_end': cls.today + timedelta(days=200),
            'state': 'open',
        })
        if not (cls.year.date_start <= cls.today <= cls.year.date_end):
            cls.year.date_end = max(cls.year.date_end, cls.today + timedelta(days=30))
        cls.user_teacher = cls.env['res.users'].create({
            'name': 'Prof Vie Scolaire', 'login': 'prof_vie_scolaire', 'email': 'prof.vs@school.local',
            'is_teacher': True,
            'groups_id': [(6, 0, [cls.env.ref('eacta_school.group_eacta_school_teacher').id])],
        })
        cls.user_other_teacher = cls.env['res.users'].create({
            'name': 'Prof Autre', 'login': 'prof_autre_vs', 'email': 'prof.autre@school.local',
            'is_teacher': True,
            'groups_id': [(6, 0, [cls.env.ref('eacta_school.group_eacta_school_teacher').id])],
        })
        cls.user_finance = cls.env['res.users'].create({
            'name': 'Comptable Vie Scolaire', 'login': 'finance_vs', 'email': 'finance.vs@school.local',
            'groups_id': [(6, 0, [cls.env.ref('eacta_school.group_eacta_school_finance').id])],
        })
        cls.course = cls.env['eacta.course'].create({
            'name': 'Mathématiques VS', 'code': 'MATHVS', 'teacher_id': cls.user_teacher.id,
        })
        cls.klass = cls.env['eacta.class'].create({
            'name': 'Classe VS', 'level': 'secondary', 'capacity': 30,
            'academic_year_id': cls.year.id, 'year': cls.year.name,
            'teacher_id': cls.user_teacher.id, 'course_ids': [(6, 0, cls.course.ids)],
        })
        cls.other_class = cls.env['eacta.class'].create({
            'name': 'Classe VS 2', 'level': 'primary', 'capacity': 30,
            'academic_year_id': cls.year.id, 'year': cls.year.name,
            'teacher_id': cls.user_other_teacher.id,
        })
        cls.parent = cls.env['res.partner'].create({
            'name': 'Parent VS', 'email': 'parent.vs@example.com', 'is_school_parent': True,
        })
        cls.user_parent = cls.env['res.users'].create({
            'name': 'Parent VS', 'login': 'parent_vs', 'email': 'parent.vs@example.com',
            'partner_id': cls.parent.id,
            'groups_id': [(6, 0, [cls.env.ref('base.group_portal').id])],
        })
        cls.student = cls.env['eacta.student'].create({
            'name': 'Yasmine Tazi', 'class_ids': [(6, 0, cls.klass.ids)],
            'parent_ids': [(6, 0, cls.parent.ids)], 'state': 'enrolled',
        })
        cls.other_student = cls.env['eacta.student'].create({
            'name': 'Omar Filali', 'class_ids': [(6, 0, cls.other_class.ids)], 'state': 'enrolled',
        })

    # ------------------------------------------------------------------
    def test_01_homework_visible_to_parent_only_when_published(self):
        homework = self.env['eacta.homework'].create({
            'name': 'Exercices 1 à 5', 'class_id': self.klass.id, 'course_id': self.course.id,
            'date_assigned': self.today, 'due_date': self.today + timedelta(days=3),
        })
        Homework = self.env['eacta.homework'].with_user(self.user_parent)
        self.assertFalse(Homework.search([('id', '=', homework.id)]))
        homework.action_publish()
        self.assertEqual(Homework.search([('id', '=', homework.id)]), homework)
        with self.assertRaises(ValidationError):
            homework.due_date = self.today - timedelta(days=1)

    def test_02_teacher_sees_only_own_lessons(self):
        mine = self.env['eacta.lesson'].create({
            'name': 'Fractions', 'class_id': self.klass.id, 'course_id': self.course.id,
            'teacher_id': self.user_teacher.id,
        })
        other = self.env['eacta.lesson'].create({
            'name': 'Lecture', 'class_id': self.other_class.id, 'course_id': self.course.id,
            'teacher_id': self.user_other_teacher.id,
        })
        visible = self.env['eacta.lesson'].with_user(self.user_teacher).search([('id', 'in', (mine | other).ids)])
        self.assertEqual(visible, mine)

    def test_03_conduct_score_and_portal_visibility(self):
        insolence = self.env.ref('eacta_school.incident_type_insolence')
        helping = self.env.ref('eacta_school.incident_type_help')
        incident = self.env['eacta.discipline.incident'].create({
            'student_id': self.student.id, 'type_id': insolence.id, 'description': 'Insolence en cours.',
        })
        self.assertEqual(incident.points, insolence.default_points)
        self.assertEqual(incident.class_id, self.klass)
        self.assertEqual(self.student.conduct_score, 20.0, "Un incident non validé ne compte pas.")
        Incident = self.env['eacta.discipline.incident'].with_user(self.user_parent)
        self.assertFalse(Incident.search([('id', '=', incident.id)]))

        incident.action_confirm()
        self.env['eacta.discipline.incident'].create({
            'student_id': self.student.id, 'type_id': helping.id, 'description': 'Aide un camarade.',
            'state': 'confirmed',
        })
        self.student.invalidate_recordset(['conduct_score', 'incident_count'])
        self.assertEqual(self.student.conduct_score, 20.0 + insolence.default_points + helping.default_points)
        self.assertEqual(self.student.incident_count, 1)
        self.assertEqual(Incident.search([('id', '=', incident.id)]), incident)
        with self.assertRaises(UserError):
            incident.action_confirm()

    def test_04_announcement_targets_and_reads(self):
        announcement = self.env['eacta.announcement'].create({
            'name': 'Sortie scolaire', 'body': '<p>Autorisation à rendre.</p>',
            'audience': 'classes', 'class_ids': [(6, 0, self.klass.ids)], 'send_email': False,
        })
        self.assertIn(self.parent, announcement.recipient_partner_ids)
        self.assertEqual(announcement.recipient_count, 1)
        Announcement = self.env['eacta.announcement'].with_user(self.user_parent)
        self.assertFalse(Announcement.search([('id', '=', announcement.id)]))
        announcement.action_publish()
        self.assertEqual(announcement.state, 'published')
        self.assertEqual(Announcement.search([('id', '=', announcement.id)]), announcement)
        announcement._mark_read(self.parent)
        announcement._mark_read(self.parent)
        self.assertEqual(announcement.read_count, 1)
        self.assertEqual(announcement.read_rate, 100.0)

        empty = self.env['eacta.announcement'].create({
            'name': 'Vide', 'body': '<p>-</p>', 'audience': 'students', 'send_email': False,
        })
        with self.assertRaises(UserError):
            empty.action_publish()

    def test_05_infirmary_and_certificates(self):
        visit = self.env['eacta.infirmary.visit'].create({
            'student_id': self.student.id, 'reason': 'fever', 'temperature': 38.5, 'outcome': 'sent_home',
        })
        self.assertTrue(visit.name and visit.name != '/')
        with self.assertRaises(ValidationError):
            visit.temperature = 52.0
        with self.assertRaises(AccessError):
            self.env['eacta.infirmary.visit'].with_user(self.user_teacher).search([])
        self.assertFalse(self.student.sport_exempted)
        self.env['eacta.medical.certificate'].create({
            'student_id': self.student.id, 'certificate_type': 'sport_exemption',
            'date_from': self.today - timedelta(days=1), 'date_to': self.today + timedelta(days=10),
        })
        self.student.invalidate_recordset(['sport_exempted'])
        self.assertTrue(self.student.sport_exempted)

    def test_06_canteen_subscription_fees_and_daily_count(self):
        subscription = self.env['eacta.canteen.subscription'].create({
            'student_id': self.student.id, 'academic_year_id': self.year.id, 'plan': 'full',
            'monthly_price': 900.0, 'date_start': self.today - timedelta(days=30), 'diet_note': 'Sans gluten',
        })
        self.assertTrue(self.student.canteen)
        fees = subscription.action_generate_month_fee()
        self.assertEqual(len(fees), 1)
        self.assertEqual(fees.amount, 900.0)
        self.assertFalse(subscription.action_generate_month_fee(), "Le même mois n'est pas facturé deux fois.")
        with self.assertRaises(ValidationError):
            self.env['eacta.canteen.subscription'].create({
                'student_id': self.student.id, 'academic_year_id': self.year.id, 'plan': 'full'})

        # Un jour ouvré hors mercredi pour la formule 5 jours
        day = self.today - timedelta(days=1)
        while day.weekday() >= 5:
            day -= timedelta(days=1)
        wizard = self.env['eacta.canteen.count.wizard'].create({'date': day})
        line = wizard.line_ids.filtered(lambda l: l.class_id == self.klass)
        self.assertEqual((line.subscribed, line.absent, line.expected), (1, 0, 1))
        self.assertIn('Yasmine Tazi', wizard.diet_summary)
        self.env['eacta.attendance'].create({
            'student_id': self.student.id, 'date': day, 'attendance_type': 'absent', 'session': 'all_day',
            'notification_sent': True,
        })
        wizard = self.env['eacta.canteen.count.wizard'].create({'date': day})
        line = wizard.line_ids.filtered(lambda l: l.class_id == self.klass)
        self.assertEqual((line.subscribed, line.absent, line.expected), (1, 1, 0))

        subscription.action_end()
        self.assertFalse(self.student.canteen)

    def test_07_massar_export(self):
        self.student.massar_code = 'J130000001'
        with self.assertRaises(Exception):
            with self.cr.savepoint():
                self.other_student.massar_code = 'J130000001'
                self.other_student.flush_recordset()
        wizard = self.env['eacta.massar.export.wizard'].create({
            'export_type': 'students', 'academic_year_id': self.year.id,
            'class_ids': [(6, 0, (self.klass | self.other_class).ids)],
        })
        self.assertEqual(wizard.missing_code_count, 1)
        wizard.action_export()
        self.assertEqual(wizard.state, 'done')
        self.assertTrue(wizard.file_data)
        self.assertTrue(wizard.file_name.endswith('.xlsx'))

    def test_08_payslip_amounts_and_lock(self):
        contract = self.env['eacta.staff.contract'].create({
            'name': 'Nadia Test', 'job': 'admin', 'contract_type': 'cdi', 'monthly_wage': 8000.0,
        })
        contract.action_start()
        vacataire = self.env['eacta.staff.contract'].create({
            'name': 'Vacataire Test', 'job': 'teacher', 'contract_type': 'vacataire', 'hourly_rate': 100.0,
        })
        with self.assertRaises(UserError):
            self.env['eacta.staff.contract'].create({
                'name': 'Sans taux', 'contract_type': 'vacataire'}).action_start()
        vacataire.action_start()

        month = self.today.replace(day=1)
        self.env['eacta.payslip.generate.wizard'].with_user(self.user_finance).create(
            {'month': month}).action_generate()
        slip = self.env['eacta.payslip'].search([('contract_id', '=', contract.id), ('date_from', '=', month)])
        self.assertEqual(len(slip), 1)
        self.assertAlmostEqual(slip.gross, 8000.0)
        self.assertAlmostEqual(slip.cnss_amount, round(6000.0 * 0.0448, 2), msg="CNSS plafonnée à 6 000 DH.")
        self.assertAlmostEqual(slip.amo_amount, round(8000.0 * 0.0226, 2))
        slip.income_tax = 500.0
        self.assertAlmostEqual(slip.net, round(8000.0 - slip.cnss_amount - slip.amo_amount - 500.0, 2))

        vac_slip = self.env['eacta.payslip'].search([('contract_id', '=', vacataire.id)])
        vac_slip.worked_hours = 20.0
        self.assertAlmostEqual(vac_slip.gross, 2000.0)

        slip.action_confirm()
        with self.assertRaises(UserError):
            slip.bonus = 100.0
        slip.action_mark_paid()
        self.assertEqual(slip.state, 'paid')
        with self.assertRaises(UserError):
            slip.unlink()
        with self.assertRaises(AccessError):
            self.env['eacta.payslip'].with_user(self.user_teacher).search([])
