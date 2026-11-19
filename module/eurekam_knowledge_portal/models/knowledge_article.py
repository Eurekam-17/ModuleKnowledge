# -*- coding: utf-8 -*-
import html
import logging
import re
import uuid

from odoo import _, api, models
from odoo.exceptions import UserError
from odoo.tools import split_every

_logger = logging.getLogger(__name__)

# Pièces jointes citées dans un corps d'article : liens /web/content/<id>, images
# /web/image/<id>[-<checksum>], et blocs « fichier » embarqués ({"fileData": {..., "id": <id>}}).
ATTACHMENT_URL_RE = re.compile(r'/web/(?:content|image)/(\d+)(?=[-/?"\'&#]|$)')
EMBEDDED_FILE_RE = re.compile(r'"fileData"\s*:\s*\{[^{}]*?"id"\s*:\s*(\d+)')


def referenced_attachment_ids(body):
    """Ids des pièces jointes référencées dans un corps HTML d'article."""
    if not body:
        return set()
    text = html.unescape(str(body))
    ids = {int(i) for i in ATTACHMENT_URL_RE.findall(text)}
    ids |= {int(i) for i in EMBEDDED_FILE_RE.findall(text)}
    return ids

ROOT_PARAM = 'eurekam_knowledge_portal.root_article_id'
# Rubriques par langue, sous la racine : « en:463, de:520, it:530 ». Le français est la base
# elle-même (racine sans les rubriques de langue) ; l'anglais sert de langue de repli.
LANG_ROOTS_PARAM = 'eurekam_knowledge_portal.lang_root_articles'
# Ancien paramètre (18.0.1.0.5), converti par la migration 18.0.1.0.6.
LEGACY_EN_ROOT_PARAM = 'eurekam_knowledge_portal.en_root_article_id'
FALLBACK_LANG = 'en'


def parse_lang_roots(value):
    """« en:463, de:520 » → {'en': 463, 'de': 520}. Entrées invalides ignorées.

    Clé = code langue à deux lettres (préfixe de ``res.users.lang`` : de_DE → de) ; le
    français est exclu (c'est la base elle-même).
    """
    roots = {}
    for chunk in (value or '').replace(';', ',').split(','):
        lang, sep, article = chunk.partition(':')
        lang = lang.strip().lower()[:2]
        if not sep or len(lang) != 2 or not lang.isalpha() or lang == 'fr':
            continue
        try:
            article_id = int(article.strip())
        except ValueError:
            continue
        if article_id > 0:
            roots[lang] = article_id
    return roots


