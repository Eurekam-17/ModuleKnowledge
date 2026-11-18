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


# Libellés de l'interface portail, par langue d'interface. Littéraux (et non _()) car les
# chaînes Python des modules Eurekam ne sont pas traduites sur ce déploiement.
# Nouvelle langue : ajouter un dictionnaire avec les mêmes clés (traduction à faire relire).
# Langue sans dictionnaire : anglais.
KB_LABELS = {
    'fr': {
        'kb': "Base de connaissance",
        'kb_full': "Base de connaissance Eurekam",
        'card_text': "Guides, procédures et réponses aux questions fréquentes",
        'summary': "Sommaire",
        'updated': "Mis à jour le",
        'in_section': "Dans cette section",
        'back_to': "Retour à",
        'back_summary': "Retour au sommaire",
        'empty': "Aucun article n'est disponible pour le moment.",
        'open': "Ouvrir",
        'unavailable': "Base de connaissance indisponible",
        'unavailable_text': "La base de connaissance n'est pas encore accessible depuis votre "
                            "espace client. Merci de contacter le Service Client Eurekam si le "
                            "problème persiste.",
    },
    'en': {
        'kb': "Knowledge base",
        'kb_full': "Eurekam knowledge base",
        'card_text': "Guides, procedures and answers to frequently asked questions",
        'summary': "Contents",
        'updated': "Updated on",
        'in_section': "In this section",
        'back_to': "Back to",
        'back_summary': "Back to contents",
        'empty': "No article is available yet.",
        'open': "Open",
        'unavailable': "Knowledge base unavailable",
        'unavailable_text': "The knowledge base is not yet available from your customer area. "
                            "Please contact Eurekam Customer Service if the problem persists.",
    },
    # Allemand, italien, espagnol : prêts pour de futures rubriques, à faire relire.
    'de': {
        'kb': "Wissensdatenbank",
        'kb_full': "Eurekam Wissensdatenbank",
        'card_text': "Anleitungen, Verfahren und Antworten auf häufig gestellte Fragen",
        'summary': "Inhalt",
        'updated': "Aktualisiert am",
        'in_section': "In diesem Abschnitt",
        'back_to': "Zurück zu",
        'back_summary': "Zurück zum Inhalt",
        'empty': "Derzeit ist kein Artikel verfügbar.",
        'open': "Öffnen",
        'unavailable': "Wissensdatenbank nicht verfügbar",
        'unavailable_text': "Die Wissensdatenbank ist in Ihrem Kundenbereich noch nicht "
                            "verfügbar. Bitte wenden Sie sich an den Eurekam-Kundendienst, wenn "
                            "das Problem weiterhin besteht.",
    },
    'it': {
        'kb': "Base di conoscenza",
        'kb_full': "Base di conoscenza Eurekam",
        'card_text': "Guide, procedure e risposte alle domande frequenti",
        'summary': "Sommario",
        'updated': "Aggiornato il",
        'in_section': "In questa sezione",
        'back_to': "Torna a",
        'back_summary': "Torna al sommario",
        'empty': "Nessun articolo è disponibile al momento.",
        'open': "Apri",
        'unavailable': "Base di conoscenza non disponibile",
        'unavailable_text': "La base di conoscenza non è ancora accessibile dalla tua area "
                            "clienti. Se il problema persiste, contatta il Servizio Clienti "
                            "Eurekam.",
    },
    'es': {
        'kb': "Base de conocimiento",
        'kb_full': "Base de conocimiento Eurekam",
        'card_text': "Guías, procedimientos y respuestas a las preguntas frecuentes",
        'summary': "Índice",
        'updated': "Actualizado el",
        'in_section': "En esta sección",
        'back_to': "Volver a",
        'back_summary': "Volver al índice",
        'empty': "No hay ningún artículo disponible por el momento.",
        'open': "Abrir",
        'unavailable': "Base de conocimiento no disponible",
        'unavailable_text': "La base de conocimiento aún no está disponible desde su área de "
                            "cliente. Póngase en contacto con el Servicio al Cliente de Eurekam "
                            "si el problema persiste.",
    },
}


def kb_labels(lang):
    """Libellés pour la langue d'interface ``lang`` (deux lettres), anglais par défaut."""
    return KB_LABELS.get(lang) or KB_LABELS['en']


