# -*- coding: utf-8 -*-
import re

from odoo import models
from odoo.http import request

# Adresses qui ne doivent jamais être indexées (cf. spec §6.4) : articles Knowledge, base
# portail, et fichiers / images servis par jeton (les pièces jointes des articles avaient été
# indexées par Google quand ceux-ci étaient publics). Préfixe de langue du site accepté
# (/fr_FR/knowledge/…).
NOINDEX_PATH_RE = re.compile(
    r'^/(?:[a-z]{2}(?:_[A-Za-z]{2,4})?/)?(?:knowledge|my/kb|web/content|web/image)(?:/|$)')


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    @classmethod
    def _post_dispatch(cls, response):
        super()._post_dispatch(response)
        path = request.httprequest.path if request else ''
        if NOINDEX_PATH_RE.match(path):
            response.headers['X-Robots-Tag'] = 'noindex, nofollow'
