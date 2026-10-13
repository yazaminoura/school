# -*- coding: utf-8 -*-
from odoo import models, fields, api


class EactaThemeConfig(models.Model):
    _name = 'eacta.theme.config'
    _description = 'Configuration du Thème E-ACTA'
    _order = 'active desc, id desc'

    name = fields.Char(
        string="Nom du style",
        required=True,
        default="E-ACTA Premium Modern"
    )
    active = fields.Boolean(
        string="Actif",
        default=True
    )

    color_scheme = fields.Selection([
        ('indigo', 'Bleu Indigo Élégant (#4F46E5)'),
        ('emerald', 'Vert Émeraude Académique (#059669)'),
        ('sky', 'Bleu Océan Moderne (#0284C7)'),
        ('violet', 'Violet Royal (#7C3AED)'),
        ('slate', 'Gris Anthracite Chic (#334155)'),
        ('custom', 'Personnalisé'),
    ], string="Palette de Couleurs", default='indigo', required=True)

    primary_color = fields.Char(
        string="Couleur Principale",
        default="#4F46E5"
    )
    secondary_color = fields.Char(
        string="Couleur Secondaire",
        default="#06B6D4"
    )
    accent_color = fields.Char(
        string="Couleur d'Accent",
        default="#F59E0B"
    )
    ink_color = fields.Char(
        string="Couleur Sombre (Navbar/En-tête)",
        default="#1E1B4B",
        help="Couleur de base pour le fond de la barre de navigation et les éléments sombres"
    )

    card_style = fields.Selection([
        ('modern', 'Cartes Modernes (Arrondis & Ombres fluides)'),
        ('bordered', 'Encadrement Délicat'),
        ('flat', 'Minimaliste Flat'),
    ], string="Style des Cartes", default='modern')

    card_radius = fields.Selection([
        ('small', 'Compact (8px)'),
        ('medium', 'Moderne Standard (14px)'),
        ('large', 'Très Arrondi (20px)'),
    ], string="Rayon des Bordures", default='medium')

    badge_style = fields.Selection([
        ('pill', 'Pillules Pleines'),
        ('soft', 'Fond Doux & Texte Coloré'),
        ('outline', 'Contour Fin'),
    ], string="Style des Badges", default='soft')

    show_gpa_badges = fields.Boolean(
        string="Afficher le badge GPA / Moyenne",
        default=True,
        help="Affiche un badge de performance stylisé sur les cartes des élèves"
    )
    show_capacity_bar = fields.Boolean(
        string="Afficher la jauge de capacité des classes",
        default=True,
        help="Affiche une barre de progression visuelle pour les places restantes par classe"
    )
    show_avatar_glow = fields.Boolean(
        string="Effet soigné sur les photos des élèves",
        default=True
    )
    school_header_banner = fields.Boolean(
        string="Bannière d'en-tête moderne sur les fiches",
        default=True
    )

    custom_css = fields.Text(
        string="CSS Personnalisé additionnel",
        help="Règles CSS supplémentaires appliquées à l'interface"
    )

    @api.onchange('color_scheme')
    def _onchange_color_scheme(self):
        palettes = {
            'indigo': ('#4F46E5', '#06B6D4', '#F59E0B', '#1E1B4B'),
            'emerald': ('#059669', '#10B981', '#F59E0B', '#064E3B'),
            'sky': ('#0284C7', '#38BDF8', '#F97316', '#0C4A6E'),
            'violet': ('#7C3AED', '#A855F7', '#EC4899', '#3B0764'),
            'slate': ('#334155', '#64748B', '#0284C7', '#0F172A'),
        }
        if self.color_scheme in palettes:
            self.primary_color, self.secondary_color, self.accent_color, self.ink_color = palettes[self.color_scheme]

    def _sync_to_config_parameters(self):
        for rec in self:
            ICP = self.env['ir.config_parameter'].sudo()
            ICP.set_param('eacta_theme.primary_color', rec.primary_color or '#4F46E5')
            ICP.set_param('eacta_theme.secondary_color', rec.secondary_color or '#06B6D4')
            ICP.set_param('eacta_theme.accent_color', rec.accent_color or '#F59E0B')
            ICP.set_param('eacta_theme.ink_color', rec.ink_color or '#1E1B4B')
            ICP.set_param('eacta_theme.active_theme_name', rec.name or 'E-ACTA Theme')
            if rec.custom_css:
                ICP.set_param('eacta_theme.custom_css', rec.custom_css)
            else:
                ICP.set_param('eacta_theme.custom_css', '')

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            if rec.active:
                rec._sync_to_config_parameters()
        return records

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            if rec.active:
                rec._sync_to_config_parameters()
        return res

    def action_set_active(self):
        self.ensure_one()
        self.search([('id', '!=', self.id)]).write({'active': False})
        self.write({'active': True})
        self._sync_to_config_parameters()

    def action_reset_defaults(self):
        for rec in self:
            rec.color_scheme = 'indigo'
            rec.primary_color = '#4F46E5'
            rec.secondary_color = '#06B6D4'
            rec.accent_color = '#F59E0B'
            rec.ink_color = '#1E1B4B'
            rec.card_style = 'modern'
            rec.card_radius = 'medium'
            rec.badge_style = 'soft'
            rec.show_gpa_badges = True
            rec.show_capacity_bar = True
            rec.show_avatar_glow = True
            rec.school_header_banner = True
            if rec.active:
                rec._sync_to_config_parameters()

