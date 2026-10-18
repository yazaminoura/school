from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import ValidationError

WEEKDAYS = [
    ('0', 'Lundi'),
    ('1', 'Mardi'),
    ('2', 'Mercredi'),
    ('3', 'Jeudi'),
    ('4', 'Vendredi'),
    ('5', 'Samedi'),
]


def _fmt_hour(value):
    hours = int(value)
    minutes = int(round((value - hours) * 60))
    return f"{hours:02d}:{minutes:02d}"


class EactaTimetableSlot(models.Model):
    _name = 'eacta.timetable.slot'
    _description = "Créneau d'emploi du temps"
    _order = 'class_id, weekday, hour_from'

    class_id = fields.Many2one('eacta.class', string='Classe', required=True, ondelete='cascade', index=True)
    academic_year_id = fields.Many2one(
        'eacta.academic.year', string='Année académique',
        related='class_id.academic_year_id', store=True, index=True)
    year = fields.Char(related='academic_year_id.name', store=True, string='Année')

    @property
    def year_id(self):
        return self.academic_year_id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'year_id' in vals and 'academic_year_id' not in vals:
                vals['academic_year_id'] = vals.pop('year_id')
        return super().create(vals_list)

    def write(self, vals):
        if 'year_id' in vals and 'academic_year_id' not in vals:
            vals['academic_year_id'] = vals.pop('year_id')
        return super().write(vals)

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None):
        def _remap(term):
            if isinstance(term, (list, tuple)) and len(term) == 3 and term[0] == 'year_id':
                return ('academic_year_id', term[1], term[2])
            return term
        remapped_domain = [_remap(term) for term in domain] if domain else domain
        return super()._search(remapped_domain, offset=offset, limit=limit, order=order)
    course_id = fields.Many2one('eacta.course', string='Matière', required=True, ondelete='cascade',
                                domain="[('id', 'in', allowed_course_ids)]")
    allowed_course_ids = fields.Many2many('eacta.course', compute='_compute_allowed_course_ids')
    teacher_id = fields.Many2one('res.users', string='Enseignant', compute='_compute_teacher_id', store=True,
                                 readonly=False, domain="[('is_teacher', '=', True)]", index=True)
    weekday = fields.Selection(WEEKDAYS, string='Jour', required=True, default='0')
    hour_from = fields.Float(string='Début', required=True, default=8.0)
    hour_to = fields.Float(string='Fin', required=True, default=10.0)
    duration = fields.Float(string='Durée (h)', compute='_compute_duration', store=True)
    room = fields.Char(string='Salle')
    color = fields.Integer(related='course_id.color', string='Couleur')
    note = fields.Char(string='Remarque')
    active = fields.Boolean(default=True)

    @api.constrains('teacher_id', 'course_id')
    def _check_teacher_teaches_course(self):
        for slot in self:
            if slot.teacher_id and slot.course_id and slot.course_id.teacher_id:
                if slot.teacher_id != slot.course_id.teacher_id:
                    raise ValidationError(
                        f"L'enseignant « {slot.teacher_id.name} » n'est pas l'enseignant assigné "
                        f"au cours « {slot.course_id.name} » ({slot.course_id.teacher_id.name})."
                    )

    @api.depends('class_id.course_ids')
    def _compute_allowed_course_ids(self):
        all_courses = self.env['eacta.course'].search([])
        for slot in self:
            slot.allowed_course_ids = slot.class_id.course_ids or all_courses

    @api.depends('course_id')
    def _compute_teacher_id(self):
        for slot in self:
            if slot.course_id.teacher_id:
                slot.teacher_id = slot.course_id.teacher_id

    @api.depends('hour_from', 'hour_to')
    def _compute_duration(self):
        for slot in self:
            slot.duration = max(slot.hour_to - slot.hour_from, 0.0)

    @api.depends('course_id', 'weekday', 'hour_from', 'hour_to')
    def _compute_display_name(self):
        days = dict(WEEKDAYS)
        for slot in self:
            slot.display_name = (f"{slot.course_id.name or ''} — {days.get(slot.weekday, '')} "
                                 f"{_fmt_hour(slot.hour_from)}-{_fmt_hour(slot.hour_to)}")

    @api.constrains('hour_from', 'hour_to')
    def _check_hours(self):
        for slot in self:
            if not (0 <= slot.hour_from < slot.hour_to <= 24):
                raise ValidationError("L'heure de fin doit être postérieure à l'heure de début (entre 0h et 24h).")

    @api.constrains('class_id', 'teacher_id', 'room', 'weekday', 'hour_from', 'hour_to', 'active')
    def _check_conflicts(self):
        for slot in self.filtered('active'):
            base = [
                ('id', '!=', slot.id),
                ('active', '=', True),
                ('weekday', '=', slot.weekday),
                ('academic_year_id', '=', slot.academic_year_id.id),
                ('hour_from', '<', slot.hour_to),
                ('hour_to', '>', slot.hour_from),
            ]
            checks = [
                ([('class_id', '=', slot.class_id.id)], f"la classe {slot.class_id.display_name}"),
            ]
            if slot.teacher_id:
                checks.append(([('teacher_id', '=', slot.teacher_id.id)], f"l'enseignant {slot.teacher_id.name}"))
            if slot.room:
                checks.append(([('room', '=ilike', slot.room)], f"la salle {slot.room}"))
            for extra, label in checks:
                others = self.search(base + extra)
                for other in others:
                    # Respect class start/end dates: if class date ranges do not overlap, no conflict!
                    c1_start = slot.class_id.start_date
                    c1_end = slot.class_id.end_date
                    c2_start = other.class_id.start_date
                    c2_end = other.class_id.end_date
                    if c1_start and c1_end and c2_start and c2_end:
                        if c1_end < c2_start or c1_start > c2_end:
                            continue
                    raise ValidationError(
                        f"Conflit d'emploi du temps pour {label} : « {other.display_name} » "
                        f"({other.class_id.display_name}) chevauche ce créneau."
                    )

    @api.model
    def get_timetable_data(self, mode, record_id):
        """Données de la grille hebdomadaire pour une classe, un enseignant ou une salle."""
        if mode == 'class':
            domain = [('class_id', '=', record_id)]
        elif mode == 'teacher':
            domain = [('teacher_id', '=', record_id)]
        else:
            domain = [('room', '=ilike', record_id)]
        slots = self.search(domain)
        start = min([8.0] + slots.mapped('hour_from'))
        end = max([18.0] + slots.mapped('hour_to'))
        return {
            'days': [{'key': key, 'label': label} for key, label in WEEKDAYS],
            'start': int(start),
            'end': int(end + 0.99),
            'slots': [{
                'id': s.id,
                'weekday': s.weekday,
                'from': s.hour_from,
                'to': s.hour_to,
                'label_from': _fmt_hour(s.hour_from),
                'label_to': _fmt_hour(s.hour_to),
                'course': s.course_id.name,
                'class': s.class_id.display_name,
                'teacher': s.teacher_id.name or '',
                'room': s.room or '',
                'color': s.color or (s.course_id.id % 11) + 1,
            } for s in slots],
            'total_hours': round(sum(slots.mapped('duration')), 2),
        }

    @api.model
    def get_timetable_filters(self):
        classes = self.env['eacta.class'].search([], order='year desc, name')
        teachers = self.env['res.users'].search([('is_teacher', '=', True)], order='name')
        rooms = sorted({r for r in self.search([]).mapped('room') if r})
        return {
            'classes': [{'id': c.id, 'name': c.display_name} for c in classes],
            'teachers': [{'id': t.id, 'name': t.name} for t in teachers],
            'rooms': [{'id': r, 'name': r} for r in rooms],
        }

    @api.model
    def _generate_ics_string(self, slots, title="Emploi du temps", start_date=None, end_date=None):
        """
        Génère une chaîne iCalendar (.ics) conforme au standard RFC 5545
        avec répétition hebdomadaire pour les créneaux réguliers.
        """
        import datetime
        now = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        weekday_map = {'0': 'MO', '1': 'TU', '2': 'WE', '3': 'TH', '4': 'FR', '5': 'SA'}

        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//NR School//Emploi du Temps 1.0//FR",
            f"X-WR-CALNAME:{title}",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH",
        ]

        base_date = start_date or fields.Date.today()
        # Trouver le lundi de référence
        monday = base_date - datetime.timedelta(days=base_date.weekday())
        until_dt = (end_date or (base_date + datetime.timedelta(days=270)))
        until_str = until_dt.strftime("%Y%m%dT235959Z")

        for slot in slots:
            day_offset = int(slot.weekday)
            slot_date = monday + datetime.timedelta(days=day_offset)
            if slot_date < base_date:
                slot_date += datetime.timedelta(days=7)

            start_hours = int(slot.hour_from)
            start_mins = int(round((slot.hour_from - start_hours) * 60))
            end_hours = int(slot.hour_to)
            end_mins = int(round((slot.hour_to - end_hours) * 60))

            dtstart = f"{slot_date.strftime('%Y%m%d')}T{start_hours:02d}{start_mins:02d}00"
            dtend = f"{slot_date.strftime('%Y%m%d')}T{end_hours:02d}{end_mins:02d}00"
            byday = weekday_map.get(slot.weekday, 'MO')

            summary = f"{slot.course_id.name or 'Cours'} - {slot.class_id.name or ''}"
            desc = f"Matière: {slot.course_id.name or ''}\\nEnseignant: {slot.teacher_id.name or 'Non assigné'}\\nSalle: {slot.room or 'Non assignée'}"
            location = slot.room or ''
            uid = f"slot-{slot.id}-{slot_date.strftime('%Y%m%d')}@nrschool"

            lines.extend([
                "BEGIN:VEVENT",
                f"UID:{uid}",
                f"DTSTAMP:{now}",
                f"DTSTART:{dtstart}",
                f"DTEND:{dtend}",
                f"RRULE:FREQ=WEEKLY;BYDAY={byday};UNTIL={until_str}",
                f"SUMMARY:{summary}",
                f"DESCRIPTION:{desc}",
                f"LOCATION:{location}",
                "STATUS:CONFIRMED",
                "END:VEVENT",
            ])

        lines.append("END:VCALENDAR")
        return "\r\n".join(lines)

    @api.model
    def export_ics(self, mode, record_id):
        """Export du planning d'une classe ou d'un enseignant au format .ics."""
        if mode == 'class':
            klass = self.env['eacta.class'].browse(record_id)
            if not klass.exists():
                return None
            klass.check_access('read')
            slots = self.search([('class_id', '=', klass.id)])
            title = f"Emploi du temps - {klass.name}"
            start_date = klass.start_date or (klass.academic_year_id.date_start if klass.academic_year_id else fields.Date.today())
            end_date = klass.end_date or (klass.academic_year_id.date_end if klass.academic_year_id else fields.Date.today())
        elif mode == 'teacher':
            teacher = self.env['res.users'].browse(record_id)
            if not teacher.exists():
                return None
            teacher.check_access('read')
            slots = self.search([('teacher_id', '=', teacher.id)])
            title = f"Emploi du temps - {teacher.name}"
            start_date = fields.Date.today()
            import datetime
            end_date = fields.Date.today() + datetime.timedelta(days=270)
        else:
            return None
        return self._generate_ics_string(slots, title, start_date, end_date)

    @api.model
    def _generate_demo_admin(self):
        """Emploi du temps et frais de démonstration pour les classes de démo (déterministe)."""
        self = self.with_context(tracking_disable=True, mail_create_nolog=True, mail_notrack=True)
        classes = self.env['eacta.class'].search([], order='year desc, name', limit=4)
        all_courses = self.env['eacta.course'].search([])
        if not classes or not all_courses:
            return
        for klass in classes:
            if not klass.course_ids:
                klass.course_ids = all_courses
        periods = [(8.0, 10.0), (10.25, 12.25), (14.0, 16.0)]
        rooms = ['A101', 'A102', 'B201', 'B202']
        for n, klass in enumerate(classes):
            courses = klass.course_ids
            vals_list = []
            for day in range(5):
                for p, (start, end) in enumerate(periods):
                    if day == 2 and p == 2:  # mercredi après-midi libre
                        continue
                    course = courses[(day * 3 + p + n) % len(courses)]
                    vals_list.append({
                        'class_id': klass.id, 'course_id': course.id, 'weekday': str(day),
                        'hour_from': start, 'hour_to': end, 'room': rooms[n % len(rooms)],
                        'teacher_id': False,
                    })
            for vals in vals_list:
                try:
                    with self.env.cr.savepoint():
                        self.create(vals)
                except ValidationError:
                    # Enseignant déjà pris sur ce créneau : on laisse le créneau sans enseignant
                    with self.env.cr.savepoint():
                        slot = self.new(vals)
                        vals = dict(vals, teacher_id=False)
                        self.create(vals).teacher_id = False
        # Frais : scolarité en 3 échéances + inscription, avec quelques paiements
        Fee = self.env['eacta.student.fee']
        today = fields.Date.context_today(self)
        tuition = self.env.ref('eacta_school.fee_type_tuition', raise_if_not_found=False)
        registration = self.env.ref('eacta_school.fee_type_registration', raise_if_not_found=False)
        if not tuition or not registration:
            return
        wizard = self.env['eacta.fee.generate.wizard'].create({
            'fee_type_id': tuition.id, 'class_ids': [(6, 0, classes.ids)], 'amount': 9000.0,
            'installments': 3, 'first_due_date': today.replace(day=1) - relativedelta(months=1),
            'description': 'Scolarité',
        })
        wizard.action_generate()
        self.env['eacta.fee.generate.wizard'].create({
            'fee_type_id': registration.id, 'class_ids': [(6, 0, classes.ids)], 'amount': 1500.0,
            'first_due_date': today.replace(day=1) - relativedelta(months=1),
        }).action_generate()
        payments = []
        for i, fee in enumerate(Fee.search([('class_id', 'in', classes.ids)], order='id')):
            if fee.due_date <= today and i % 4 != 0:
                amount = fee.amount_due if i % 5 else round(fee.amount_due / 2, 2)
                payments.append({'fee_id': fee.id, 'amount': amount, 'date': min(fee.due_date, today),
                                 'method': ['cash', 'check', 'transfer'][i % 3]})
        self.env['eacta.fee.payment'].create(payments)
