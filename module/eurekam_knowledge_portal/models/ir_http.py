# -*- coding: utf-8 -*-
from odoo import models
from odoo.http import request

# Préfixes d'URL qui ne doivent jamais être indexés (cf. spec §6.4).
NOINDEX_PREFIXES = ('/knowledge', '/my/kb')


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    @classmethod
    def _post_dispatch(cls, response):
        super()._post_dispatch(response)
        path = request.httprequest.path if request else ''
        if path.startswith(NOINDEX_PREFIXES):
            response.headers['X-Robots-Tag'] = 'noindex, nofollow'
