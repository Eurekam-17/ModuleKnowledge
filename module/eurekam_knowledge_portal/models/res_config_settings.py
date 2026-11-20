# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from .knowledge_article import LANG_ROOTS_PARAM, ROOT_PARAM, parse_lang_roots

# Langues proposées dans l'écran de paramétrage (libellés d'interface déjà traduits dans
# controllers/portal.py). Une autre langue reste possible via le paramètre système.
SETTINGS_LANGS = ('en', 'de', 'it', 'es')
LANG_LABELS = {'en': "anglais", 'de': "allemand", 'it': "italien", 'es': "espagnol"}


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    eurekam_kb_root_article_id = fields.Many2one(
        'knowledge.article', string="Article racine",
        domain="[('is_article_item', '=', False)]",
        help="Article dont toute la descendance est lisible par les clients connectés au "
             "portail (/my/kb). Vide : aucun article n'est exposé.")
    eurekam_kb_en_article_id = fields.Many2one(
        'knowledge.article', string="Anglais",
        domain="[('id', 'child_of', eurekam_kb_root_article_id or 0), "
               "('id', '!=', eurekam_kb_root_article_id or 0), ('is_article_item', '=', False)]",
        help="Rubrique réservée aux clients dont le compte est en anglais, et langue de repli "
             "des langues sans rubrique.")
    eurekam_kb_de_article_id = fields.Many2one(
        'knowledge.article', string="Allemand",
        domain="[('id', 'child_of', eurekam_kb_root_article_id or 0), "
               "('id', '!=', eurekam_kb_root_article_id or 0), ('is_article_item', '=', False)]")
    eurekam_kb_it_article_id = fields.Many2one(
        'knowledge.article', string="Italien",
        domain="[('id', 'child_of', eurekam_kb_root_article_id or 0), "
               "('id', '!=', eurekam_kb_root_article_id or 0), ('is_article_item', '=', False)]")
    eurekam_kb_es_article_id = fields.Many2one(
        'knowledge.article', string="Espagnol",
        domain="[('id', 'child_of', eurekam_kb_root_article_id or 0), "
               "('id', '!=', eurekam_kb_root_article_id or 0), ('is_article_item', '=', False)]")
    eurekam_kb_other_langs = fields.Char(
        string="Autres langues", readonly=True,
        help="Rubriques d'autres langues déclarées directement dans le paramètre système "
             "eurekam_knowledge_portal.lang_root_articles (conservées telles quelles).")
    eurekam_kb_article_count = fields.Integer(string="Articles partagés", readonly=True)

    # ------------------------------------------------------------------
    # Lecture / écriture des paramètres système
    # ------------------------------------------------------------------

    @api.model
    def get_values(self):
        # Valeurs chargées ici, pas par un compute : un compute sans dépendance n'est pas
        # évalué à l'ouverture des paramètres (cf. module Jira, correctif d99805d).
        res = super().get_values()
        Param = self.env['ir.config_parameter'].sudo()
        Article = self.env['knowledge.article'].sudo()
        root = Article.browse(Article._eurekam_kb_root_id()).exists()
        roots = parse_lang_roots(Param.get_param(LANG_ROOTS_PARAM, ''))
        res['eurekam_kb_root_article_id'] = root.id
        for lang in SETTINGS_LANGS:
            article = Article.browse(roots.get(lang, 0)).exists()
            res[f'eurekam_kb_{lang}_article_id'] = article.id
        others = {lang: art for lang, art in roots.items() if lang not in SETTINGS_LANGS}
        res['eurekam_kb_other_langs'] = ', '.join(f'{lang}:{art}' for lang, art in sorted(others.items()))
        res['eurekam_kb_article_count'] = (
            Article.search_count([('id', 'child_of', root.id)]) if root else 0)
        return res

    def set_values(self):
        super().set_values()
        if not self.env.user.has_group('base.group_system'):
            # Les paramètres ne sont enregistrables que par un administrateur ; par prudence,
            # aucun changement si quelqu'un d'autre enregistre un autre écran de paramètres.
            return
        Param = self.env['ir.config_parameter'].sudo()
        Article = self.env['knowledge.article'].sudo()
        root = self.eurekam_kb_root_article_id
        old_root_id = Article._eurekam_kb_root_id()

        chosen = {lang: self[f'eurekam_kb_{lang}_article_id'] for lang in SETTINGS_LANGS}
        chosen = {lang: article for lang, article in chosen.items() if article}
        for lang, article in chosen.items():
            if not root or article == root or not Article.search_count(
                    [('id', '=', article.id), ('id', 'child_of', root.id)]):
                raise UserError(_(
                    "La rubrique %(lang)s « %(article)s » doit se trouver sous l'article racine "
                    "« %(root)s » : sinon les clients n'y ont pas accès.",
                    lang=LANG_LABELS[lang], article=article.display_name,
                    root=root.display_name if root else "-"))
        duplicates = [a for a in chosen.values() if list(chosen.values()).count(a) > 1]
        if duplicates:
            raise UserError(_("Une même rubrique ne peut pas servir à deux langues : %s.",
                              duplicates[0].display_name))

        # Langues hors écran déclarées dans le paramètre : conservées telles quelles.
        roots = {lang: art for lang, art in parse_lang_roots(Param.get_param(LANG_ROOTS_PARAM, '')).items()
                 if lang not in SETTINGS_LANGS}
        roots.update({lang: article.id for lang, article in chosen.items()})
        Param.set_param(ROOT_PARAM, str(root.id) if root else '0')
        Param.set_param(LANG_ROOTS_PARAM,
                        ', '.join(f'{lang}:{art}' for lang, art in roots.items()) or 'aucun')

        if root and root.id != old_root_id:
            # Nouvelle base partagée : mêmes garanties qu'à l'installation (aucun article
            # public, liens de fichiers déjà diffusés invalidés).
            Article._eurekam_kb_unpublish_tree()
            Article._eurekam_kb_rotate_attachment_tokens()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_eurekam_kb_rotate_tokens(self):
        """Bouton « Renouveler les jetons des fichiers » (administrateurs uniquement)."""
        if not self.env.user.has_group('base.group_system'):
            raise AccessError(_("Seul un administrateur peut renouveler les jetons."))
        result = self.env['knowledge.article']._eurekam_kb_rotate_attachment_tokens()
        message = _(
            "%(tokens)s jeton(s) renouvelé(s) sur %(attachments)s fichier(s) cité(s), "
            "%(articles)s article(s) mis à jour. Les anciens liens ne fonctionnent plus.",
            tokens=result.get('tokens_renewed', 0), attachments=result.get('attachments', 0),
            articles=result.get('articles_updated', 0))
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'title': _("Base de connaissance portail"), 'message': message,
                       'type': 'success', 'sticky': False},
        }
