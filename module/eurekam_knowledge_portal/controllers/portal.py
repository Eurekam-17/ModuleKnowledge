# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal

NAV_ORDER = 'sequence, name, id'


class KnowledgePortal(CustomerPortal):

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _kb_article_model(self):
        # Pas de sudo : les droits de l'utilisateur connecté (ir.rule) s'appliquent.
        return request.env['knowledge.article']

    def _kb_nav_domain(self, extra=None):
        """Domaine de navigation : périmètre partagé, hors « éléments d'article »."""
        Article = self._kb_article_model()
        return Article._eurekam_kb_domain() + [('is_article_item', '=', False)] + (extra or [])

    def _kb_ancestors(self, article, root):
        """Ancêtres de ``article`` strictement sous la racine, du plus haut au plus proche.

        S'arrête à la racine : on ne lit jamais un parent hors périmètre.
        """
        ancestors = request.env['knowledge.article']
        current = article.parent_id
        while current and current != root:
            ancestors = current + ancestors
            current = current.parent_id
        return ancestors

    # ------------------------------------------------------------------
    # Centre portail (/my)
    # ------------------------------------------------------------------

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'knowledge_count' in counters:
            Article = self._kb_article_model()
            values['knowledge_count'] = (
                Article.search_count(self._kb_nav_domain())
                if Article._eurekam_kb_root_id() else 0
            )
        return values

    # ------------------------------------------------------------------
    # Routes
    # ------------------------------------------------------------------

    @http.route(['/my/kb'], type='http', auth='user', website=True)
    def portal_my_kb(self, **kw):
        Article = self._kb_article_model()
        root_id = Article._eurekam_kb_root_id()
        root = Article.search([('id', '=', root_id)], limit=1) if root_id else Article
        if not root:
            # Paramètre absent/invalide ou racine inaccessible : aucun article exposé.
            return request.render('eurekam_knowledge_portal.portal_no_kb', {'page_name': 'kb'})
        children = Article.search(self._kb_nav_domain([('parent_id', '=', root.id)]), order=NAV_ORDER)
        return request.render('eurekam_knowledge_portal.portal_kb_index', {
            'root': root,
            'children': children,
            'page_name': 'kb',
        })

    @http.route(['/my/kb/article/<int:article_id>'], type='http', auth='user', website=True)
    def portal_my_kb_article(self, article_id, **kw):
        Article = self._kb_article_model()
        root_id = Article._eurekam_kb_root_id()
        if not root_id:
            return request.render('eurekam_knowledge_portal.portal_no_kb', {'page_name': 'kb'})
        # Contrôle explicite du périmètre (en plus de l'ir.rule) : un article accessible par
        # un autre biais (ex. membre natif Knowledge) mais hors arborescence → 404.
        article = Article.search([('id', '=', article_id)] + Article._eurekam_kb_domain(), limit=1)
        if not article:
            raise request.not_found()
        if article.id == root_id:
            return request.redirect('/my/kb')
        root = Article.browse(root_id)
        siblings = Article.search(
            self._kb_nav_domain([('parent_id', '=', article.parent_id.id)]), order=NAV_ORDER)
        children = Article.search(
            self._kb_nav_domain([('parent_id', '=', article.id)]), order=NAV_ORDER)
        return request.render('eurekam_knowledge_portal.portal_kb_article', {
            'root': root,
            'article': article,
            'ancestors': self._kb_ancestors(article, root),
            'siblings': siblings,
            'children': children,
            'page_name': 'kb_article',
        })
