from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Avant 2.0 : participants dans une table many2many et date simple.

    On crée une inscription par participant et on initialise le début de l'événement à 9h.
    """
    cr.execute("""
        INSERT INTO eacta_school_event_registration
               (event_id, student_id, state, create_uid, write_uid, create_date, write_date)
        SELECT rel.event_id, rel.student_id, 'registered', 1, 1, now() at time zone 'UTC', now() at time zone 'UTC'
          FROM eacta_event_student_rel rel
     ON CONFLICT DO NOTHING
    """)
    cr.execute("""
        UPDATE eacta_school_event
           SET date_start = (date + time '09:00'), date_end = (date + time '13:00')
         WHERE date IS NOT NULL AND date_start IS NULL
    """)
    cr.execute("UPDATE eacta_school_event SET state = 'confirmed' WHERE state IS NULL OR state = 'draft'")
    env = api.Environment(cr, SUPERUSER_ID, {})
    regs = env['eacta.school.event.registration'].search([])
    env.add_to_compute(regs._fields['class_id'], regs)
    env.add_to_compute(regs._fields['parent_id'], regs)
    env.add_to_compute(regs._fields['event_date'], regs)
    events = env['eacta.school.event'].search([])
    for name in ('participant_count', 'attended_count', 'authorized_count', 'paid_count', 'seats_available',
                 'fill_rate', 'amount_collected', 'amount_expected'):
        env.add_to_compute(events._fields[name], events)
    env.flush_all()
