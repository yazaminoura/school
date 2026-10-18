import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    _logger.info("Running post-migration script for eacta_school to version %s", version)

    # 1. Ensure MAD currency is active
    cr.execute("UPDATE res_currency SET active = true WHERE name = 'MAD'")

    # 2. Synchronize term academic_year_id if column exists
    cr.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'eacta_term' AND column_name IN ('year_id', 'academic_year_id')
    """)
    cols = [r[0] for r in cr.fetchall()]
    if 'year_id' in cols and 'academic_year_id' in cols:
        cr.execute("UPDATE eacta_term SET academic_year_id = year_id WHERE academic_year_id IS NULL AND year_id IS NOT NULL")
