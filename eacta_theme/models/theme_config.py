# -*- coding: utf-8 -*-
import re

from markupsafe import Markup

from odoo import api, fields, models
from odoo.exceptions import ValidationError

HEX_RE = re.compile(r'^#[0-9A-Fa-f]{6}$')

# primary, secondary, accent, ink
PALETTES = {
    'nr_school': ('#8E1B3A', '#E0A630', '#F2784B', '#3B0A18'),
    'nr_marine': ('#00285C', '#00B8C8', '#F5A524', '#001A3D'),
    'indigo': ('#4F46E5', '#06B6D4', '#F59E0B', '#1E1B4B'),
    'emerald': ('#059669', '#10B981', '#F59E0B', '#064E3B'),
    'sky': ('#0284C7', '#38BDF8', '#F97316', '#0C4A6E'),
    'violet': ('#7C3AED', '#A855F7', '#EC4899', '#3B0764'),
    'slate': ('#334155', '#64748B', '#0284C7', '#0F172A'),
    'terracotta': ('#C2410C', '#0D9488', '#EAB308', '#431407'),
}

FONTS = {
    'system': (None, 'system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif'),
    'inter': ('Inter:wght@400;500;600;700;800', '"Inter", system-ui, sans-serif'),
    'poppins': ('Poppins:wght@400;500;600;700;800', '"Poppins", system-ui, sans-serif'),
    'nunito': ('Nunito:wght@400;500;600;700;800', '"Nunito", system-ui, sans-serif'),
    'cairo': ('Cairo:wght@400;500;600;700;800', '"Cairo", system-ui, sans-serif'),
}

RADII = {'small': 8, 'medium': 14, 'large': 20}

DEFAULTS = {
    'name': 'NR School',
    'primary_color': PALETTES['nr_school'][0],
    'secondary_color': PALETTES['nr_school'][1],
    'accent_color': PALETTES['nr_school'][2],
    'ink_color': PALETTES['nr_school'][3],
    'navbar_style': 'gradient',
    'card_style': 'modern',
    'card_radius': 'medium',
    'badge_style': 'soft',
    'density': 'comfortable',
    'font_family': 'system',
    'show_gpa_badges': True,
    'show_capacity_bar': True,
    'show_avatar_glow': True,
    'school_header_banner': True,
    'brand_login': True,
    'custom_css': '',
}


def _rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    return ', '.join(str(int(hex_color[i:i + 2], 16)) for i in (0, 2, 4))


