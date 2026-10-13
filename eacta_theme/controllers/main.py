# -*- coding: utf-8 -*-
import os
from odoo import http
from odoo.http import request, Response
from odoo.modules.module import get_module_resource


class NRThemeFaviconController(http.Controller):

    @http.route(['/favicon.ico'], type='http', auth='none', cors='*')
    def favicon(self, **kw):
        icon_path = get_module_resource('eacta_school', 'static', 'src', 'img', 'favicon.ico')
        if not (icon_path and os.path.exists(icon_path)):
            icon_path = get_module_resource('eacta_theme', 'static', 'src', 'img', 'favicon.ico')
        if icon_path and os.path.exists(icon_path):
            with open(icon_path, 'rb') as f:
                content = f.read()
            return Response(content, headers=[
                ('Content-Type', 'image/x-icon'),
                ('Cache-Control', 'public, max-age=86400'),
            ])
        return request.not_found()
