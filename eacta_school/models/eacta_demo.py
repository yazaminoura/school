import logging
import random
import unicodedata
from collections import defaultdict
from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from .sample_data import adopt_existing_records, sample_data_step, sample_records

_logger = logging.getLogger(__name__)

FATHER_NAMES = ['Pierre', 'Jean', 'Nicolas', 'Thomas', 'Philippe', 'Marc', 'Olivier', 'Laurent', 'Éric', 'Julien',
                'Karim', 'Youssef', 'Hassan', 'Omar', 'Rachid']
MOTHER_NAMES = ['Sophie', 'Isabelle', 'Nathalie', 'Claire', 'Camille', 'Julie', 'Céline', 'Sandrine', 'Aurélie',
                'Nadia', 'Leïla', 'Samira', 'Khadija', 'Salma', 'Imane']
CITIES = ['Rabat', 'Salé', 'Témara', 'Rabat Agdal', 'Rabat Hay Riad', 'Harhoura']
STREETS = ['Avenue Mohammed V', 'Rue Patrice Lumumba', 'Avenue Fal Ould Oumeir', 'Rue Oued Fès', 'Avenue Annakhil',
           'Boulevard Mehdi Ben Barka', 'Rue Ibn Sina', 'Avenue de France']

# Classes 2024-2025 -> classes 2026-2027 (rentrée de démonstration)
DEMO_PROMOTIONS = [
    ('class_3a_2024', 'class_5a_2026'),
    ('class_3b_2024', 'class_5b_2026'),
    ('class_4a_2024', 'class_6a_2026'),
    ('class_4b_2024', 'class_6b_2026'),
]


def _slug(text):
    text = unicodedata.normalize('NFD', text).encode('ascii', 'ignore').decode()
    return ''.join(c for c in text.lower() if c.isalnum() or c == '.')


