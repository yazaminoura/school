from datetime import date, timedelta
from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged
from ..models.eacta_notification import (
    sanitize_phone_number,
    build_whatsapp_url,
    format_absence_message,
    format_fee_reminder_message,
    format_grade_message,
)


@tagged('post_install', '-at_install')
class TestNewFeatures(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.academic_year = cls.env['eacta.academic.year'].search([('state', '=', 'open')], limit=1)
        if not cls.academic_year:
            cls.academic_year = cls.env['eacta.academic.year'].search([], limit=1)

        cls.term = cls.academic_year.term_ids[:1]
        if not cls.term:
            cls.term = cls.env['eacta.term'].create({
                'name': '1er Semestre TF',
                'academic_year_id': cls.academic_year.id,
                'date_start': cls.academic_year.date_start,
                'date_end': cls.academic_year.date_start + timedelta(days=120),
            })

        cls.level = cls.env['eacta.school.level'].search([], limit=1)
        if not cls.level:
            cls.level = cls.env['eacta.school.level'].create({
                'name': 'Collège TF',
                'sequence': 20,
            })

        cls.teacher = cls.env['res.users'].create({
            'name': 'Professeur Test TF',
            'login': 'prof_test_tf',
            'email': 'prof.test.tf@school.local',
            'is_teacher': True,
        })

        cls.klass = cls.env['eacta.class'].create({
            'name': '3ème A Test TF',
            'academic_year_id': cls.academic_year.id,
            'level_id': cls.level.id,
            'capacity': 30,
            'teacher_id': cls.teacher.id,
        })

        cls.course = cls.env['eacta.course'].create({
            'name': 'Mathématiques TF',
            'code': 'MATH-TF',
            'coefficient': 4.0,
            'teacher_id': cls.teacher.id,
            'class_ids': [(4, cls.klass.id)],
        })

        cls.parent = cls.env['res.partner'].create({
            'name': 'Parent Benali TF',
            'phone': '0522123456',
            'mobile': '0661122334',
            'email': 'parent.benali.tf@example.com',
        })

        cls.student_1 = cls.env['eacta.student'].create({
            'name': 'Mehdi Benali TF',
            'current_class_id': cls.klass.id,
            'class_ids': [(4, cls.klass.id)],
            'parent_ids': [(4, cls.parent.id)],
            'state': 'enrolled',
            'phone': '0661122334',
        })

        cls.student_2 = cls.env['eacta.student'].create({
            'name': 'Salma Benali TF',
            'current_class_id': cls.klass.id,
            'class_ids': [(4, cls.klass.id)],
            'parent_ids': [(4, cls.parent.id)],
            'state': 'enrolled',
        })

        cls.fee_type = cls.env['eacta.fee.type'].search([], limit=1)
        if not cls.fee_type:
            cls.fee_type = cls.env['eacta.fee.type'].create({
                'name': 'Mensualité Octobre TF',
                'default_amount': 2500.0,
            })

    def test_01_phone_sanitization_and_whatsapp_urls(self):
        """Vérifie le formatage et le nettoyage des numéros WhatsApp."""
        self.assertEqual(sanitize_phone_number('06 12 34 56 78', '212'), '212612345678')
        self.assertEqual(sanitize_phone_number('+212 661-12-23-34', '212'), '212661122334')
        self.assertEqual(sanitize_phone_number('00212670112233', '212'), '212670112233')
        self.assertEqual(sanitize_phone_number('661234567', '212'), '212661234567')
        self.assertFalse(sanitize_phone_number('12345', '212'))
        self.assertFalse(sanitize_phone_number('', '212'))

        url = build_whatsapp_url('0661122334', 'Bonjour Test!', default_country='212')
        self.assertTrue(url.startswith('https://wa.me/212661122334?text='))
        self.assertIn('Bonjour%20Test%21', url)

    def test_02_whatsapp_attendance_flow(self):
        """Vérifie l'action et l'assistant WhatsApp sur l'assiduité."""
        attendance = self.env['eacta.attendance'].create({
            'student_id': self.student_1.id,
            'class_id': self.klass.id,
            'date': fields.Date.today(),
            'session': 'morning',
            'attendance_type': 'absent',
            'justified': False,
        })

        # Test génération message
        msg = format_absence_message(attendance, signature="Vie Scolaire")
        self.assertIn("Mehdi Benali TF", msg)
        self.assertIn("absent(e)", msg)

        # Action d'ouverture
        action = attendance.action_send_whatsapp_alert()
        self.assertEqual(action['res_model'], 'eacta.whatsapp.composer')

        # Test Assistant
        wiz = self.env['eacta.whatsapp.composer'].with_context(
            active_model='eacta.attendance',
            active_id=attendance.id,
        ).create({})
        self.assertEqual(wiz.attendance_id, attendance)
        self.assertEqual(wiz.student_id, self.student_1)
        self.assertEqual(wiz.mobile, '0661122334')
        self.assertIn('Mehdi Benali TF', wiz.body)

        # Envoi
        send_act = wiz.action_send_whatsapp()
        self.assertEqual(send_act['type'], 'ir.actions.act_url')
        self.assertTrue(attendance.notification_sent)
        self.assertIn(self.parent, attendance.notified_parent_ids)

    def test_03_whatsapp_fee_reminder_flow(self):
        """Vérifie l'action et l'assistant WhatsApp sur les frais de scolarité."""
        fee = self.env['eacta.student.fee'].create({
            'student_id': self.student_1.id,
            'class_id': self.klass.id,
            'fee_type_id': self.fee_type.id,
            'amount': 2500.0,
            'due_date': fields.Date.today() - timedelta(days=5),
        })

        msg = format_fee_reminder_message(fee, signature="Comptabilité")
        self.assertIn("2500", msg)
        self.assertIn("Mehdi Benali TF", msg)

        action = fee.action_send_whatsapp_reminder()
        self.assertEqual(action['res_model'], 'eacta.whatsapp.composer')

        wiz = self.env['eacta.whatsapp.composer'].with_context(
            active_model='eacta.student.fee',
            active_id=fee.id,
        ).create({})
        self.assertEqual(wiz.fee_id, fee)
        send_act = wiz.action_send_whatsapp()
        self.assertEqual(send_act['type'], 'ir.actions.act_url')
        self.assertEqual(fee.reminder_count, 1)

    def test_04_teacher_fast_grade_grid(self):
        """Vérifie la grille de saisie rapide des notes et calcul des stats."""
        # Initialisation de l'assistant pour la classe et le cours
        wiz = self.env['eacta.grade.sheet.wizard'].create({
            'class_id': self.klass.id,
            'course_id': self.course.id,
            'new_exam_name': 'Contrôle 1 - Algèbre TF',
            'exam_date': fields.Date.today(),
            'exam_type': 'quiz',
            'term_id': self.term.id,
            'academic_year_id': self.academic_year.id,
        })
        wiz.action_load_students()
        self.assertEqual(wiz.student_count, 2)

        # Renseignement des notes dans les lignes
        lines = wiz.line_ids.sorted('student_name')
        lines[0].write({'grade': 16.0, 'status': 'graded', 'comment': 'Très bon travail'})
        lines[1].write({'grade': 12.0, 'status': 'graded', 'comment': 'Bon travail'})

        # Vérification des statistiques calculées en direct
        self.assertEqual(wiz.graded_count, 2)
        self.assertEqual(wiz.class_average, 14.0)
        self.assertEqual(wiz.max_grade, 16.0)
        self.assertEqual(wiz.min_grade, 12.0)
        self.assertEqual(wiz.success_rate, 100.0)

        # Enregistrement des notes
        wiz.action_save_grades()

        # Vérification qu'un examen a bien été créé
        exam = self.env['eacta.exam'].search([('name', '=', 'Contrôle 1 - Algèbre TF')], limit=1)
        self.assertTrue(exam)
        self.assertEqual(exam.course_id, self.course)
        self.assertEqual(exam.graded_count, 2)
        self.assertEqual(exam.average, 14.0)

        # Vérification de l'action rapide depuis l'examen
        exam_fast_act = exam.action_open_fast_grade_grid()
        self.assertEqual(exam_fast_act['res_model'], 'eacta.grade.sheet.wizard')

    def test_05_executive_dashboard_kpis(self):
        """Vérifie les métriques calculées pour le tableau de bord exécutif."""
        fee = self.env['eacta.student.fee'].create({
            'student_id': self.student_2.id,
            'class_id': self.klass.id,
            'fee_type_id': self.fee_type.id,
            'amount': 3000.0,
            'due_date': fields.Date.today() + timedelta(days=10),
        })

        finance_data = self.env['eacta.student']._get_dashboard_finance()
        self.assertTrue(finance_data['finance'])
        self.assertIn('collection_rate', finance_data)
        self.assertIn('total_invoiced', finance_data)
        self.assertIn('total_collected', finance_data)
        self.assertIn('fees_due', finance_data)

        dash_data = self.env['eacta.student'].get_school_dashboard_data()
        self.assertIn('attendance_rate', dash_data['kpis'])
        self.assertIn('honor_count', dash_data['kpis'])
        self.assertIn('warning_count', dash_data['kpis'])
        self.assertIn('cycle_absences', dash_data)

    def test_06_student_timetable_portal(self):
        """Vérifie l'accès à l'emploi du temps (استعمال الزمن) pour l'élève."""
        slot = self.env['eacta.timetable.slot'].create({
            'class_id': self.klass.id,
            'course_id': self.course.id,
            'teacher_id': self.teacher.id,
            'weekday': '0',
            'hour_from': 8.5,
            'hour_to': 10.5,
            'room': 'Salle 101',
        })
        slots = self.env['eacta.timetable.slot'].search([
            ('class_id', '=', self.student_1.current_class_id.id),
        ], order='weekday, hour_from')
        self.assertIn(slot, slots)
        self.assertEqual(slot.weekday, '0')
        self.assertEqual(slot.hour_from, 8.5)
        self.assertEqual(slot.hour_to, 10.5)
        self.assertEqual(slot.room, 'Salle 101')
