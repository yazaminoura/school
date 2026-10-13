from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Applique les couleurs officielles de marque NR School (Bleu marine & Turquoise) issues du logo."""
    cr.execute("""
        UPDATE eacta_theme_config
        SET primary_color = '#00285C',
            secondary_color = '#00B8C8',
            accent_color = '#F5A524',
            ink_color = '#001A3D',
            name = 'NR School (Bleu marine & Turquoise)',
            color_scheme = 'nr_school',
            is_current = True,
            active = True
        WHERE id = 5 OR color_scheme IN ('nr_school', 'nr_marine') OR is_current = True
    """)
    # Assure qu'un seul enregistrement est actif comme style appliqué
    cr.execute("""
        UPDATE eacta_theme_config
        SET is_current = (id = (
            SELECT id FROM eacta_theme_config 
            WHERE color_scheme = 'nr_school' OR id = 5 
            ORDER BY id ASC LIMIT 1
        ))
    """)
