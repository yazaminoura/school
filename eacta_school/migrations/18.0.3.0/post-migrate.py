import logging
from datetime import date
from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    _logger.info("Running post-migration script for eacta_school to version %s", version)
    env = api.Environment(cr, SUPERUSER_ID, {})
    AcademicYear = env['eacta.academic.year']
    Term = env['eacta.term']

    # 1. Collect all distinct year strings from existing tables
    distinct_years = set()
    cr.execute("SELECT DISTINCT year FROM eacta_class WHERE year IS NOT NULL AND year != ''")
    distinct_years.update(r[0] for r in cr.fetchall())

    cr.execute("SELECT DISTINCT year FROM eacta_student_fee WHERE year IS NOT NULL AND year != ''")
    distinct_years.update(r[0] for r in cr.fetchall())

    cr.execute("SELECT DISTINCT year FROM eacta_course_grade WHERE year IS NOT NULL AND year != ''")
    distinct_years.update(r[0] for r in cr.fetchall())

    # Map raw string (e.g. "2026") to academic year record
    year_map = {}
    today = date.today()

    for raw_year in distinct_years:
        raw_clean = str(raw_year).strip()
        if '-' in raw_clean and len(raw_clean) >= 9:
            ay_name = raw_clean
            try:
                start_yr = int(raw_clean.split('-')[0])
            except ValueError:
                start_yr = today.year
        elif raw_clean.isdigit():
            start_yr = int(raw_clean)
            ay_name = f"{start_yr}-{start_yr + 1}"
        else:
            ay_name = raw_clean
            start_yr = today.year

        d_start = date(start_yr, 9, 1)
        d_end = date(start_yr + 1, 6, 30)

        ay = AcademicYear.search([('name', '=', ay_name)], limit=1)
        if not ay:
            ay = AcademicYear.create({
                'name': ay_name,
                'date_start': d_start,
                'date_end': d_end,
                'state': 'draft',
            })
            # Create standard Moroccan terms (3 trimestres)
            Term.create([
                {
                    'name': '1er Trimestre',
                    'year_id': ay.id,
                    'sequence': 1,
                    'date_start': date(start_yr, 9, 1),
                    'date_end': date(start_yr, 11, 30),
                    'weight': 1.0,
                },
                {
                    'name': '2ème Trimestre',
                    'year_id': ay.id,
                    'sequence': 2,
                    'date_start': date(start_yr, 12, 1),
                    'date_end': date(start_yr + 1, 2, 28),
                    'weight': 1.0,
                },
                {
                    'name': '3ème Trimestre',
                    'year_id': ay.id,
                    'sequence': 3,
                    'date_start': date(start_yr + 1, 3, 1),
                    'date_end': date(start_yr + 1, 6, 30),
                    'weight': 1.0,
                },
            ])
        year_map[raw_year] = ay

    # Open the current year if none is open
    open_year = AcademicYear.search([('state', '=', 'open')], limit=1)
    if not open_year and year_map:
        current_candidates = [ay for ay in year_map.values() if ay.date_start <= today <= ay.date_end]
        if current_candidates:
            current_candidates[0].state = 'open'
        else:
            list(year_map.values())[0].state = 'open'

    # 2. Update eacta_class.academic_year_id
    for raw_year, ay in year_map.items():
        cr.execute(
            "UPDATE eacta_class SET academic_year_id = %s WHERE (academic_year_id IS NULL OR academic_year_id = 0) AND year = %s",
            (ay.id, str(raw_year))
        )

    # 3. Update eacta_student_fee.academic_year_id
    for raw_year, ay in year_map.items():
        cr.execute(
            "UPDATE eacta_student_fee SET academic_year_id = %s WHERE (academic_year_id IS NULL OR academic_year_id = 0) AND year = %s",
            (ay.id, str(raw_year))
        )

    # 4. Update eacta_course_grade.academic_year_id
    for raw_year, ay in year_map.items():
        cr.execute(
            "UPDATE eacta_course_grade SET academic_year_id = %s WHERE (academic_year_id IS NULL OR academic_year_id = 0) AND year = %s",
            (ay.id, str(raw_year))
        )

    # Fallback: if grade has class_id with academic_year_id, copy it
    cr.execute("""
        UPDATE eacta_course_grade g
        SET academic_year_id = c.academic_year_id
        FROM eacta_class c
        WHERE g.class_id = c.id AND (g.academic_year_id IS NULL OR g.academic_year_id = 0)
    """)

    # 5. Update eacta_timetable_slot.academic_year_id from class_id
    cr.execute("""
        UPDATE eacta_timetable_slot s
        SET academic_year_id = c.academic_year_id
        FROM eacta_class c
        WHERE s.class_id = c.id AND (s.academic_year_id IS NULL OR s.academic_year_id = 0)
    """)

    # 6. Update eacta_exam academic_year_id and term_id
    cr.execute("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_name = 'eacta_exam_class_rel'
        )
    """)
    if cr.fetchone()[0]:
        cr.execute("""
            UPDATE eacta_exam e
            SET academic_year_id = c.academic_year_id
            FROM eacta_exam_class_rel rel
            JOIN eacta_class c ON rel.class_ids = c.id
            WHERE rel.exam_id = e.id AND (e.academic_year_id IS NULL OR e.academic_year_id = 0)
        """)

    exams_without_term = env['eacta.exam'].search([('term_id', '=', False), ('date', '!=', False)])
    for exam in exams_without_term:
        term = Term.search([
            ('date_start', '<=', exam.date),
            ('date_end', '>=', exam.date),
        ], limit=1)
        if term:
            exam.term_id = term.id
            if not exam.academic_year_id:
                exam.academic_year_id = term.year_id.id

    _logger.info("Post-migration eacta_school completed successfully.")
