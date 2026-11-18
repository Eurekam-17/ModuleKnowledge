# -*- coding: utf-8 -*-
"""Override du routage Knowledge natif pour les utilisateurs portail.

Les liens internes entre articles pointent vers ``/knowledge/article/<id>``. Pour un
utilisateur portail et un article de la base partagée (racine + descendants), la vue
Knowledge native n'est pas souhaitée (panneau de partage, membres — risque RGPD) : on le
redirige vers la vue portail ``/my/kb/article/<id>``.

Les autres articles gardent le comportement natif : les bases partagées nominativement
(McKesson, IT HEALTH…) restent consultées par leurs membres portail via Knowledge.
Les utilisateurs internes ne sont pas affectés.
"""
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

try:
    from odoo.addons.knowledge.controllers.main import KnowledgeController
except ImportError:  # pragma: no cover - dépend de la version d'Enterprise
    KnowledgeController = None
    _logger.warning("eurekam_knowledge_portal: KnowledgeController introuvable, "
                    "pas de redirection portail sur /knowledge/article/<id>.")


PORTAL_REDIRECT_ACTIVE = (
    KnowledgeController is not None and hasattr(KnowledgeController, 'redirect_to_article'))

if PORTAL_REDIRECT_ACTIVE:

    class EurekamKnowledgeController(KnowledgeController):

        @http.route()
        def redirect_to_article(self, *args, **kwargs):
            # Signature transmise telle quelle : la version de website_knowledge n'accepte que
            # des arguments nommés (article_id compris) ; un appel positionnel lève TypeError.
            article_id = kwargs.get('article_id', args[0] if args else None)
            if article_id and request.env.user._is_portal() and self._eurekam_kb_in_scope(article_id):
                return request.redirect(f'/my/kb/article/{int(article_id)}')
            return super().redirect_to_article(*args, **kwargs)

        def _eurekam_kb_in_scope(self, article_id):
            Article = request.env['knowledge.article']
            try:
                article_id = int(article_id)
            except (TypeError, ValueError):
                return False
            if not Article._eurekam_kb_root_id():
                return False
            return bool(Article.search_count(
                [('id', '=', article_id)] + Article._eurekam_kb_domain(), limit=1))
