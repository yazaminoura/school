from datetime import date, datetime, timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import common, tagged


@tagged('post_install', '-at_install')
class TestSchoolEvent(common.TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.group_event_manager = cls.env.ref('eacta_event.group_eacta_event_manager')
        cls.group_event_user = cls.env.ref('eacta_event.group_eacta_event_user')
        cls.group_teacher = cls.env.ref('eacta_school.group_eacta_school_teacher')
        cls.group_direction = cls.env.ref('eacta_school.group_eacta_school_direction')
        cls.group_portal = cls.env.ref('base.group_portal')
        cls.group_student = cls.env.ref('eacta_school.group_eacta_school_student')

        # Academic Year
        cls.academic_year = cls.env['eacta.academic.year'].search([('name', '=', '2026-2027')], limit=1)
        if not cls.academic_year:
            cls.academic_year = cls.env['eacta.academic.year'].create({
                'name': '2026-2027',
                'date_start': date(2026, 9, 1),
                'date_end': date(2027, 6, 30),
                'state': 'open',
            })

        # Teachers
        cls.user_teacher_1 = cls.env['res.users'].create({
            'name': 'Professeur Event 1',
            'login': 'prof_event_1',
            'email': 'prof_event_1@school.local',
            'is_teacher': True,
            'groups_id': [(6, 0, [cls.group_teacher.id, cls.group_event_user.id])],
        })
        cls.user_teacher_2 = cls.env['res.users'].create({
            'name': 'Professeur Event 2',
            'login': 'prof_event_2',
            'email': 'prof_event_2@school.local',
            'is_teacher': True,
            'groups_id': [(6, 0, [cls.group_teacher.id, cls.group_event_user.id])],
        })

        # Manager
        cls.user_manager = cls.env['res.users'].create({
            'name': 'Responsable Event',
            'login': 'manager_event',
            'email': 'manager_event@school.local',
            'groups_id': [(6, 0, [cls.group_event_manager.id])],
        })

        # Parents & Students
        cls.partner_parent = cls.env['res.partner'].create({
            'name': 'Parent Event Test',
            'email': 'parent.event@example.com',
            'is_school_parent': True,
        })
        cls.user_parent = cls.env['res.users'].create({
            'name': 'Parent Event User',
            'login': 'parent_event_user',
            'email': 'parent.event@example.com',
            'partner_id': cls.partner_parent.id,
            'groups_id': [(6, 0, [cls.group_portal.id])],
        })

        cls.student_child = cls.env['eacta.student'].create({
            'name': 'Enfant Inscrit',
            'gender': 'male',
            'date_of_birth': date(2012, 5, 10),
            'parent_ids': [(6, 0, [cls.partner_parent.id])],
            'state': 'enrolled',
        })
        cls.student_other = cls.env['eacta.student'].create({
            'name': 'Autre Enfant',
            'gender': 'female',
            'date_of_birth': date(2012, 8, 20),
            'state': 'enrolled',
        })

        # Classes
        cls.class_1 = cls.env['eacta.class'].create({
            'name': 'Classe Sortie 1',
            'level': 'secondary',
            'academic_year_id': cls.academic_year.id,
            'teacher_id': cls.user_teacher_1.id,
            'student_ids': [(6, 0, [cls.student_child.id])],
        })
        cls.class_2 = cls.env['eacta.class'].create({
            'name': 'Classe Sortie 2',
            'level': 'secondary',
            'academic_year_id': cls.academic_year.id,
            'teacher_id': cls.user_teacher_2.id,
            'student_ids': [(6, 0, [cls.student_other.id])],
        })

    def test_01_event_lifecycle_and_workflow(self):
        """Vérifie le cycle de vie complet d'un événement (Brouillon -> Confirmé -> En cours -> Terminé)."""
        event = self.env['eacta.school.event'].create({
            'name': 'Visite Cité des Sciences',
            'event_type': 'outing',
            'date_start': fields.Datetime.now() + timedelta(days=5),
            'date_end': fields.Datetime.now() + timedelta(days=5, hours=4),
            'location': 'Rabat',
            'capacity': 30,
            'fee_amount': 50.0,
            'organizer_id': self.user_teacher_1.id,
            'class_ids': [(6, 0, [self.class_1.id])],
        })
        self.assertEqual(event.state, 'draft')

        # Passage à Confirmé
        event.action_confirm()
        self.assertEqual(event.state, 'confirmed')

        # Passage à En cours
        event.action_start()
        self.assertEqual(event.state, 'in_progress')

        # Passage à Terminé
        event.action_done()
        self.assertEqual(event.state, 'done')

        # Annulation
        event.action_cancel()
        self.assertEqual(event.state, 'cancel')

        # Remise en brouillon
        event.action_reset_draft()
        self.assertEqual(event.state, 'draft')

    def test_02_class_bulk_registration_and_capacity_limits(self):
        """Vérifie l'inscription automatique d'une classe et le contrôle strict de la capacité."""
        student_extra = self.env['eacta.student'].create({
            'name': 'Élève Supplémentaire',
            'gender': 'male',
            'state': 'enrolled',
        })
        self.class_1.write({'student_ids': [(4, student_extra.id)]})

        event = self.env['eacta.school.event'].create({
            'name': 'Excursion Botanique',
            'event_type': 'outing',
            'capacity': 1,  # Capacité volontairement trop faible (1 place pour 2 élèves)
            'class_ids': [(6, 0, [self.class_1.id])],
        })

        # 1. Inscription de la classe : remplit la seule place disponible (capacité = 1)
        event.action_register_classes()
        self.assertEqual(len(event.registration_ids), 1)

        # 2. Une 2e tentative d'inscription automatique lève UserError car complet
        with self.assertRaises(UserError):
            event.action_register_classes()

        # 3. Forcer une inscription manuelle au-delà de la capacité lève ValidationError
        with self.assertRaises(ValidationError):
            self.env['eacta.school.event.registration'].create({
                'event_id': event.id,
                'student_id': student_extra.id,
            })

        # 4. Élargissement de la capacité et inscription du reste des élèves
        event.write({'capacity': 10})
        event.action_register_classes()
        self.assertEqual(len(event.registration_ids), 2)
        self.assertEqual(event.participant_count, 2)
        self.assertEqual(event.seats_available, 8)
        self.assertAlmostEqual(event.fill_rate, 20.0, places=1)

    def test_03_authorizations_and_attendance_statistics(self):
        """Vérifie le suivi des autorisations parentales et le pointage des présences."""
        event = self.env['eacta.school.event'].create({
            'name': 'Sortie Théâtre',
            'event_type': 'cultural',
            'requires_authorization': True,
            'fee_amount': 25.0,
            'class_ids': [(6, 0, [self.class_1.id])],
        })
        event.action_register_classes()
        reg = event.registration_ids.filtered(lambda r: r.student_id == self.student_child)
        self.assertTrue(reg)
        self.assertFalse(reg.authorized)
        self.assertFalse(reg.authorization_date)

        # Enregistrement de l'autorisation parentale
        reg.write({'authorized': True, 'authorization_date': fields.Date.today()})
        self.assertEqual(event.authorized_count, 1)

        # Pointage présence
        reg.action_mark_attended()
        self.assertEqual(reg.state, 'attended')
        self.assertEqual(event.attended_count, 1)

        # Rapport imprimable d'autorisation
        report = event.action_print_authorizations()
        self.assertTrue(report)

    def test_04_security_and_record_rules_isolation(self):
        """Vérifie le cloisonnement des règles d'enregistrement pour enseignants et parents."""
        event_1 = self.env['eacta.school.event'].create({
            'name': 'Sortie Classe 1 Prof 1',
            'organizer_id': self.user_teacher_1.id,
            'class_ids': [(6, 0, [self.class_1.id])],
        })
        event_1.action_register_classes()

        event_2 = self.env['eacta.school.event'].create({
            'name': 'Sortie Classe 2 Prof 2',
            'organizer_id': self.user_teacher_2.id,
            'class_ids': [(6, 0, [self.class_2.id])],
        })
        event_2.action_register_classes()

        # Enseignant 1 ne doit voir que son propre événement
        events_t1 = self.env['eacta.school.event'].with_user(self.user_teacher_1).search([
            ('id', 'in', [event_1.id, event_2.id])
        ])
        self.assertIn(event_1, events_t1)
        self.assertNotIn(event_2, events_t1)

        # Parent ne doit voir que l'inscription de son enfant
        regs_parent = self.env['eacta.school.event.registration'].with_user(self.user_parent).search([])
        child_regs = regs_parent.filtered(lambda r: r.student_id == self.student_child)
        other_regs = regs_parent.filtered(lambda r: r.student_id == self.student_other)
        self.assertTrue(child_regs)
        self.assertFalse(other_regs)

        # Responsable voit les deux événements
        events_mgr = self.env['eacta.school.event'].with_user(self.user_manager).search([
            ('id', 'in', [event_1.id, event_2.id])
        ])
        self.assertEqual(len(events_mgr), 2)
