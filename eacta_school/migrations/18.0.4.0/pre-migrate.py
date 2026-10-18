import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    _logger.info("Running pre-migration script for eacta_school to version %s", version)

    # 1. Rename column year_id to academic_year_id in eacta_term safely
    cr.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'eacta_term' AND column_name IN ('year_id', 'academic_year_id')
    """)
    cols = [r[0] for r in cr.fetchall()]
    if 'year_id' in cols and 'academic_year_id' not in cols:
        _logger.info("Renaming column year_id to academic_year_id in eacta_term")
        cr.execute("ALTER TABLE eacta_term RENAME COLUMN year_id TO academic_year_id")
    elif 'year_id' in cols and 'academic_year_id' in cols:
        _logger.info("Synchronizing data from year_id to academic_year_id in eacta_term")
        cr.execute("UPDATE eacta_term SET academic_year_id = year_id WHERE academic_year_id IS NULL AND year_id IS NOT NULL")
