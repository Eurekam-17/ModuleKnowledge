# -*- coding: utf-8 -*-
"""Critères d'acceptation du §8 de la spécification, automatisés.

Les tests créent leur propre arborescence et règlent eux-mêmes le paramètre racine :
ils ne dépendent pas de l'article 19 de la production.
"""
from odoo.exceptions import AccessError, UserError
from odoo.tests import HttpCase, TransactionCase, new_test_user, tagged

from ..controllers.knowledge import PORTAL_REDIRECT_ACTIVE
from ..controllers.portal import render_portal_body
from ..models.knowledge_article import ROOT_PARAM


class KbPortalCommon:

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Article = cls.env['knowledge.article'].with_context(mail_create_nolog=True)
        cls.root = Article.create({'name': 'KB test root', 'internal_permission': 'write'})
        cls.child = Article.create({'name': 'KB test child', 'parent_id': cls.root.id})
        cls.grandchild = Article.create({'name': 'KB test grandchild', 'parent_id': cls.child.id})
        cls.great_grandchild = Article.create(
            {'name': 'KB test level 3', 'parent_id': cls.grandchild.id})
        cls.outside = Article.create({'name': 'KB test outside', 'internal_permission': 'write'})
        cls.tree = cls.root | cls.child | cls.grandchild | cls.great_grandchild
        cls.env['ir.config_parameter'].sudo().set_param(ROOT_PARAM, str(cls.root.id))

        cls.portal_user = new_test_user(
            cls.env, login='kb_portal_test', groups='base.group_portal', name='KB Portal Test')
        cls.other_portal_user = new_test_user(
            cls.env, login='kb_portal_other', groups='base.group_portal', name='Autre Client Test')
        cls.internal_user = new_test_user(
            cls.env, login='kb_internal_test', groups='base.group_user', name='KB Internal Test')

    def _portal_visible(self, user=None):
        Article = self.env['knowledge.article'].with_user(user or self.portal_user)
        return Article.search([('id', 'in', (self.tree | self.outside).ids)])


@tagged('post_install', '-at_install')
class TestKbPortalAccess(KbPortalCommon, TransactionCase):

    # §8.1 / §8.2 : lecture de la racine et des niveaux 1, 2, 3
    def test_portal_reads_whole_tree(self):
        self.assertEqual(self._portal_visible(), self.tree)
        self.great_grandchild.with_user(self.portal_user).read(['name', 'body'])

    # §8.3 : article hors arborescence
    def test_portal_cannot_read_outside_tree(self):
        with self.assertRaises(AccessError):
            self.outside.with_user(self.portal_user).read(['name'])

    def test_portal_is_read_only(self):
        with self.assertRaises(AccessError):
            self.child.with_user(self.portal_user).write({'name': 'Modifié par le portail'})

    # Fail-safe : paramètre absent, nul ou invalide → aucun article exposé
    def test_failsafe_without_root_parameter(self):
        for value in ('0', 'abc', '-5'):
            self.env['ir.config_parameter'].sudo().set_param(ROOT_PARAM, value)
            self.assertFalse(self._portal_visible(), f"articles exposés avec root={value!r}")

    def test_root_change_is_applied_immediately(self):
        self.env['ir.config_parameter'].sudo().set_param(ROOT_PARAM, str(self.grandchild.id))
        self.assertEqual(self._portal_visible(), self.grandchild | self.great_grandchild)

    # §8.5 : le portail ne voit pas les autres clients
    def test_portal_cannot_see_other_members(self):
        member = self.env['knowledge.article.member'].create({
            'article_id': self.child.id,
            'partner_id': self.other_portal_user.partner_id.id,
            'permission': 'read',
        })
        with self.assertRaises(AccessError):
            member.with_user(self.portal_user).partner_id.name  # noqa: B018

    # §8.6 : les internes gardent l'accès natif
    def test_internal_user_unaffected(self):
        visible = self.env['knowledge.article'].with_user(self.internal_user).search(
            [('id', 'in', (self.tree | self.outside).ids)])
        self.assertIn(self.outside, visible)
        self.outside.with_user(self.internal_user).write({'name': 'KB test outside renamed'})

    # Règle n°1 : rien de public dans l'arborescence
    def test_publishing_inside_tree_is_blocked(self):
        if 'is_published' not in self.child._fields:
            self.skipTest("website_knowledge non installé")
        with self.assertRaises(UserError):
            self.child.write({'is_published': True})
        self.outside.write({'is_published': True})  # hors périmètre : autorisé

    def test_moving_published_article_into_tree_is_blocked(self):
        if 'is_published' not in self.outside._fields:
            self.skipTest("website_knowledge non installé")
        self.outside.write({'is_published': True})
        with self.assertRaises(UserError):
            self.outside.write({'parent_id': self.child.id})

    def test_unpublish_tree(self):
        if 'is_published' not in self.child._fields:
            self.skipTest("website_knowledge non installé")
        Param = self.env['ir.config_parameter'].sudo()
        Param.set_param(ROOT_PARAM, '0')  # lève le garde-fou le temps de publier
        self.grandchild.write({'is_published': True})
        Param.set_param(ROOT_PARAM, str(self.root.id))
        self.env['knowledge.article']._eurekam_kb_unpublish_tree()
        self.assertFalse(self.tree.filtered('is_published'))

    # Garde-fou RPC (cf. revue prestataire Jira) : aucune méthode du module n'est publique
    def test_module_methods_are_private(self):
        Article = type(self.env['knowledge.article'])
        own = [name for name in dir(Article) if 'eurekam' in name]
        self.assertTrue(own)
        self.assertTrue(all(name.startswith('_') for name in own), own)


