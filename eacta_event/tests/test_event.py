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

        # Avant confirmation, les parents ne voient pas les événements en brouillon
        regs_parent_draft = self.env['eacta.school.event.registration'].with_user(self.user_parent).search([])
        self.assertFalse(regs_parent_draft.filtered(lambda r: r.student_id == self.student_child))

        # Confirmation des événements
        event_1.action_confirm()
        event_2.action_confirm()

        # Après confirmation, le parent ne doit voir que l'inscription de son propre enfant
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

    def test_05_event_expenses_and_financial_margin(self):
        """Vérifie la gestion des dépenses et le calcul du bilan financier (marge nette, surplus/déficit)."""
        event = self.env['eacta.school.event'].create({
            'name': 'Excursion Musée',
            'event_type': 'outing',
            'fee_amount': 100.0,
            'capacity': 10,
            'class_ids': [(6, 0, [self.class_1.id])],
        })
        event.action_register_classes()
        # 1 élève inscrit, mettons-le en payé
        reg = event.registration_ids[0]
        reg.write({'paid': True})

        self.assertEqual(event.amount_collected, 100.0)
        self.assertEqual(event.total_expenses, 0.0)
        self.assertEqual(event.net_margin, 100.0)
        self.assertEqual(event.financial_result_status, 'profit')

        # Ajout d'une dépense de transport
        self.env['eacta.school.event.expense'].create({
            'event_id': event.id,
            'name': 'Location Autocar',
            'expense_type': 'transport',
            'amount': 70.0,
            'state': 'planned',
        })
        self.assertEqual(event.total_expenses, 70.0)
        self.assertEqual(event.net_margin, 30.0)
        self.assertEqual(event.financial_result_status, 'profit')

        # Ajout d'une dépense imprévue rendant l'événement déficitaire
        self.env['eacta.school.event.expense'].create({
            'event_id': event.id,
            'name': 'Guides Supplémentaires',
            'expense_type': 'tickets',
            'amount': 50.0,
            'state': 'paid',
        })
        self.assertEqual(event.total_expenses, 120.0)
        self.assertEqual(event.net_margin, -20.0)
        self.assertEqual(event.financial_result_status, 'deficit')

        # Action d'ouverture des dépenses
        action = event.action_view_expenses()
        self.assertEqual(action['res_model'], 'eacta.school.event.expense')

    def test_06_field_trip_logistics_and_safety_ratios(self):
        """Vérifie les paramètres logistiques, les vérifications de sécurité et le ratio d'encadrement."""
        event = self.env['eacta.school.event'].create({
            'name': 'Sortie Montagne',
            'event_type': 'outing',
            'transport_type': 'charter_bus',
            'transport_company': 'Trans Atlas SARL',
            'driver_contact': 'Mohamed (+212 600000000)',
            'vehicle_plate': '12345-A-1',
            'departure_meeting_point': 'Portail Principal Collège',
            'emergency_contact': 'Mme Direction',
            'emergency_phone': '+212 522000000',
            'first_aid_kit': True,
            'safety_briefing_done': True,
            'organizer_id': self.user_teacher_1.id,
            'supervisor_ids': [(6, 0, [self.user_teacher_2.id])],
            'class_ids': [(6, 0, [self.class_1.id, self.class_2.id])],
        })
        event.action_register_classes()
        # 2 élèves inscrits, 2 encadrants (1 organisateur + 1 accompagnateur) -> ratio 1.0 élève par encadrant
        self.assertEqual(event.participant_count, 2)
        self.assertAlmostEqual(event.supervisor_ratio, 1.0, places=1)

    def test_07_medical_alerts_and_pai_surfacing(self):
        """Vérifie la détection et la consolidation des alertes médicales / PAI pour les sorties."""
        # Définition d'une allergie sur l'élève
        self.student_child.write({
            'allergies': 'Arachides sévère (Emporte EpiPen)',
            'medical_notes': 'Protocole PAI actif - contacter infirmière.',
        })

        event = self.env['eacta.school.event'].create({
            'name': 'Visite Ferme Pédagogique',
            'event_type': 'outing',
            'class_ids': [(6, 0, [self.class_1.id])],
        })
        event.action_register_classes()

        self.assertGreaterEqual(event.medical_alert_count, 1)
        self.assertIn('Arachides', event.medical_alert_summary)
        self.assertIn(self.student_child.name, event.medical_alert_summary)

        # Action d'ouverture de la fiche médicale
        action = event.action_view_medical_sheet()
        self.assertEqual(action['res_model'], 'eacta.student')

    def test_08_portal_online_parental_authorization_and_reminders(self):
        """Vérifie l'autorisation parentale en ligne via le portail et les relances automatiques."""
        event = self.env['eacta.school.event'].create({
            'name': 'Sortie Musée Mohammed VI',
            'event_type': 'cultural',
            'requires_authorization': True,
            'class_ids': [(6, 0, [self.class_1.id])],
        })
        event.action_register_classes()
        reg = event.registration_ids.filtered(lambda r: r.student_id == self.student_child)
        self.assertFalse(reg.authorized)
        self.assertEqual(reg.authorization_method, 'paper')

        # Le parent valide l'autorisation en ligne
        reg.action_authorize_online(parent_partner=self.partner_parent)
        self.assertTrue(reg.authorized)
        self.assertEqual(reg.authorization_method, 'portal')
        self.assertEqual(reg.authorized_by_parent_id, self.partner_parent)
        self.assertEqual(reg.authorization_date, fields.Date.today())

        # Relance des parents pour les autorisations manquantes
        # Inscription d'un 2e élève non autorisé via une nouvelle classe
        student_unauth = self.env['eacta.student'].create({
            'name': 'Élève Sans Accord',
            'gender': 'male',
            'state': 'enrolled',
        })
        class_extra = self.env['eacta.class'].create({
            'name': 'Classe Découverte',
            'level': 'secondary',
            'academic_year_id': self.academic_year.id,
            'teacher_id': self.user_teacher_1.id,
            'student_ids': [(6, 0, [student_unauth.id])],
        })
        event.write({
            'capacity': 20,
            'class_ids': [(4, class_extra.id)],
        })
        event.action_register_classes()

        reminder_action = event.action_send_parent_reminders()
        self.assertEqual(reminder_action.get('type'), 'ir.actions.client')
        self.assertEqual(reminder_action.get('tag'), 'display_notification')