class KnowledgeArticle(models.Model):
    _inherit = 'knowledge.article'

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @api.model
    def _eurekam_kb_param_id(self, key):
        """Id d'article lu dans un paramètre système, 0 si absent ou invalide.

        ``sudo()`` limité à la lecture d'un paramètre de configuration (spec §5.4).
        """
        value = self.env['ir.config_parameter'].sudo().get_param(key, '0')
        try:
            article_id = int(value)
        except (TypeError, ValueError):
            return 0
        return article_id if article_id > 0 else 0

    @api.model
    def _eurekam_kb_root_id(self):
        """Id de l'article racine partagé avec le portail, 0 si non configuré."""
        return self._eurekam_kb_param_id(ROOT_PARAM)

    @api.model
    def _eurekam_kb_lang_roots(self):
        """Rubriques de langue valides : {'en': 463, ...}.

        Une rubrique hors de la base partagée, ou égale à la racine, est ignorée.
        Dictionnaire vide : pas de tri par langue, tout le monde voit toute la base.
        """
        root_id = self._eurekam_kb_root_id()
        if not root_id:
            return {}
        value = self.env['ir.config_parameter'].sudo().get_param(LANG_ROOTS_PARAM, '')
        roots = {lang: article_id for lang, article_id in parse_lang_roots(value).items()
                 if article_id != root_id}
        if not roots:
            return {}
        valid = set(self.sudo().search(
            [('id', 'in', list(roots.values())), ('id', 'child_of', root_id)]).ids)
        return {lang: article_id for lang, article_id in roots.items() if article_id in valid}

    @api.model
    def _eurekam_kb_audience(self, lang_code):
        """Partie de la base destinée à un compte de langue ``lang_code`` (ex. de_DE).

        Retourne ``(racine, domaine, langue d'interface)`` ; racine 0 si non configurée.
        - aucune rubrique de langue : toute la base, interface selon la langue du compte ;
        - compte en français : la base sans les rubriques de langue ;
        - autre langue avec sa rubrique : cette rubrique ;
        - autre langue sans rubrique : la rubrique anglaise (repli), interface anglaise ;
          sans rubrique anglaise non plus, la base française.
        Tri de présentation : l'ir.rule couvre toujours toute la base.
        """
        root_id = self._eurekam_kb_root_id()
        lang = (lang_code or '').lower()[:2]
        if not root_id:
            return 0, [], lang or 'fr'
        roots = self._eurekam_kb_lang_roots()
        french = [('id', 'child_of', root_id)]
        for lang_root in roots.values():
            french += ['!', ('id', 'child_of', lang_root)]
        if not roots:
            return root_id, french, lang or 'fr'
        if lang == 'fr':
            return root_id, french, 'fr'
        if lang in roots:
            return roots[lang], [('id', 'child_of', roots[lang])], lang
        if FALLBACK_LANG in roots:
            return roots[FALLBACK_LANG], [('id', 'child_of', roots[FALLBACK_LANG])], FALLBACK_LANG
        return root_id, french, 'fr'

    @api.model
    def _eurekam_kb_domain(self):
        """Domaine du périmètre partagé (racine + descendants), vide si non configuré."""
        return [('id', 'child_of', self._eurekam_kb_root_id())]

    def _eurekam_kb_in_scope(self):
        """Sous-ensemble de ``self`` appartenant au périmètre partagé."""
        if not self or not self._eurekam_kb_root_id():
            return self.browse()
        return self.search([('id', 'in', self.ids)] + self._eurekam_kb_domain())

    @api.model
    def _eurekam_kb_unpublish_tree(self):
        """Dépublie la racine et tous ses descendants (règle non négociable n°1).

        Ne fait rien si ``website_knowledge`` n'est pas installé (pas de champ
        ``is_published``). Exécuté en sudo : action d'installation, pas de lecture
        de données par un utilisateur.
        """
        if 'is_published' not in self._fields or not self._eurekam_kb_root_id():
            return
        self._eurekam_kb_check_no_helpdesk_team()
        articles = self.sudo().with_context(active_test=False).search(
            self._eurekam_kb_domain() + [('is_published', '=', True)])
        if articles:
            articles.write({'is_published': False})
            _logger.info("eurekam_knowledge_portal: %s article(s) dépublié(s).", len(articles))

    @api.model
    def _eurekam_kb_rotate_attachment_tokens(self):
        """Renouvelle les jetons d'accès des pièces jointes citées dans la base partagée.

        Un lien ``/web/content/<id>?access_token=…`` donne le fichier à quiconque le possède,
        connecté ou non : les liens indexés par Google quand les articles étaient publics
        restent valables après la dépublication. On génère un nouveau jeton pour chaque
        pièce jointe citée dans la base, puis on remplace l'ancien dans le corps de **tous**
        les articles (une même pièce jointe peut être citée ailleurs) : les anciens liens
        tombent, les articles continuent de fonctionner.

        Corps mis à jour en SQL : une écriture ORM du corps changerait la date « Mis à jour
        le » et ajouterait une version à l'historique pour un simple remplacement de jeton.
        Les pièces jointes d'articles marquées ``public`` (lisibles sans jeton) sont
        repassées en privé. Sudo : opération de maintenance (installation / migration).
        """
        if not self._eurekam_kb_root_id():
            return {}
        cr = self.env.cr
        Article = self.sudo().with_context(active_test=False)
        tree_ids = Article.search(self._eurekam_kb_domain()).ids
        attachment_ids = set()
        for chunk in split_every(20, tree_ids):
            cr.execute("SELECT body FROM knowledge_article WHERE id IN %s", [tuple(chunk)])
            for (body,) in cr.fetchall():
                attachment_ids |= referenced_attachment_ids(body)

        attachments = self.env['ir.attachment'].sudo().browse(sorted(attachment_ids)).exists()
        replacements = {}
        for attachment in attachments:
            if attachment.access_token:
                new_token = str(uuid.uuid4())
                replacements[attachment.access_token] = new_token
                attachment.write({'access_token': new_token})
        made_private = attachments.filtered(
            lambda a: a.public and a.res_model == 'knowledge.article')
        made_private.write({'public': False})

        updated_articles = 0
        if replacements:
            pattern = re.compile('|'.join(re.escape(token) for token in replacements))
            cr.execute("SELECT id FROM knowledge_article WHERE body IS NOT NULL ORDER BY id")
            all_ids = [row[0] for row in cr.fetchall()]
            for chunk in split_every(20, all_ids):
                cr.execute("SELECT id, body FROM knowledge_article WHERE id IN %s", [tuple(chunk)])
                for article_id, body in cr.fetchall():
                    new_body = pattern.sub(lambda match: replacements[match.group(0)], body)
                    if new_body != body:
                        cr.execute("UPDATE knowledge_article SET body = %s WHERE id = %s",
                                   [new_body, article_id])
                        updated_articles += 1
            self.env['knowledge.article'].invalidate_model(['body'])

        result = {
            'attachments': len(attachments),
            'tokens_renewed': len(replacements),
            'made_private': len(made_private),
            'articles_updated': updated_articles,
        }
        _logger.info("eurekam_knowledge_portal: renouvellement des jetons %s", result)
        return result

    @api.model
    def _eurekam_kb_check_no_helpdesk_team(self):
        """Refuse la dépublication si une équipe d'assistance expose encore l'arborescence.

        ``website_helpdesk_knowledge`` publie l'article « Connaissances » d'une équipe sur sa
        page d'assistance publique et interdit de le dépublier. Retirer cette fonction publique
        est une décision métier : on ne le fait pas automatiquement, on explique quoi faire.

        Décocher « Connaissances » sur l'équipe ne vide pas ``website_article_id`` (champ alors
        masqué, impossible à vider dans l'interface), et ce lien résiduel suffit à bloquer la
        dépublication. Quand la case est déjà décochée, la décision est prise : on retire le
        lien résiduel.
        """
        if 'helpdesk.team' not in self.env:
            return
        Team = self.env['helpdesk.team']
        if 'website_article_id' not in Team._fields:
            return
        teams = Team.sudo().with_context(active_test=False).search([
            ('website_article_id', 'child_of', self._eurekam_kb_root_id()),
        ])
        if 'use_website_helpdesk_knowledge' in Team._fields:
            publishing = teams.filtered('use_website_helpdesk_knowledge')
        else:
            publishing = teams
        if publishing:
            raise UserError(_(
                "La base de connaissance ne peut pas être réservée au portail : elle est encore "
                "affichée publiquement par l'Assistance.\n\n"
                "Équipe(s) concernée(s) : %(teams)s.\n\n"
                "Avant d'installer ce module, ouvrir Assistance → Configuration → Équipes, puis "
                "pour chacune décocher « Connaissances » et enregistrer. La page d'assistance "
                "publique n'affichera plus la base de connaissance ; les clients la retrouveront "
                "connectés sur /my/kb.",
                teams=', '.join(publishing.mapped('display_name')),
            ))
        if teams:
            teams.write({'website_article_id': False})
            _logger.info("eurekam_knowledge_portal: lien résiduel vers la base retiré des "
                         "équipes d'assistance %s.", teams.ids)

    # ------------------------------------------------------------------
    # Garde-fou : interdiction de republier un article du périmètre portail
    # ------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        articles = super().create(vals_list)
        if 'is_published' in self._fields:
            articles.filtered('is_published')._eurekam_kb_check_not_published()
        return articles

    def write(self, vals):
        res = super().write(vals)
        # Un déplacement (parent_id) peut aussi faire entrer un article publié dans le périmètre.
        if 'is_published' in self._fields and ('is_published' in vals or 'parent_id' in vals):
            self.filtered('is_published')._eurekam_kb_check_not_published()
        return res

    def _eurekam_kb_check_not_published(self):
        published_in_scope = self._eurekam_kb_in_scope_sudo()
        if published_in_scope:
            raise UserError(_(
                "Les articles de la base de connaissance partagée avec le portail ne peuvent "
                "pas être publiés sur le site web (accès public sans connexion).\n"
                "Article(s) concerné(s) : %(names)s",
                names=', '.join(published_in_scope.mapped('display_name')),
            ))

    def _eurekam_kb_in_scope_sudo(self):
        # sudo : le contrôle doit s'appliquer même si l'utilisateur ne voit pas la racine.
        return self.sudo()._eurekam_kb_in_scope()
