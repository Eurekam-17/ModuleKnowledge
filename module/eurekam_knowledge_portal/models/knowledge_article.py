# -*- coding: utf-8 -*-
import logging

from odoo import _, api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

ROOT_PARAM = 'eurekam_knowledge_portal.root_article_id'
EN_ROOT_PARAM = 'eurekam_knowledge_portal.en_root_article_id'


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
    def _eurekam_kb_en_root_id(self):
        """Id de la rubrique anglaise (sous la racine), réservée aux clients non francophones.

        0 si non configurée ou hors de la base partagée : pas de tri par langue.
        """
        en_root_id = self._eurekam_kb_param_id(EN_ROOT_PARAM)
        root_id = self._eurekam_kb_root_id()
        if not en_root_id or not root_id or en_root_id == root_id:
            return 0
        in_tree = self.sudo().search_count(
            [('id', '=', en_root_id), ('id', 'child_of', root_id)], limit=1)
        return en_root_id if in_tree else 0

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