@tagged('post_install', '-at_install')
class TestKbPortalBody(TransactionCase):
    """Blocs embarqués Knowledge, rendus seulement par le JavaScript de l'éditeur."""

    def test_embedded_file_becomes_download_link(self):
        body = ('<p>Avant <span data-embedded="file" data-embedded-props=\'{"fileData": '
                '{"access_token": "tok", "extension": "pdf", "id": 42, "name": "Manuel.pdf"}}\'>'
                '</span> après</p><div data-embedded="articleIndex"></div><p>fin</p>')
        out = render_portal_body(body)
        self.assertIn('href="/web/content/42?download=true&amp;access_token=tok"', out)
        self.assertIn('Manuel.pdf', out)
        self.assertIn(' après', out)
        self.assertIn('<p>fin</p>', out)
        self.assertNotIn('data-embedded', out)

    def test_malformed_embedded_block_is_dropped(self):
        out = render_portal_body('<p>a<span data-embedded="file" data-embedded-props="x"></span>b</p>')
        self.assertIn('ab', out)
        self.assertNotIn('data-embedded', out)


@tagged('post_install', '-at_install')
class TestKbPortalHttp(KbPortalCommon, HttpCase):

    # §8.1
    def test_kb_index(self):
        self.authenticate('kb_portal_test', 'kb_portal_test')
        response = self.url_open('/my/kb')
        self.assertEqual(response.status_code, 200)
        self.assertIn('KB test child', response.text)
        self.assertNotIn('KB test outside', response.text)
        self.assertNotIn('Autre Client Test', response.text)
        self.assertIn('noindex', response.headers.get('X-Robots-Tag', ''))

    # §8.2
    def test_kb_article_levels(self):
        self.authenticate('kb_portal_test', 'kb_portal_test')
        for article in self.child | self.grandchild | self.great_grandchild:
            response = self.url_open(f'/my/kb/article/{article.id}')
            self.assertEqual(response.status_code, 200, article.name)
            self.assertIn(article.name, response.text)

    # §8.3
    def test_kb_article_outside_tree_is_404(self):
        self.authenticate('kb_portal_test', 'kb_portal_test')
        response = self.url_open(f'/my/kb/article/{self.outside.id}')
        self.assertEqual(response.status_code, 404)

    # §8.4
    def test_native_route_redirects_portal(self):
        if not PORTAL_REDIRECT_ACTIVE:
            self.skipTest("KnowledgeController.redirect_to_article introuvable")
        self.authenticate('kb_portal_test', 'kb_portal_test')
        response = self.url_open(f'/knowledge/article/{self.child.id}')
        self.assertTrue(response.url.endswith(f'/my/kb/article/{self.child.id}'), response.url)
        # Hors base partagée : comportement natif, jamais le contenu d'un article non partagé
        response = self.url_open(f'/knowledge/article/{self.outside.id}')
        self.assertNotIn('/my/kb/', response.url)
        self.assertNotEqual(response.status_code, 500)
        self.assertNotIn('KB test outside', response.text)

    # Bases partagées nominativement (McKesson…) : le membre portail garde l'accès natif
    def test_member_keeps_native_access_outside_tree(self):
        if not PORTAL_REDIRECT_ACTIVE:
            self.skipTest("KnowledgeController.redirect_to_article introuvable")
        self.env['knowledge.article.member'].create({
            'article_id': self.outside.id,
            'partner_id': self.portal_user.partner_id.id,
            'permission': 'read',
        })
        self.authenticate('kb_portal_test', 'kb_portal_test')
        response = self.url_open(f'/knowledge/article/{self.outside.id}')
        self.assertNotIn('/my/kb/', response.url)
        self.assertNotEqual(response.status_code, 500)

    # §8.6 : la route native reste fonctionnelle pour les internes (régression 500 du 2026-11-18)
    def test_native_route_still_works_for_internal(self):
        self.authenticate('kb_internal_test', 'kb_internal_test')
        response = self.url_open(f'/knowledge/article/{self.outside.id}')
        self.assertNotEqual(response.status_code, 500)

    # §3.3 : rien pour l'anonyme
    def test_anonymous_is_sent_to_login(self):
        response = self.url_open(f'/my/kb/article/{self.child.id}')
        self.assertIn('/web/login', response.url)
        self.assertNotIn('KB test child', response.text)

    def test_failsafe_page(self):
        self.env['ir.config_parameter'].sudo().set_param(ROOT_PARAM, '0')
        self.authenticate('kb_portal_test', 'kb_portal_test')
        response = self.url_open('/my/kb')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('KB test child', response.text)