class KnowledgePortal(CustomerPortal):

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _kb_article_model(self):
        # Pas de sudo : les droits de l'utilisateur connecté (ir.rule) s'appliquent.
        return request.env['knowledge.article']

    def _kb_audience(self):
        """``(racine, domaine, langue d'interface)`` pour le compte connecté.

        Voir ``knowledge.article._eurekam_kb_audience`` : rubrique de sa langue, sinon
        rubrique anglaise (repli) ; base sans rubriques de langue pour un compte français.
        """
        return self._kb_article_model()._eurekam_kb_audience(request.env.user.lang)

    def _kb_values(self, ui_lang=None, **values):
        if ui_lang is None:
            ui_lang = self._kb_audience()[2]
        values.update({'kb_labels': kb_labels(ui_lang), 'kb_lang': ui_lang})
        return values

    def _prepare_portal_layout_values(self):
        # Libellés de la carte /my et du lien depuis les tickets, dans la langue du client.
        values = super()._prepare_portal_layout_values()
        values.setdefault('kb_labels', kb_labels(self._kb_audience()[2]))
        return values

    def _kb_nav_domain(self, audience_domain, extra=None):
        """Domaine de navigation : public du client, hors « éléments d'article »."""
        return audience_domain + [('is_article_item', '=', False)] + (extra or [])

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
        Article = self._kb_article_model()
        root_id = Article._eurekam_kb_root_id()
        if 'eurekam_kb_count' in counters:
            audience_root, audience_domain, ui_lang = self._kb_audience()
            values['eurekam_kb_count'] = (
                Article.search_count(self._kb_nav_domain(audience_domain)) if audience_root else 0)
        if 'knowledge_count' in counters and root_id and request.env.user.share:
            # Carte native « Connaissances » : pour un client, elle ne doit compter que les
            # articles partagés nominativement (McKesson, IT HEALTH…), pas la base partagée
            # que notre règle rend lisible. À 0, le portail masque la carte.
            values['knowledge_count'] = Article.search_count(
                ['!', ('id', 'child_of', root_id)])
        return values

    # ------------------------------------------------------------------
    # Routes
    # ------------------------------------------------------------------

    @http.route(['/my/kb'], type='http', auth='user', website=True)
    def portal_my_kb(self, **kw):
        Article = self._kb_article_model()
        audience_root, audience_domain, ui_lang = self._kb_audience()
        root = Article.search([('id', '=', audience_root)], limit=1) if audience_root else Article
        if not root:
            # Paramètre absent/invalide ou racine inaccessible : aucun article exposé.
            return request.render('eurekam_knowledge_portal.portal_no_kb',
                                  self._kb_values(ui_lang, page_name='kb'))
        children = Article.search(
            self._kb_nav_domain(audience_domain, [('parent_id', '=', root.id)]), order=NAV_ORDER)
        return request.render('eurekam_knowledge_portal.portal_kb_index', self._kb_values(
            ui_lang,
            root=root,
            children=children,
            page_name='kb',
        ))

    @http.route(['/my/kb/article/<int:article_id>'], type='http', auth='user', website=True)
    def portal_my_kb_article(self, article_id, **kw):
        Article = self._kb_article_model()
        audience_root, audience_domain, ui_lang = self._kb_audience()
        if not audience_root:
            return request.render('eurekam_knowledge_portal.portal_no_kb',
                                  self._kb_values(ui_lang, page_name='kb'))
        # Contrôle explicite du périmètre (en plus de l'ir.rule) : un article accessible par
        # un autre biais (ex. membre natif Knowledge), ou destiné à l'autre langue → 404.
        article = Article.search([('id', '=', article_id)] + audience_domain, limit=1)
        if not article:
            raise request.not_found()
        if article.id == audience_root:
            return request.redirect('/my/kb')
        root = Article.browse(audience_root)
        siblings = Article.search(
            self._kb_nav_domain(audience_domain, [('parent_id', '=', article.parent_id.id)]),
            order=NAV_ORDER)
        children = Article.search(
            self._kb_nav_domain(audience_domain, [('parent_id', '=', article.id)]), order=NAV_ORDER)
        return request.render('eurekam_knowledge_portal.portal_kb_article', self._kb_values(
            ui_lang,
            root=root,
            article=article,
            body=render_portal_body(article.body),
            ancestors=self._kb_ancestors(article, root),
            siblings=siblings,
            children=children,
            page_name='kb_article',
        ))
