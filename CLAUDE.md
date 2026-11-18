# CLAUDE.md — Module `eurekam_knowledge_portal`

> Spécification de travail pour Claude Code.
> Rédigée le 18 novembre 2026 pour Loïc TAMARELLE (Président, Eurekam).
> Cibles successives : sandbox → recette → production (`eurekam.odoo.com`, Odoo 18 Enterprise).

---

## 1. Contexte et problème à résoudre

Eurekam développe Drugcam, un logiciel de contrôle par vision des préparations de chimiothérapie
en pharmacie hospitalière. **Drugcam n'est pas un dispositif médical** : ne jamais l'écrire ainsi,
ni dans le code, ni dans les libellés, ni dans la documentation du module.

Eurekam utilise le module `knowledge` d'Odoo 18 pour maintenir une base de connaissance partagée
avec ses clients hospitaliers. Aujourd'hui, le partage se fait via le champ `website_published`
des articles, ce qui rend les articles **publiquement accessibles et indexables par Google**.
L'équipe a pris ce choix parce que l'alternative native d'Odoo (partage article par article avec
des partners nommés) expose à chaque client la liste des autres partners avec qui l'article est
partagé — ce qui est contraire au RGPD.

**Objectif du module** : donner aux utilisateurs portail (`base.group_portal`) un accès en
lecture à l'arborescence « Base de connaissance » (article racine `id=19` sur la prod), sans
exposer les articles à l'extérieur et sans révéler les autres clients.

## 2. Règles non négociables

1. **Aucun article ne doit rester accessible sans connexion** une fois le module déployé.
   `website_published` sera forcé à `False` sur tous les descendants de l'article racine, et
   une data file du module pourra en plus supprimer le routage public de ces articles.
2. **Aucune donnée personnelle** n'est stockée dans le module. L'id de l'article racine est la
   seule donnée métier.
3. **Pas de code qui contourne les droits** : le module s'appuie exclusivement sur
   `ir.rule` + `ir.model.access` + overrides du routing Knowledge, jamais de `sudo()`
   permissif sans raison justifiée.
4. **Pas de nouveau modèle** : réutiliser `knowledge.article` et `res.groups` existants. Le
   seul enregistrement data custom est l'id de l'article racine (`eurekam_knowledge_portal.kb_root`).

## 3. Comportement cible

### 3.1 Côté utilisateur portail (client hospitalier connecté)

- Il se connecte avec son compte portail sur `eurekam.odoo.com`.
- Via son centre portail (`/my`), il voit un bloc « Base de connaissance Eurekam » qui liste les
  articles racines de l'arborescence partagée.
- Il peut naviguer dans les sous-articles. Les liens entre articles fonctionnent.
- Il ne voit **jamais** les autres utilisateurs portail ni leurs noms.
- Il ne voit pas les articles qui ne sont pas descendants de l'article racine partagé.
- Un lien vers la KB est aussi présent dans son portail Helpdesk (`/my/tickets`).

### 3.2 Côté interne (collaborateur Eurekam)

- L'accès actuel aux articles reste inchangé via l'interface Knowledge (`/odoo/knowledge`).
- Les règles d'accès internes (Workspace / Shared / Private / Members) continuent de
  fonctionner telles quelles.
- L'équipe peut éditer la base comme avant, avec l'éditeur Knowledge natif.

### 3.3 Côté public anonyme (Google, visiteur non connecté)

- Aucune URL publique ne doit répondre avec le contenu d'un article.
- `/knowledge/public/<id>` (route native quand `website_published`) doit renvoyer 404 ou
  redirection vers login pour les articles concernés.
- Les méta-balises `robots` sont inutiles car les routes elles-mêmes sont désactivées.

## 4. Structure du module

```
eurekam_knowledge_portal/
├── __init__.py
├── __manifest__.py
├── security/
│   ├── ir.model.access.csv          # accès portail sur knowledge.article en read
│   └── knowledge_portal_rules.xml   # ir.rule sur l'article racine + descendants
├── data/
│   └── kb_root.xml                  # id de l'article racine (external id Odoo)
├── models/
│   ├── __init__.py
│   └── knowledge_article.py         # override check_access si besoin (voir §6.2)
├── controllers/
│   ├── __init__.py
│   └── portal.py                    # routes /my/kb et /my/kb/article/<id>
├── views/
│   └── portal_templates.xml         # templates QWeb du centre portail
└── README.md
```

