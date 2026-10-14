from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Style NR School en bordeaux & or (ni bleu ni vert) ; le bleu marine reste disponible via « NR School Marine »."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    Theme = env['eacta.theme.config'].with_context(active_test=False)
    preset = env.ref('eacta_theme.theme_preset_nr_school', raise_if_not_found=False)
    marine = env.ref('eacta_theme.theme_preset_nr_marine', raise_if_not_found=False)
    if marine:
        marine.write({
            'name': 'NR School Marine', 'color_scheme': 'nr_marine',
            'primary_color': '#00285C', 'secondary_color': '#00B8C8',
            'accent_color': '#F5A524', 'ink_color': '#001A3D', 'is_current': False,
        })
    if preset:
        Theme.search([('id', '!=', preset.id)]).write({'is_current': False})
        preset.write({
            'name': 'NR School', 'color_scheme': 'nr_school', 'active': True, 'is_current': True,
            'primary_color': '#8E1B3A', 'secondary_color': '#E0A630',
            'accent_color': '#F2784B', 'ink_color': '#3B0A18',
        })
