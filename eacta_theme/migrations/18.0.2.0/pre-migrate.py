def migrate(cr, version):
    """Avant 2.0, « active » servait à marquer le style appliqué (les autres étaient archivés).

    On reporte cette information dans le nouveau champ ``is_current`` et on désarchive les styles.
    """
    cr.execute("ALTER TABLE eacta_theme_config ADD COLUMN IF NOT EXISTS is_current boolean")
    cr.execute("UPDATE eacta_theme_config SET is_current = COALESCE(active, false)")
    cr.execute("""
        UPDATE eacta_theme_config SET is_current = false
         WHERE is_current AND id <> (SELECT max(id) FROM eacta_theme_config WHERE is_current)
    """)
    cr.execute("UPDATE eacta_theme_config SET active = true")
