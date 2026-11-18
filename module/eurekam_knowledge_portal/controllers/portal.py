# -*- coding: utf-8 -*-
import json
import logging
from urllib.parse import quote

from lxml import etree, html as lxml_html
from markupsafe import Markup

from odoo import http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal

_logger = logging.getLogger(__name__)

NAV_ORDER = 'sequence, name, id'


def _drop_node(node):
    """Retire ``node`` de l'arbre en conservant le texte qui le suit (tail)."""
    parent = node.getparent()
    if parent is None:
        return
    if node.tail:
        previous = node.getprevious()
        if previous is not None:
            previous.tail = (previous.tail or '') + node.tail
        else:
            parent.text = (parent.text or '') + node.tail
    parent.remove(node)


def _file_link(props):
    """Lien de téléchargement pour un bloc Knowledge ``data-embedded="file"``.

    Le bloc n'est rendu que par le JavaScript de l'éditeur Knowledge ; côté portail il
    resterait vide. Les propriétés portent l'id et le jeton d'accès de la pièce jointe :
    ``/web/content`` vérifie lui-même ce jeton, aucun droit supplémentaire n'est accordé.
    """
    try:
        data = json.loads(props or '{}').get('fileData') or {}
        attachment_id = int(data['id'])
    except (ValueError, TypeError, KeyError, AttributeError):
        return None
    name = str(data.get('name') or data.get('filename') or 'Fichier')
    href = f'/web/content/{attachment_id}?download=true'
    token = data.get('access_token')
    if token:
        href += f'&access_token={quote(str(token), safe="")}'
    link = etree.Element('a', {
        'href': href,
        'class': 'btn btn-light border d-inline-flex align-items-center gap-2 my-1 me-1 o_eurekam_kb_file',
    })
    icon_class = 'fa fa-file-pdf-o' if str(data.get('extension')).lower() == 'pdf' else 'fa fa-file-o'
    icon = etree.SubElement(link, 'i', {'class': icon_class, 'title': 'Télécharger', 'aria-hidden': 'true'})
    icon.tail = name
    return link


def render_portal_body(body):
    """Corps d'article affichable sans le JavaScript de Knowledge.

    - ``file`` : remplacé par un lien de téléchargement ;
    - autres blocs embarqués (``articleIndex``…) : retirés, la page portail affiche déjà
      la liste des sous-articles.
    """
    if not body:
        return body
    try:
        root = lxml_html.fragment_fromstring(str(body), create_parent='div')
    except (etree.ParserError, ValueError):
        return body
    for node in root.xpath('//*[@data-embedded]'):
        if node.getparent() is None:
            continue
        link = _file_link(node.get('data-embedded-props')) if node.get('data-embedded') == 'file' else None
        if link is not None:
            link.tail = node.tail
            node.getparent().replace(node, link)
        else:
            _drop_node(node)
    return Markup(lxml_html.tostring(root, encoding='unicode'))


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
        if 'eurekam_kb_count' in counters:
            Article = self._kb_article_model()
            values['eurekam_kb_count'] = (
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
            'body': render_portal_body(article.body),
            'ancestors': self._kb_ancestors(article, root),
            'siblings': siblings,
            'children': children,
            'page_name': 'kb_article',
        })