class EactaStudentDemo(models.Model):
    _inherit = 'eacta.student'

    @api.model
    def _sample_data_adopt(self, module, path):
        """Appelé en tête de chaque fichier d'exemple : réutilise les enregistrements déjà présents."""
        adopt_existing_records(self.env, module, path)

    @api.model
    def _sample_year(self):
        """Année académique des données d'exemple (2026-2027), ou à défaut l'année en cours."""
        return self.env.ref('eacta_school.academic_year_2026_2027', raise_if_not_found=False) \
            or self.env['eacta.academic.year'].get_current_year()

    @api.model
    def _sample_classes(self, year=None):
        classes = sample_records(self.env, 'eacta.class')
        return classes.filtered(lambda c: c.academic_year_id == year) if year else classes

    # ------------------------------------------------------------------
    # Données de démonstration : familles et rentrée (avant notes et frais)
    # ------------------------------------------------------------------
    @api.model
    def _generate_demo_families(self):
        """Rentrée 2026-2027 et familles (parents partagés entre frères et sœurs), déterministe."""
        if not sample_data_step(self.env, 'families'):
            return
        self = self.with_context(tracking_disable=True, mail_create_nolog=True, mail_notrack=True)
        rng = random.Random(2027)
        ref = lambda xmlid: self.env.ref(f'eacta_school.{xmlid}', raise_if_not_found=False)

        # 0. Ouvrir l'année d'exemple si aucune année n'est encore ouverte
        sample_year = ref('academic_year_2026_2027')
        Year = self.env['eacta.academic.year']
        if sample_year and sample_year.state == 'draft' and not Year.search_count([('state', '=', 'open')]):
            sample_year.state = 'open'

        # 1. Les élèves de 2024-2025 passent dans les classes de l'année en cours
        for src_xmlid, dst_xmlid in DEMO_PROMOTIONS:
            src, dst = ref(src_xmlid), ref(dst_xmlid)
            if not src or not dst:
                continue
            movers = src.student_ids.filtered(lambda s: dst.academic_year_id not in s.class_ids.academic_year_id)
            free = (dst.capacity or len(movers)) - len(dst.student_ids)
            for student in movers[:max(free, 0)]:
                student.write({'class_ids': [(4, dst.id)]})

        # 2. Familles : élèves de même nom regroupés par fratries de 1 à 3 enfants
        Partner = self.env['res.partner']
        by_surname = defaultdict(list)
        sample_students = sample_records(self.env, 'eacta.student')
        for student in sample_students.filtered(lambda s: not s.parent_ids).sorted(
                lambda s: (s.date_of_birth or fields.Date.to_date('9999-12-31'), s.id)):
            by_surname[student.name.split()[-1]].append(student)
        family_no = 0
        for surname in sorted(by_surname):
            kids = by_surname[surname]
            i = 0
            while i < len(kids):
                size = rng.choice((1, 2, 2, 3))
                family = self.browse([k.id for k in kids[i:i + size]])
                i += size
                family_no += 1
                city = rng.choice(CITIES)
                street = f"{rng.randint(2, 180)} {rng.choice(STREETS)}"
                father = rng.choice(FATHER_NAMES)
                parents = Partner.create({
                    'name': f"M. {father} {surname}",
                    'email': f"{_slug(father)}.{_slug(surname)}{family_no}@demo.nrschool.com",
                    'phone': f"+212 6{rng.randint(10, 79)} {rng.randint(100000, 999999)}",
                    'street': street,
                    'city': city,
                    'is_school_parent': True,
                })
                if rng.random() < 0.6:
                    mother = rng.choice(MOTHER_NAMES)
                    parents |= Partner.create({
                        'name': f"Mme {mother} {surname}",
                        'email': f"{_slug(mother)}.{_slug(surname)}{family_no}@demo.nrschool.com",
                        'phone': f"+212 6{rng.randint(10, 79)} {rng.randint(100000, 999999)}",
                        'street': street,
                        'city': city,
                        'is_school_parent': True,
                    })
                contact = parents[-1]
                for student in family:
                    vals = {'parent_ids': [(4, p.id) for p in parents]}
                    if not student.emergency_contact_name:
                        vals.update({
                            'emergency_contact_name': contact.name,
                            'emergency_contact_phone': contact.phone,
                            'emergency_contact_relation': 'Mère' if contact.name.startswith('Mme') else 'Père',
                        })
                    student.write(vals)

    # ------------------------------------------------------------------
    # Données de démonstration : vie scolaire (après notes et frais)
    # ------------------------------------------------------------------
    @api.model
    def _generate_demo_life(self):
        """Transport, cantine, assiduité des dernières semaines et bulletins du trimestre, déterministe."""
        if not sample_data_step(self.env, 'life', 'eacta.attendance'):
            return
        self = self.with_context(tracking_disable=True, mail_create_nolog=True, mail_notrack=True)
        rng = random.Random(2028)
        ref = lambda xmlid: self.env.ref(f'eacta_school.{xmlid}', raise_if_not_found=False)
        today = fields.Date.context_today(self)
        year = self._sample_year()
        if not year:
            return
        classes = self._sample_classes(year)
        students = classes.student_ids.filtered(lambda s: s.state in ('draft', 'enrolled')).sorted('id')
        if not students:
            return

        # 1. Transport scolaire et cantine
        lines = [line for line in (ref('demo_transport_line_1'), ref('demo_transport_line_2'),
                                   ref('demo_transport_line_3')) if line and line.stop_ids]
        riders = students.filtered(lambda s: not s.transport_line_id)
        riders = riders.filtered(lambda s: rng.random() < 0.55)
        for line in lines:
            free = line.capacity - len(line.passenger_ids) - 2
            for k, student in enumerate(riders[:max(free, 0)]):
                student.write({
                    'transport_mode': 'bus',
                    'transport_line_id': line.id,
                    'transport_stop_id': line.stop_ids[k % len(line.stop_ids)].id,
                })
            riders = riders[max(free, 0):]
        for student in students:
            vals = {'canteen': rng.random() < 0.6}
            if not student.transport_line_id and rng.random() < 0.25:
                vals['transport_mode'] = 'autonomous'
            student.write(vals)

        # 2. Assiduité des 6 dernières semaines (jours ouvrés, sans notifier les familles)
        start = max(year.date_start, today - timedelta(days=42))
        days = [start + timedelta(days=n) for n in range((today - start).days)]
        days = [d for d in days if d.weekday() < 5]
        reasons = ['illness', 'illness', 'family', 'appointment', 'transport', 'other']
        vals_list = []
        for student in students:
            p_absent = 0.07 if rng.random() < 0.15 else 0.02
            for day in days:
                r = rng.random()
                if r < p_absent:
                    session = rng.choice(('all_day', 'all_day', 'morning', 'afternoon'))
                    vals = {
                        'student_id': student.id, 'class_id': student.current_class_id.id, 'date': day,
                        'attendance_type': 'absent', 'session': session,
                        'duration_hours': 6.0 if session == 'all_day' else 3.0, 'notification_sent': True,
                    }
                    if rng.random() < 0.6:
                        vals.update({
                            'justified': True,
                            'reason': rng.choice(reasons),
                            'justification_date': min(day + timedelta(days=rng.randint(0, 2)), today),
                        })
                    vals_list.append(vals)
                elif r < p_absent + 0.025:
                    vals_list.append({
                        'student_id': student.id, 'class_id': student.current_class_id.id, 'date': day,
                        'attendance_type': 'late', 'session': 'morning', 'duration_hours': 0.25,
                        'notification_sent': True, 'justified': rng.random() < 0.3,
                    })
                    if vals_list[-1]['justified']:
                        vals_list[-1]['reason'] = 'transport'
        if vals_list:
            ICP = self.env['ir.config_parameter'].sudo()
            send_email = ICP.get_param('eacta_school.send_absence_parent_email', 'True')
            ICP.set_param('eacta_school.send_absence_parent_email', 'False')
            try:
                self.env['eacta.attendance'].create(vals_list)
            finally:
                ICP.set_param('eacta_school.send_absence_parent_email', send_email)

        # 3. Bulletins des trimestres déjà commencés
        terms = year.term_ids.filtered(lambda t: t.date_start and t.date_start <= today) or year.term_ids[:1]
        for term in terms:
            try:
                with self.env.cr.savepoint():
                    self.env['eacta.student.result'].compute_all_results(academic_year=year, term=term)
            except Exception:
                _logger.warning("Bulletins de démonstration non générés pour %s", term.display_name, exc_info=True)

    # ------------------------------------------------------------------
    # Données de démonstration : cahier de textes, vie scolaire, santé, cantine, Massar, personnel
    # ------------------------------------------------------------------
    @api.model
    def _generate_demo_extras(self):
        """Démonstration des modules de vie scolaire, déterministe et sans envoi d'emails."""
        if not sample_data_step(self.env, 'extras', 'eacta.lesson'):
            return
        self = self.with_context(tracking_disable=True, mail_create_nolog=True, mail_notrack=True)
        rng = random.Random(2029)
        today = fields.Date.context_today(self)
        year = self._sample_year()
        if not year:
            return
        classes = self._sample_classes(year).sorted('name')
        students = classes.student_ids.filtered(lambda s: s.state in ('draft', 'enrolled')).sorted('id')
        if not students:
            return
        school_days = [today - timedelta(days=n) for n in range(1, 43)]
        school_days = [d for d in school_days if d.weekday() < 5 and d >= year.date_start] or [today]
        ref = lambda xmlid: self.env.ref(f'eacta_school.{xmlid}', raise_if_not_found=False)

        # 1. Codes Massar (quelques élèves restent à compléter)
        for n, student in enumerate(students):
            if not student.massar_code and n % 11:
                student.massar_code = f"{'JKLMN'[n % 5]}1{30000000 + student.id:08d}"

        # 2. Cahier de textes et devoirs
        topics = {
            'MATH101': ['Nombres relatifs', 'Fractions', 'Équations du 1er degré', 'Théorème de Pythagore'],
            'FRA101': ['Le récit fantastique', 'Les figures de style', 'Le discours rapporté', 'Lecture suivie'],
            'SCI101': ['La cellule', 'Les états de la matière', 'Le circuit électrique', 'La respiration'],
            'ENG101': ['Present perfect', 'Describing people', 'Past simple vs continuous', 'Reading comprehension'],
            'HIS101': ['Les Almoravides', 'La dynastie saadienne', 'Les grandes découvertes', 'Le Maroc au XIXe siècle'],
            'GEO101': ['Les reliefs du Maroc', 'Le climat', 'Les villes et la population', "L'eau, une ressource rare"],
            'ART101': ['Les couleurs primaires', 'Le zellige', 'La perspective', 'Le portrait'],
        }
        Lesson = self.env['eacta.lesson']
        Homework = self.env['eacta.homework']
        for klass in classes:
            for course in klass.course_ids:
                chapters = topics.get(course.code, ['Introduction', 'Approfondissement', 'Exercices', 'Synthèse'])
                teacher = course.teacher_id or klass.teacher_id
                days = sorted(rng.sample(school_days, min(3, len(school_days))))
                for k, day in enumerate(days):
                    chapter = chapters[k % len(chapters)]
                    lesson = Lesson.create({
                        'name': f"{chapter} - séance {k + 1}",
                        'date': day,
                        'class_id': klass.id,
                        'course_id': course.id,
                        'teacher_id': teacher.id,
                        'content': f"<p>Notions abordées : {chapter.lower()}. "
                                   f"Activités en binômes puis correction collective.</p>",
                    })
                    if k == len(days) - 1:
                        Homework.create({
                            'name': f"Exercices de révision : {chapter}",
                            'homework_type': rng.choice(('exercise', 'reading', 'revision')),
                            'class_id': klass.id,
                            'course_id': course.id,
                            'teacher_id': teacher.id,
                            'lesson_id': lesson.id,
                            'date_assigned': day,
                            'due_date': day + timedelta(days=rng.randint(2, 9)),
                            'description': '<p>Faire les exercices du manuel et relire la leçon.</p>',
                            'state': 'published' if rng.random() < 0.85 else 'draft',
                        })
                if rng.random() < 0.5:
                    Homework.create({
                        'name': f"Exposé : {rng.choice(chapters)}",
                        'homework_type': 'project',
                        'class_id': klass.id,
                        'course_id': course.id,
                        'teacher_id': teacher.id,
                        'date_assigned': today,
                        'due_date': today + timedelta(days=rng.randint(10, 25)),
                        'estimated_minutes': 120,
                        'state': 'published',
                    })

        # 3. Vie scolaire : incidents, comportements positifs, sanctions
        negative = [t for t in (ref('incident_type_lateness'), ref('incident_type_disruption'),
                                ref('incident_type_homework'), ref('incident_type_phone'),
                                ref('incident_type_insolence'), ref('incident_type_cheating'),
                                ref('incident_type_violence')) if t]
        positive = [t for t in (ref('incident_type_help'), ref('incident_type_engagement')) if t]
        descriptions = {
            'minor': ["Bavardages répétés malgré plusieurs rappels.", "Arrivé sans ses affaires pour la 3e fois.",
                      "Utilisation du téléphone pendant le cours."],
            'major': ["Réponse insolente au professeur devant la classe.", "Antisèche trouvée pendant le contrôle."],
            'serious': ["Bagarre dans la cour à la récréation de 10h."],
        }
        Incident = self.env['eacta.discipline.incident']
        for n in range(min(30, len(students)) if negative else 0):
            student = students[rng.randrange(len(students))]
            is_positive = bool(positive) and rng.random() < 0.3
            itype = rng.choice(positive if is_positive else negative)
            incident = Incident.create({
                'student_id': student.id,
                'date': rng.choice(school_days),
                'type_id': itype.id,
                'location': rng.choice(('Salle de classe', 'Cour', 'Cantine', 'Couloir', 'Bibliothèque')),
                'description': "Aide spontanée à un camarade en difficulté." if is_positive
                else rng.choice(descriptions.get(itype.severity, descriptions['minor'])),
            })
            if n % 6 == 5:
                continue  # reste « signalé », à valider par la vie scolaire
            incident.state = 'confirmed'
            if itype.kind == 'negative' and itype.severity in ('major', 'serious'):
                serious = itype.severity == 'serious'
                start = incident.date + timedelta(days=1)
                self.env['eacta.discipline.sanction'].create({
                    'incident_id': incident.id,
                    'sanction_type': 'temporary_exclusion' if serious else 'written_warning',
                    'date': incident.date,
                    'date_from': start if serious else False,
                    'date_to': start + timedelta(days=1) if serious else False,
                    'note': "Décision prise après entretien avec l'élève et sa famille.",
                })
                incident.parent_notified = True

        # 4. Annonces aux classes d'exemple (publiées directement, sans envoi d'emails)
        Announcement = self.env['eacta.announcement']
        demo_announcements = [
            ("Réunion parents-professeurs du 1er trimestre", 'important', 'classes', classes,
             "<p>Chers parents, la réunion parents-professeurs se tiendra le samedi de 9h à 12h "
             "dans la salle polyvalente. Merci de confirmer votre présence.</p>", 6),
            ("Sortie au musée Mohammed VI : autorisation à rendre", 'normal', 'classes', classes[:2],
             "<p>Merci de retourner l'autorisation parentale signée avant vendredi.</p>", 3),
            ("Fermeture exceptionnelle de la cantine", 'urgent', 'classes', classes,
             "<p>En raison de travaux, la cantine sera fermée lundi. Prévoyez un repas froid.</p>", 1),
            ("Calendrier des contrôles de novembre", 'normal', 'classes', classes,
             "<p>Le calendrier des contrôles est disponible dans l'espace devoirs du portail.</p>", 9),
        ]
        for name, priority, audience, klasses, body, age in demo_announcements:
            announcement = Announcement.create({
                'name': name, 'priority': priority, 'audience': audience, 'body': body,
                'class_ids': [(6, 0, klasses.ids)],
            })
            announcement.write({'state': 'published',
                                'date_publish': fields.Datetime.now() - timedelta(days=age)})
            readers = announcement.recipient_partner_ids.filtered(lambda p: rng.random() < 0.55)
            self.env['eacta.announcement.read'].create([
                {'announcement_id': announcement.id, 'partner_id': p.id} for p in readers])
        Announcement.create({
            'name': "Journée portes ouvertes", 'audience': 'classes', 'priority': 'normal',
            'class_ids': [(6, 0, classes.ids)],
            'body': "<p>Venez découvrir l'école avec vos proches.</p>",
        })

        # 5. Santé : passages à l'infirmerie, vaccinations, certificats
        Visit = self.env['eacta.infirmary.visit']
        for _n in range(min(22, len(students))):
            student = students[rng.randrange(len(students))]
            reason = rng.choice(('headache', 'stomach', 'fever', 'injury', 'fatigue', 'allergy'))
            fever = reason == 'fever'
            day = rng.choice(school_days)
            Visit.create({
                'student_id': student.id,
                'visit_datetime': fields.Datetime.to_datetime(day) + timedelta(
                    hours=rng.randint(8, 15), minutes=rng.choice((0, 15, 30, 45))),
                'reason': reason,
                'temperature': round(rng.uniform(38.0, 39.2) if fever else rng.uniform(36.4, 37.2), 1),
                'symptoms': "Fièvre et frissons." if fever else "Se plaint de douleurs depuis le matin.",
                'treatment': "Mise au repos, parents appelés." if fever else "Repos et hydratation.",
                'outcome': 'sent_home' if fever else rng.choice(('back_to_class', 'back_to_class', 'rest')),
                'parent_notified': fever or rng.random() < 0.3,
                'follow_up': rng.random() < 0.15,
            })
        vaccinations = []
        for student in students.filtered(lambda s: s.id % 3 == 0):
            vaccinations += [
                {'student_id': student.id, 'vaccine': 'ROR', 'dose': '2e dose',
                 'date': fields.Date.to_date('2016-05-10')},
                {'student_id': student.id, 'vaccine': 'DTCP', 'dose': 'Rappel 11-13 ans',
                 'date': today - timedelta(days=rng.randint(30, 400)),
                 'next_due_date': today + timedelta(days=rng.randint(10, 700))},
            ]
        self.env['eacta.vaccination'].create(vaccinations)
        Certificate = self.env['eacta.medical.certificate']
        for k, student in enumerate(students[3::17][:4]):
            Certificate.create({
                'student_id': student.id,
                'certificate_type': 'sport_exemption' if k % 2 == 0 else 'sport_aptitude',
                'date_from': today - timedelta(days=20),
                'date_to': today + timedelta(days=40) if k % 2 == 0 else False,
                'doctor_name': rng.choice(('Dr. Benjelloun', 'Dr. Lahlou', 'Dr. Martin')),
            })

        # 6. Cantine : menus, abonnements des demi-pensionnaires, facturation du mois
        dishes = [
            ('Salade marocaine', 'Tajine de poulet aux olives', 'Tajine de légumes', 'Orange'),
            ('Harira', 'Couscous aux sept légumes', 'Couscous végétarien', 'Yaourt'),
            ('Salade de carottes', 'Poisson pané et riz', 'Omelette et riz', 'Banane'),
            ('Soupe de légumes', 'Kefta et pommes de terre', 'Lentilles aux légumes', 'Compote'),
            ('Taboulé', 'Pastilla au poulet', 'Pastilla aux légumes', 'Pomme'),
            ('Zaalouk', 'Poulet rôti et haricots verts', 'Gratin de légumes', 'Flan'),
        ]
        menus = []
        for n in range(-7, 15):
            day = today + timedelta(days=n)
            if day.weekday() >= 5:
                continue
            starter, main, veggie, dessert = dishes[day.toordinal() % len(dishes)]
            menus.append({'date': day, 'meal': 'lunch', 'starter': starter, 'main_course': main,
                          'vegetarian_option': veggie, 'dessert': dessert,
                          'allergens': 'gluten' if ('pané' in main or 'Pastilla' in main) else False})
        existing_days = set(self.env['eacta.canteen.menu'].search([
            ('date', 'in', [m['date'] for m in menus]), ('meal', '=', 'lunch')]).mapped('date'))
        self.env['eacta.canteen.menu'].create([m for m in menus if m['date'] not in existing_days])
        Subscription = self.env['eacta.canteen.subscription']
        diets = ['Sans porc', 'Sans gluten', 'Allergie aux arachides', 'Végétarien']
        subscriptions = Subscription
        for student in students.filtered('canteen'):
            plan = 'four_days' if rng.random() < 0.3 else 'full'
            subscriptions |= Subscription.create({
                'student_id': student.id,
                'academic_year_id': year.id,
                'plan': plan,
                'date_start': min(year.date_start, today),
                'monthly_price': 750.0 if plan == 'four_days' else 900.0,
                'diet_note': rng.choice(diets) if rng.random() < 0.12 else False,
            })
        if subscriptions and ref('fee_type_canteen'):
            subscriptions.action_generate_month_fee()

        # 7. Personnel : contrats et bulletins des deux derniers mois
        Contract = self.env['eacta.staff.contract']
        contracts = Contract
        sample_teachers = self.env['res.users'].browse([t.id for t in (
            ref('demo_teacher_amina'), ref('demo_teacher_youssef'), ref('demo_teacher_sara')) if t])
        for k, teacher in enumerate(sample_teachers):
            contracts |= Contract.create({
                'name': teacher.name, 'user_id': teacher.id, 'job': 'teacher',
                'contract_type': 'cdi', 'monthly_wage': 7500.0 + 500 * k,
                'date_start': fields.Date.to_date('2021-09-01'),
                'cin': f"AB{120000 + k * 731}", 'cnss_number': f"1{45000000 + k * 97}",
            })
        staff = [
            ('Nadia El Fassi', 'direction', 'cdi', 14000.0, 0.0),
            ('Hicham Ouazzani', 'admin', 'cdi', 5200.0, 0.0),
            ('Salma Bennis', 'admin', 'cdd', 4300.0, 0.0),
            ('Rachida Amrani', 'nurse', 'cdi', 5800.0, 0.0),
            ('Brahim Tahiri', 'supervisor', 'cdi', 3900.0, 0.0),
            ('Abdelaziz Berrada', 'driver', 'cdi', 3600.0, 0.0),
            ('Mustapha Chraibi', 'driver', 'cdd', 3500.0, 0.0),
            ('Fatiha Zerouali', 'canteen', 'cdi', 3300.0, 0.0),
            ('Ahmed Kettani', 'maintenance', 'cdi', 3200.0, 0.0),
            ('Imane Sqalli', 'teacher', 'vacataire', 0.0, 120.0),
        ]
        for k, (name, job, ctype, wage, rate) in enumerate(staff):
            contracts |= Contract.create({
                'name': name, 'job': job, 'contract_type': ctype, 'monthly_wage': wage, 'hourly_rate': rate,
                'date_start': fields.Date.to_date(f'{2018 + k % 6}-09-01'),
                'cin': f"C{300000 + k * 457}", 'cnss_number': f"1{52000000 + k * 113}",
                'phone': f"+212 6{rng.randint(10, 79)} {rng.randint(100000, 999999)}",
            })
        contracts.action_start()
        Payslip = self.env['eacta.payslip']
        for months_back in (2, 1):
            date_from = today.replace(day=1) - relativedelta(months=months_back)
            self.env['eacta.payslip.generate.wizard'].create({'month': date_from}).action_generate()
            slips = Payslip.search([('date_from', '=', date_from)])
            for slip in slips:
                vals = {'income_tax': round(max(slip.gross - 3500.0, 0.0) * 0.1, 2)}
                if slip.contract_type == 'vacataire':
                    vals['worked_hours'] = 48.0
                if rng.random() < 0.2:
                    vals['bonus'] = 500.0
                slip.write(vals)
            slips.action_confirm()
            if months_back == 2:
                slips.action_mark_paid()
