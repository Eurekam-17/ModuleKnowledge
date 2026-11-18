# -*- coding: utf-8 -*-
"""18.0.1.0.6 : en_root_article_id (une seule rubrique anglaise) → lang_root_articles.

Le nouveau paramètre vient d'être créé par data/kb_root.xml avec « en:463 ». On reporte
la valeur réellement réglée dans l'ancien paramètre (0 = tri désactivé), puis on supprime
l'ancien. Idempotent : sans ancien paramètre, rien à faire.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

LEGACY_KEY = 'eurekam_knowledge_portal.en_root_article_id'
NEW_KEY = 'eurekam_knowledge_portal.lang_root_articles'


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Param = env['ir.config_parameter']
    legacy = Param.search([('key', '=', LEGACY_KEY)], limit=1)
    if not legacy:
        return
    try:
        en_root_id = int(legacy.value or 0)
    except ValueError:
        en_root_id = 0
    # « aucun » plutôt que vide : set_param supprimerait le paramètre, et une mise à jour
    # ultérieure le recréerait avec la valeur par défaut « en:463 ».
    Param.set_param(NEW_KEY, f'en:{en_root_id}' if en_root_id > 0 else 'aucun')
    legacy.unlink()
    _logger.info("eurekam_knowledge_portal: %s=%s converti en %s=%s.",
                 LEGACY_KEY, en_root_id, NEW_KEY, Param.get_param(NEW_KEY))
