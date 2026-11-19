# -*- coding: utf-8 -*-
"""18.0.1.0.7 : renouvellement des jetons d'accès des pièces jointes de la base partagée.

Les liens /web/content/<id>?access_token=… indexés par Google quand les articles étaient
publics restent valables après la dépublication : un nouveau jeton les invalide.
"""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['knowledge.article']._eurekam_kb_rotate_attachment_tokens()