## 5. Contenu des fichiers

### 5.1 `__manifest__.py`

```python
{
    'name': 'Eurekam Knowledge Portal',
    'version': '18.0.1.0.0',
    'summary': "Donne aux utilisateurs portail la lecture de la base de connaissance Eurekam.",
    'author': 'Eurekam',
    'website': 'https://www.eurekam.fr',
    'license': 'LGPL-3',
    'depends': ['knowledge', 'portal'],
    'data': [
        'security/ir.model.access.csv',
        'security/knowledge_portal_rules.xml',
        'data/kb_root.xml',
        'views/portal_templates.xml',
    ],
    'installable': True,
    'application': False,
}
```

### 5.2 `data/kb_root.xml`

L'id de l'article racine à partager varie selon la base (prod `19`, sandbox et recette à
confirmer). Deux solutions :

- **Option A (choisie)** : paramétrage via `ir.config_parameter` pour qu'un admin le configure
  sans toucher au code.

```xml
<odoo noupdate="1">
    <record id="kb_root_param" model="ir.config_parameter">
        <field name="key">eurekam_knowledge_portal.root_article_id</field>
        <field name="value">19</field>
    </record>
</odoo>
```

Le controller et la rule liront `ir.config_parameter` pour obtenir l'id. Si le paramètre n'est
pas défini, le module retourne une page explicite et aucun article n'est exposé — fail-safe.

### 5.3 `security/ir.model.access.csv`

Donner au groupe `base.group_portal` l'accès lecture au modèle `knowledge.article`. La `ir.rule`
du §5.4 restreint le périmètre ensuite.

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_knowledge_article_portal,knowledge.article portal read,knowledge.model_knowledge_article,base.group_portal,1,0,0,0
```

### 5.4 `security/knowledge_portal_rules.xml`

```xml
<odoo noupdate="1">
    <record id="knowledge_article_portal_rule" model="ir.rule">
        <field name="name">Portal users : lecture des descendants de l'article racine Eurekam</field>
        <field name="model_id" ref="knowledge.model_knowledge_article"/>
        <field name="groups" eval="[(4, ref('base.group_portal'))]"/>
        <field name="domain_force">
            [('id', 'child_of', int(env['ir.config_parameter'].sudo().get_param('eurekam_knowledge_portal.root_article_id', '0')))]
        </field>
        <field name="perm_read" eval="True"/>
        <field name="perm_write" eval="False"/>
        <field name="perm_create" eval="False"/>
        <field name="perm_unlink" eval="False"/>
    </record>
</odoo>
```

> **Note** : `child_of` inclut l'article racine lui-même et toute sa descendance récursive.
> Le `sudo()` sur `ir.config_parameter.get_param` est acceptable : c'est de la lecture d'un
> paramètre de configuration, pas de la donnée métier.

### 5.5 `controllers/portal.py`

```python
# -*- coding: utf-8 -*-
from odoo import http, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal


class KnowledgePortal(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'knowledge_count' in counters:
            root_id = self._get_kb_root_id()
            values['knowledge_count'] = (
                request.env['knowledge.article'].search_count([('id', 'child_of', root_id)])
                if root_id else 0
            )
        return values

    def _get_kb_root_id(self):
        param = request.env['ir.config_parameter'].sudo().get_param(
            'eurekam_knowledge_portal.root_article_id', '0')
        try:
            return int(param)
        except (TypeError, ValueError):
            return 0

    @http.route(['/my/kb', '/my/kb/page/<int:page>'], type='http', auth='user', website=True)
    def portal_my_kb(self, page=1, **kw):
        root_id = self._get_kb_root_id()
        if not root_id:
            return request.render('eurekam_knowledge_portal.portal_no_kb')
        root = request.env['knowledge.article'].browse(root_id).exists()
        # Children de niveau 1 (uniquement les premiers enfants)
        children = request.env['knowledge.article'].search(
            [('parent_id', '=', root_id)], order='sequence, name')
        return request.render('eurekam_knowledge_portal.portal_kb_index', {
            'root': root,
            'children': children,
            'page_name': 'kb',
        })

    @http.route(['/my/kb/article/<int:article_id>'], type='http', auth='user', website=True)
    def portal_my_kb_article(self, article_id, **kw):
        article = request.env['knowledge.article'].browse(article_id).exists()
        if not article:
            return request.not_found()
        # La ir.rule rend invisibles les articles hors périmètre → le check devient implicite,
        # mais on vérifie explicitement par sécurité.
        root_id = self._get_kb_root_id()
        if root_id and not article.filtered_domain([('id', 'child_of', root_id)]):
            return request.not_found()
        # Children pour la nav latérale
        siblings = request.env['knowledge.article'].search(
            [('parent_id', '=', article.parent_id.id)], order='sequence, name')
        children = request.env['knowledge.article'].search(
            [('parent_id', '=', article.id)], order='sequence, name')
        return request.render('eurekam_knowledge_portal.portal_kb_article', {
            'article': article,
            'siblings': siblings,
            'children': children,
            'page_name': 'kb',
        })
```

### 5.6 `views/portal_templates.xml`

Trois templates QWeb :

- `portal_kb_index` : page d'accueil de la KB (liste des articles racines)
- `portal_kb_article` : affichage d'un article avec nav latérale (siblings + children)
- `portal_no_kb` : fallback si l'id racine n'est pas configuré
- Et un bloc à ajouter sur `/my` (home portal) qui affiche un lien vers `/my/kb`

Modèle à suivre : le template `portal_my_home` du module `portal` d'Odoo 18. Reprendre sa
structure (cards Bootstrap, breadcrumb). Icône suggérée : `fa-book`.

Templates à écrire en QWeb héritant de `portal.portal_breadcrumbs` et `portal.portal_layout`.

### 5.7 `README.md` du module

Documenter :

- Le but du module
- Le paramètre `eurekam_knowledge_portal.root_article_id` à configurer après installation
- Comment configurer l'id racine (via *Paramètres → Paramètres système → Paramètres techniques*)
- Le fait qu'il faut **dépublier manuellement** les articles actuellement `website_published=True`
  avant le déploiement (voir §7)

## 6. Points de vigilance techniques

### 6.1 Ordre des règles Odoo

Les `ir.rule` sont combinées en **OR entre groupes**. Si un portail user a par erreur un autre
groupe qui a une rule permissive sur `knowledge.article`, le OR gagne. Pour un portail user
standard, ce n'est pas un problème (ils n'ont que `base.group_portal`). Mais vérifier qu'aucun
groupe custom n'a été ajouté aux portails.

### 6.2 Pièges Knowledge Odoo 18

Le module `knowledge` d'Odoo 18 a un contrôleur `/knowledge/article/<id>` qui vérifie
`check_access_rule('read')`. Si la `ir.rule` est bien en place, le contrôleur natif renverra
404 sur les articles hors périmètre pour les portails users. Vérifier en recette qu'un portail
user ne peut pas accéder à `/knowledge/article/X` pour un X hors arborescence partagée.

### 6.3 Champs image/vidéo embarqués

Les articles peuvent contenir des `embedded_views` et des images. La rule sur `knowledge.article`
ne couvre pas automatiquement les pièces jointes (`ir.attachment`). Vérifier que les images
s'affichent bien pour un portail user. Si elles sont 403, ajouter une `ir.rule` sur
`ir.attachment` filtrant sur `res_model='knowledge.article'` et `res_id IN descendants(root)`.

### 6.4 Indexation Google résiduelle

Même après `website_published=False`, Google peut avoir indexé le contenu. Prévoir :
- Soumission des URLs à la Search Console Google pour désindexation rapide
- Ajouter `X-Robots-Tag: noindex` sur `/knowledge/*` dans le controller web pendant 30 jours

## 7. Plan de déploiement

### 7.1 Phase 0 — URGENT, avant même le dev

**Dépublication immédiate** des articles actuellement publics (99 articles descendants de
l'article racine `id=19` en prod). Opération réversible, à faire aujourd'hui :

```python
# Script à exécuter sur la prod en admin
articles = env['knowledge.article'].search([
    ('website_published', '=', True),
    ('id', 'child_of', 19),
])
articles.write({'website_published': False})
# Le temps que le module soit déployé, les clients n'auront plus accès.
# Prévenir Gillian Perrier (Service Client) pour qu'elle envoie un mail explicatif.
```

### 7.2 Phase 1 — Développement en sandbox

- Créer le module dans `/mnt/extra-addons/eurekam_knowledge_portal/` (chemin selon la config
  Odoo.sh)
- Installation en sandbox : `-i eurekam_knowledge_portal`
- Vérifier avec les tests de la §8

### 7.3 Phase 2 — Recette

- Merge sur la branche recette
- Configurer l'id racine en recette (à déterminer, probablement 19 aussi)
- Tester avec un utilisateur portail réel

### 7.4 Phase 3 — Production

- Merge sur main
- Déploiement
- Configurer le paramètre `root_article_id = 19`
- Envoi d'un mail aux clients hospitaliers avec le lien `/my/kb` et rappel de leurs identifiants
  portail

## 8. Critères d'acceptation (recette)

Tester en sandbox avec un compte portail (en créer un dédié si besoin, ex: `kb-test@eurekam.fr`) :

1. ✅ Le portail user accède à `/my/kb` et voit l'arborescence attendue.
2. ✅ Il peut ouvrir un article racine et ses enfants (niveau 1, 2, 3).
3. ✅ Il ne peut PAS accéder à un article hors arborescence (test avec l'id 21 « Ma page
    privée » qui n'est pas dans la racine 19) → 404 attendu.
4. ✅ `/knowledge/article/<id_hors_racine>` renvoie 404 ou redirection login.
5. ✅ Le portail user ne voit PAS la liste des autres portail users ni leurs noms.
6. ✅ Un collaborateur interne (ex: Gillian) peut toujours éditer la KB via `/odoo/knowledge`.
7. ✅ Après désinstallation du module, aucun article n'est public (sauf si réactivé explicitement).

## 9. Hors périmètre de ce module

- La **migration des articles** de l'arborescence actuelle : pas de reformatage, pas de
  renommage. L'arbo reste telle quelle.
- La **recherche fédérée** entre KB portail et autres contenus Odoo : à traiter plus tard si
  besoin.
- Le **versionnement/historique** des articles côté portail : reste accessible uniquement
  côté interne.
- Un **module de statistiques** sur ce que les clients consultent : à traiter plus tard si
  besoin (serait un module séparé `eurekam_knowledge_analytics`).

## 10. Ce que Claude Code doit faire, dans l'ordre

1. Lire ce fichier en entier ; poser ses questions avant de coder (branche, path du module,
   choix du paramètre fail-safe).
2. Créer la structure de dossiers et les fichiers (manifest, security, data, controllers,
   views, README).
3. Écrire les templates QWeb dans un style cohérent avec les templates portail natifs d'Odoo 18.
4. Installer en sandbox, vérifier que l'installation ne lève pas d'erreur de contrainte.
5. Dérouler les 7 tests du §8 avec un utilisateur portail de test. Documenter les résultats
   dans le README.
6. Attendre validation de Loïc avant de pousser en recette.

## 11. Ce que Loïc doit préparer ou trancher

1. **Hébergement et branche** : même pattern que les autres modules custom (sandbox / recette
   / main sur Odoo.sh). Préciser le path des addons custom.
2. **Id de l'article racine** à confirmer : `19` « Base de connaissance » en prod. À vérifier
   en recette si c'est bien le même id.
3. **Validation du design des templates portail** : Claude Code peut proposer une maquette
   simple, Loïc valide.
4. **Communication aux clients** (le mail post-déploiement expliquant l'URL `/my/kb`) : à
   rédiger par Gillian ou l'équipe Service Client après déploiement.
5. **Nettoyage de l'article orphelin** : id 21 « Ma page privée de connaissance » est publié
   publiquement mais pas dans la racine. À vérifier : est-ce un oubli ou un cas volontaire ?