class EactaThemeConfig(models.Model):
    _name = 'eacta.theme.config'
    _description = 'Style visuel NR School'
    _order = 'is_current desc, sequence, id'

    name = fields.Char(string="Nom du style", required=True, default="Mon style NR School")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(string="Actif", default=True)
    is_current = fields.Boolean(string="Style appliqué", readonly=True, copy=False)

    color_scheme = fields.Selection([
        ('nr_school', 'NR School (bordeaux & or)'),
        ('nr_marine', 'NR School Marine (bleu marine & turquoise)'),
        ('indigo', 'Indigo élégant'),
        ('emerald', 'Vert émeraude'),
        ('sky', 'Bleu océan'),
        ('violet', 'Violet royal'),
        ('slate', 'Anthracite'),
        ('terracotta', 'Terracotta'),
        ('custom', 'Personnalisé'),
    ], string="Palette", default='nr_school', required=True)
    primary_color = fields.Char(string="Couleur principale", default=DEFAULTS['primary_color'], required=True)
    secondary_color = fields.Char(string="Couleur secondaire", default=DEFAULTS['secondary_color'], required=True)
    accent_color = fields.Char(string="Couleur d'accent", default=DEFAULTS['accent_color'], required=True)
    ink_color = fields.Char(string="Couleur sombre", default=DEFAULTS['ink_color'], required=True,
                            help="Fond de la barre de navigation et des bandeaux")

    navbar_style = fields.Selection([
        ('gradient', 'Dégradé sombre'),
        ('solid', 'Couleur principale'),
        ('light', 'Claire'),
    ], string="Barre de navigation", default='gradient', required=True)
    card_style = fields.Selection([
        ('modern', 'Moderne (ombres douces)'),
        ('bordered', 'Encadrée'),
        ('flat', 'Plate'),
    ], string="Style des cartes", default='modern', required=True)
    card_radius = fields.Selection([
        ('small', 'Compact (8px)'),
        ('medium', 'Standard (14px)'),
        ('large', 'Très arrondi (20px)'),
    ], string="Arrondi", default='medium', required=True)
    badge_style = fields.Selection([
        ('soft', 'Fond doux'),
        ('pill', 'Pleins'),
        ('outline', 'Contour'),
    ], string="Style des badges", default='soft', required=True)
    density = fields.Selection([
        ('comfortable', 'Confortable'),
        ('compact', 'Compacte'),
    ], string="Densité", default='comfortable', required=True)
    font_family = fields.Selection([
        ('system', 'Police du système'),
        ('inter', 'Inter'),
        ('poppins', 'Poppins'),
        ('nunito', 'Nunito'),
        ('cairo', 'Cairo (latin & arabe)'),
    ], string="Police", default='system', required=True)

    show_gpa_badges = fields.Boolean(string="Badges de moyenne sur les cartes", default=True)
    show_capacity_bar = fields.Boolean(string="Jauges de remplissage des classes", default=True)
    show_avatar_glow = fields.Boolean(string="Halo autour des photos", default=True)
    school_header_banner = fields.Boolean(string="Bandeau coloré du tableau de bord", default=True)
    brand_login = fields.Boolean(string="Page de connexion aux couleurs", default=True)
    custom_css = fields.Text(string="CSS personnalisé")

    preview_html = fields.Html(string="Aperçu", compute='_compute_preview_html', sanitize=False)

    # ------------------------------------------------------------------
    @api.constrains('primary_color', 'secondary_color', 'accent_color', 'ink_color')
    def _check_colors(self):
        for rec in self:
            for field in ('primary_color', 'secondary_color', 'accent_color', 'ink_color'):
                if not HEX_RE.match(rec[field] or ''):
                    raise ValidationError(
                        f"« {rec._fields[field].string} » doit être une couleur hexadécimale (ex : #8E1B3A).")

    @api.onchange('color_scheme')
    def _onchange_color_scheme(self):
        if self.color_scheme in PALETTES:
            self.primary_color, self.secondary_color, self.accent_color, self.ink_color = PALETTES[self.color_scheme]

    @api.onchange('primary_color', 'secondary_color', 'accent_color', 'ink_color')
    def _onchange_colors(self):
        palette = PALETTES.get(self.color_scheme)
        current = tuple((c or '').upper() for c in (self.primary_color, self.secondary_color,
                                                    self.accent_color, self.ink_color))
        if palette and current != palette:
            self.color_scheme = 'custom'

    @api.depends('primary_color', 'secondary_color', 'accent_color', 'ink_color', 'navbar_style',
                 'card_radius', 'card_style', 'badge_style')
    def _compute_preview_html(self):
        for rec in self:
            v = rec._get_values()
            if not all(HEX_RE.match(v[f] or '') for f in ('primary_color', 'secondary_color', 'accent_color', 'ink_color')):
                rec.preview_html = False
                continue
            p, s, a, ink = v['primary_color'], v['secondary_color'], v['accent_color'], v['ink_color']
            radius = RADII.get(v['card_radius'], 14)
            nav_bg, nav_fg = rec._navbar_colors(v)
            shadow = {'modern': '0 6px 18px rgba(15,23,42,.10)', 'bordered': 'none', 'flat': 'none'}[v['card_style']]
            border = {'modern': '1px solid #e2e8f0', 'bordered': f'1.5px solid {p}33', 'flat': '1px solid transparent'}[v['card_style']]
            badge = {
                'soft': f'background:{p}1f;color:{p};border:1px solid {p}40',
                'pill': f'background:{p};color:#fff;border:1px solid {p}',
                'outline': f'background:transparent;color:{p};border:1px solid {p}',
            }[v['badge_style']]
            rec.preview_html = Markup(f"""
<div style="font-family:system-ui,sans-serif;border:1px solid #e2e8f0;border-radius:12px;overflow:hidden;background:#f4f6fb;max-width:640px">
  <div style="background:{nav_bg};color:{nav_fg};padding:10px 16px;display:flex;gap:18px;align-items:center;font-size:13px;border-bottom:3px solid {s}">
    <strong style="font-size:14px">NR School</strong><span style="opacity:.85">Scolarité</span><span style="opacity:.85">Pédagogie</span><span style="opacity:.85">Analyse</span>
  </div>
  <div style="padding:16px;display:flex;gap:14px;flex-wrap:wrap">
    <div style="flex:1 1 220px;background:#fff;border-radius:{radius}px;box-shadow:{shadow};border:{border};border-top:3px solid {s};padding:14px">
      <div style="display:flex;align-items:center;gap:10px">
        <div style="width:40px;height:40px;border-radius:50%;background:{p}1f;color:{p};display:flex;align-items:center;justify-content:center;font-weight:700">A</div>
        <div style="flex:1"><div style="font-weight:700;color:#0f172a">Amina Benali</div><div style="font-size:12px;color:#64748b">STU00042 · 6ème A</div></div>
        <span style="font-size:11px;font-weight:600;padding:2px 9px;border-radius:999px;{badge}">Inscrit</span>
      </div>
      <div style="margin-top:12px;height:7px;border-radius:9px;background:#eef2f7;overflow:hidden"><div style="width:72%;height:100%;background:linear-gradient(90deg,{p},{s})"></div></div>
      <div style="margin-top:10px;display:flex;justify-content:space-between;font-size:12px;color:#64748b"><span>6 cours</span><span style="font-weight:700;color:#047857;background:#d1fae5;padding:1px 8px;border-radius:7px">15.25 / 20</span></div>
    </div>
    <div style="flex:1 1 200px;display:flex;flex-direction:column;gap:10px">
      <div style="background:linear-gradient(120deg,{ink},{p});color:#fff;border-radius:{radius}px;padding:14px">
        <div style="font-size:12px;opacity:.8">Moyenne générale</div><div style="font-size:24px;font-weight:800">13.48<small style="font-size:13px;opacity:.8">/20</small></div>
      </div>
      <div style="display:flex;gap:8px">
        <span style="background:{p};color:#fff;padding:6px 14px;border-radius:6px;font-size:13px;font-weight:600">Valider</span>
        <span style="background:#fff;color:#334155;border:1px solid #cbd5e1;padding:6px 14px;border-radius:6px;font-size:13px">Annuler</span>
        <span style="background:{a};width:30px;border-radius:6px"></span>
      </div>
    </div>
  </div>
</div>""")

    # ------------------------------------------------------------------
    def _get_values(self):
        """Valeurs du style (avec valeurs par défaut si aucun style n'est défini)."""
        if not self:
            return dict(DEFAULTS)
        self.ensure_one()
        return {key: self[key] for key in DEFAULTS}

    @api.model
    def _ensure_current_theme(self):
        if not self.search_count([('is_current', '=', True)]):
            preset = self.env.ref('eacta_theme.theme_preset_nr_school', raise_if_not_found=False) or self.search([], limit=1)
            preset.write({'is_current': True})

    @api.model
    def _get_current(self):
        current = self.sudo().search([('is_current', '=', True)], limit=1)
        if not current:
            self._ensure_current_theme()
            current = self.sudo().search([('is_current', '=', True)], limit=1)
        return current

    @staticmethod
    def _navbar_colors(v):
        p, s, ink = v['primary_color'], v['secondary_color'], v['ink_color']
        if v['navbar_style'] == 'light':
            return '#ffffff', ink
        if v['navbar_style'] == 'solid':
            return p, '#ffffff'
        return f'linear-gradient(120deg, {ink} 0%, {p} 100%)', '#ffffff'

    @api.model
    def _get_font_url(self):
        values = self._get_current()._get_values()
        family = FONTS.get(values['font_family'], FONTS['system'])[0]
        return f'https://fonts.googleapis.com/css2?family={family}&display=swap' if family else False

    @api.model
    def _get_theme_css(self, scope='backend'):
        """CSS dynamique injecté dans <head> (variables + options d'affichage)."""
        v = self._get_current()._get_values()
        p, s, a, ink = v['primary_color'], v['secondary_color'], v['accent_color'], v['ink_color']
        nav_bg, nav_fg = self._navbar_colors(v)
        radius = RADII.get(v['card_radius'], 14)
        light_nav = v['navbar_style'] == 'light'
        font = FONTS.get(v['font_family'], FONTS['system'])[1]
        card = {
            'modern': ('1px solid #e7ebf2', '0 1px 2px rgba(15,23,42,.04), 0 4px 14px rgba(15,23,42,.05)',
                       '0 12px 28px rgba(15,23,42,.12)'),
            'bordered': (f'1.5px solid color-mix(in srgb, {p} 22%, #e2e8f0)', 'none',
                         f'0 0 0 3px color-mix(in srgb, {p} 12%, transparent)'),
            'flat': ('1px solid transparent', 'none', '0 2px 8px rgba(15,23,42,.06)'),
        }[v['card_style']]

        css = [f""":root {{
  --eacta-primary: {p}; --eacta-primary-rgb: {_rgb(p)};
  --eacta-secondary: {s}; --eacta-secondary-rgb: {_rgb(s)};
  --eacta-accent: {a}; --eacta-accent-rgb: {_rgb(a)};
  --eacta-primary-ink: {ink};
  --eacta-primary-hover: color-mix(in srgb, {p} 82%, black);
  --eacta-primary-subtle: color-mix(in srgb, {p} 10%, white);
  --eacta-navbar-bg: {nav_bg}; --eacta-navbar-fg: {nav_fg};
  --eacta-navbar-hover: {'color-mix(in srgb, ' + p + ' 9%, white)' if light_nav else 'rgba(255,255,255,.14)'};
  --eacta-navbar-border: {s};
  --eacta-card-radius: {radius}px; --eacta-card-border: {card[0]};
  --eacta-card-shadow: {card[1]}; --eacta-card-shadow-hover: {card[2]};
  --eacta-font: {font};
  --o-brand-odoo: {p};
  --o-brand-odoo-rgb: {_rgb(p)};
  --o-brand-primary: {p};
  --o-brand-primary-rgb: {_rgb(p)};
  --o-brand-secondary: {s};
  --o-brand-secondary-rgb: {_rgb(s)};
  --primary: {p};
  --primary-rgb: {_rgb(p)};
  --bs-primary: {p}; --bs-primary-rgb: {_rgb(p)};
  --bs-link-color: {p}; --bs-link-color-rgb: {_rgb(p)};
  --bs-link-hover-color: color-mix(in srgb, {p} 75%, black);
  --bs-primary-bg-subtle: color-mix(in srgb, {p} 12%, white);
  --bs-primary-border-subtle: color-mix(in srgb, {p} 30%, white);
  --bs-primary-text-emphasis: color-mix(in srgb, {p} 75%, black);
  --bs-focus-ring-color: color-mix(in srgb, {p} 25%, transparent);
  --btn-primary-bg: {p};
  --btn-primary-border-color: {p};
  --btn-primary-hover-bg: color-mix(in srgb, {p} 82%, black);
  --btn-primary-hover-border-color: color-mix(in srgb, {p} 82%, black);
  --btn-primary-active-bg: color-mix(in srgb, {p} 72%, black);
  --btn-primary-active-border-color: color-mix(in srgb, {p} 72%, black);
}}
.btn-primary, button.btn-primary, .o_form_button_save, .o_cp_action_menus .btn-primary {{
  background-color: {p} !important;
  border-color: {p} !important;
  color: #ffffff !important;
}}
.btn-primary:hover, button.btn-primary:hover, .o_form_button_save:hover {{
  background-color: color-mix(in srgb, {p} 82%, black) !important;
  border-color: color-mix(in srgb, {p} 82%, black) !important;
  color: #ffffff !important;
}}
.btn-primary:active, button.btn-primary:active, .btn-primary.active {{
  background-color: color-mix(in srgb, {p} 72%, black) !important;
  border-color: color-mix(in srgb, {p} 72%, black) !important;
  color: #ffffff !important;
}}
.btn-outline-primary {{
  color: {p} !important;
  border-color: {p} !important;
}}
.btn-outline-primary:hover {{
  background-color: {p} !important;
  border-color: {p} !important;
  color: #ffffff !important;
}}
"""]
        if v['badge_style'] == 'pill':
            css.append(""".o_eacta_badge { color: #fff !important; background: var(--eacta-primary) !important; border-color: transparent !important; }
.o_eacta_badge.o_eacta_badge_draft { background: #d97706 !important; }
.o_eacta_badge.o_eacta_badge_enrolled { background: #059669 !important; }
.o_eacta_badge.o_eacta_badge_alumni { background: #64748b !important; }""")
        elif v['badge_style'] == 'outline':
            css.append(".o_eacta_badge { background: transparent !important; }")
        if not v['show_gpa_badges']:
            css.append(".o_eacta_kanban .o_eacta_score { display: none !important; }")
        if not v['show_capacity_bar']:
            css.append(".o_eacta_kanban .o_eacta_meter { display: none !important; }")
        if not v['show_avatar_glow']:
            css.append(":root { --eacta-avatar-ring: none; }")
        if not v['school_header_banner']:
            css.append(""".o_eacta_dashboard .o_eacta_dash_hero { background: #fff !important; color: inherit !important; box-shadow: none !important; border: var(--eacta-card-border); }
.o_eacta_dashboard .o_eacta_dash_hero h1 { color: var(--eacta-primary-ink) !important; }""")
        if v['density'] == 'compact':
            css.append(""".o_list_renderer .o_list_table tbody td, .o_list_renderer .o_list_table thead th { padding-top: .35rem !important; padding-bottom: .35rem !important; }
.o_form_view .o_form_sheet { padding: 1.25rem 1.5rem !important; }
.o_eacta_card { padding: .65rem .8rem !important; gap: .45rem !important; }""")
        if v['custom_css']:
            # Empêche toute sortie prématurée de la balise <style>
            css.append(v['custom_css'].replace('</', '<\\/'))
        return Markup('\n'.join(css))

    # ------------------------------------------------------------------
    def action_set_current(self):
        self.ensure_one()
        self.search([('is_current', '=', True), ('id', '!=', self.id)]).write({'is_current': False})
        self.write({'is_current': True, 'active': True})
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def action_reset_defaults(self):
        values = dict(DEFAULTS)
        values.pop('name')
        values['color_scheme'] = 'nr_school'
        self.write(values)
        return {'type': 'ir.actions.client', 'tag': 'reload'} if self.filtered('is_current') else True

    def write(self, vals):
        res = super().write(vals)
        if 'active' in vals and not vals['active'] and self.filtered('is_current'):
            raise ValidationError("Impossible d'archiver le style actuellement appliqué.")
        return res
