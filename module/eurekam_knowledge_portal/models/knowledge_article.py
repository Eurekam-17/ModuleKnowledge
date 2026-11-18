# -*- coding: utf-8 -*-
import logging

from odoo import _, api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

ROOT_PARAM = 'eurekam_knowledge_portal.root_article_id'


class KnowledgeArticle(models.Model):
    _inherit = 'knowledge.article'

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @api.model
    def _eurekam_kb_root_id(self):
        """Id de l'article racine partagé avec le portail, 0 si non configuré.

        ``sudo()`` limité à la lecture d'un paramètre de configuration (spec §5.4).
        """
        value = self.env['ir.config_parameter'].sudo().get_param(ROOT_PARAM, '0')
        try:
            root_id = int(value)
        except (TypeError, ValueError):
            return 0
        return root_id if root_id > 0 else 0

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
        """
        if 'helpdesk.team' not in self.env:
            return
        Team = self.env['helpdesk.team']
        if 'website_article_id' not in Team._fields:
            return
        teams = Team.sudo().with_context(active_test=False).search([
            ('website_article_id', 'child_of', self._eurekam_kb_root_id()),
        ])
        if teams:
            raise UserError(_(
                "La base de connaissance ne peut pas être réservée au portail : elle est encore "
                "affichée publiquement par l'Assistance.\n\n"
                "Équipe(s) concernée(s) : %(teams)s.\n\n"
                "Avant d'installer ce module, ouvrir Assistance → Configuration → Équipes, puis "
                "pour chacune décocher « Connaissances » (et vider le champ « Article » s'il reste "
                "renseigné). La page d'assistance publique n'affichera plus la base de "
                "connaissance ; les clients la retrouveront connectés sur /my/kb.",
                teams=', '.join(teams.mapped('display_name')),
            ))

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
