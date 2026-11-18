# Eurekam Knowledge Portal (`eurekam_knowledge_portal`)

Odoo 18 Enterprise. Dépend de `knowledge` et `portal`.

## But

Donner aux **utilisateurs portail connectés** (clients hospitaliers) un accès **en lecture seule**
à l'arborescence « Base de connaissance » de Knowledge, **sans publication publique** des articles
(plus d'indexation Google) et **sans révéler les autres clients** (pas de partage nominatif
article par article, donc pas de liste de partners visible : conforme RGPD).

## Fonctionnement

| Élément | Rôle |
|---|---|
| `security/ir.model.access.csv` | Lecture de `knowledge.article` pour `base.group_portal`. |
| `security/knowledge_portal_rules.xml` | `ir.rule` portail : `[('id', 'child_of', eurekam_kb_root_id)]` (racine + descendants). |
| `models/ir_rule.py` | Injecte `eurekam_kb_root_id` dans le contexte d'évaluation des règles (le contexte natif ne contient pas `env`). |
| `models/knowledge_article.py` | Lecture du paramètre (fail-safe à 0), dépublication de l'arborescence, **blocage de toute republication** d'un article du périmètre (`UserError`). |
| `models/ir_http.py` | En-tête `X-Robots-Tag: noindex, nofollow` sur `/knowledge*` et `/my/kb*`. |
| `controllers/portal.py` | Routes `/my/kb` et `/my/kb/article/<id>`, compteur de la carte sur `/my`. |
| `controllers/knowledge.py` | Redirige les utilisateurs portail de `/knowledge/article/<id>` (liens internes entre articles) vers `/my/kb/article/<id>`. Les internes ne sont pas concernés. |
| `views/portal_templates.xml` | Carte « Base de connaissance Eurekam » sur `/my`, pages index/article/fallback, fil d'Ariane, lien KB sur les pages `/my/ticket*` (Helpdesk). |
| `post_init_hook` | À l'installation, passe `is_published=False` sur la racine et tous ses descendants. |

Aucun nouveau modèle, aucune donnée personnelle. Aucun `sudo()` sur les données métier : seuls la
lecture du paramètre système et la dépublication à l'installation sont en `sudo`.

L'utilisateur portail ne voit jamais : membres des articles, auteurs, autres utilisateurs portail,
historique. Les pages n'affichent que titre, émoji, date de mise à jour et contenu.

## Configuration après installation

Paramètre système **`eurekam_knowledge_portal.root_article_id`** = id de l'article racine
(`19` « Base de connaissance » en prod, valeur créée par défaut à l'installation).

Pour le modifier : *Paramètres → (mode développeur) → Technique → Paramètres → Paramètres système*,
rechercher `eurekam_knowledge_portal.root_article_id`.

- Valeur absente, invalide ou `0` → **aucun article exposé**, `/my/kb` affiche une page
  « Base de connaissance indisponible » (fail-safe).
- Ne pas créer le paramètre **avant** l'installation (contrainte d'unicité sur la clé).
- Après un changement de racine, relancer la dépublication du nouvel arbre si besoin (shell :
  `env['knowledge.article']._eurekam_kb_unpublish_tree()`).

## ⚠️ Avant le déploiement : dépublier manuellement

Le module dépublie l'arbre à l'installation, mais la **Phase 0** (spec §7.1) doit être faite dès
maintenant sur la prod, sans attendre le module :

```python
articles = env['knowledge.article'].search([('is_published', '=', True), ('id', 'child_of', 19)])
articles.write({'is_published': False})
env.cr.commit()
```

(`website_published` est un champ calculé à partir de `is_published` : écrire `is_published`.)
Vérifier aussi l'article **21 « Ma page privée de connaissance »**, publié mais hors racine : il
n'est pas couvert par ce module.

Désindexation : soumettre les anciennes URL `/knowledge/article/<id>` à la Google Search Console.

## Limites connues

- Les **vues embarquées** (kanban/liste d'articles, `data-embedded`) ne sont pas interactives
  côté portail : seul le HTML de l'article est rendu.
- Les **éléments d'article** (`is_article_item`) ne sont pas listés dans la navigation.
- Règles `ir.rule` combinées en OR entre groupes : un utilisateur portail auquel on ajouterait
  un groupe custom avec une règle permissive sur `knowledge.article` verrait plus d'articles.
  La route `/my/kb/article/<id>` revérifie toutefois explicitement le périmètre.
- La redirection `/knowledge/article/<id>` suppose la classe Enterprise
  `odoo.addons.knowledge.controllers.main.KnowledgeController.redirect_to_article`. Si elle est
  introuvable, un warning est logué au démarrage et la redirection est inactive (l'`ir.rule` reste
  appliquée).

## Tests automatiques

`tests/test_portal_access.py` (tag `post_install`) automatise les critères §8.1 à §8.6, le
fail-safe, le blocage de la republication et la page anonyme. Les tests créent leur propre
arborescence : ils ne dépendent pas de l'article 19.

⚠️ Comme pour les modules Jira, **une branche Odoo.sh de type Staging (`sandbox`) ne lance pas
les tests** : une montée de version y fait `-u` sans `--test-enable`, et un nouveau module n'y est
jamais installé automatiquement. « Test: Success » sur la sandbox ne prouve rien pour ce module.
Les lancer sur une branche *Development* ou sur une base locale :

```
odoo-bin -d <base> -i eurekam_knowledge_portal --test-enable --test-tags /eurekam_knowledge_portal --stop-after-init
```

Ces tests n'ont **jamais été exécutés** (pas d'Odoo sur le poste de développement). Deux d'entre
eux reposent sur des API Enterprise non vérifiées : la création directe d'un
`knowledge.article.member` (`test_portal_cannot_see_other_members`) et la redirection
`/knowledge/article/<id>` (sautée automatiquement si la classe n'est pas trouvée).

## Travers des modules précédents vérifiés

Revue faite le 2026-11-18 contre les correctifs de `eurekam_jira_*` et `eurekam_maintenance` :

| Travers déjà corrigé ailleurs | Ici |
|---|---|
| Méthode publique appelable par RPC sans contrôle de droits (Jira `d059ea0`) | Toutes les méthodes du module sont privées (`_eurekam_*`), vérifié par un test. |
| `search()` sans `sudo()` dans une surcharge qui casse un flux natif pour les utilisateurs sans groupe (Maintenance `511e517`, `a007d99`) | Le garde-fou de `write`/`create` ne lit qu'en `sudo` et ne se déclenche que si `is_published`/`parent_id` change (pas à chaque sauvegarde du corps). |
| API Odoo 17 périmées (`numbercall`, `kanban-box`, `STORE_ATTR`, `assertRaises` avec tuple) | `_post_dispatch`, `_eval_context`, `portal_docs_entry`, `o_portal_submenu`, `portal_common_category` vérifiés dans les sources 18.0. |
| `invisible="1"` sans commentaire (lint `s6r_unit_tests`), champ de modificateur déclaré trop bas | Aucune vue backend, aucun `invisible`. |
| Icônes `fa` sans `title` (`87d12e5`) | Toutes ont un texte adjacent ou un `title` (le contrôle Odoo ne vise pas le QWeb, ajouté par cohérence). |
| Chaînes `_()` jamais traduites sur ce déploiement | Libellés en français directement (même choix que les modules Jira). |
| Paramètre écrasé à chaque mise à jour | `ir.config_parameter` en `noupdate="1"`. |
| Aucun test livré | Ajoutés (voir ci-dessus). |

Risque résiduel à valider en recette : avec l'accès lecture, un utilisateur portail peut appeler
par RPC (`/web/dataset/call_kw`) les méthodes publiques natives de `knowledge.article` et lire ses
champs (ex. `create_uid`, `write_uid` : noms des collaborateurs Eurekam). Les membres d'articles
(autres clients) restent protégés par les règles natives de `knowledge.article.member`, ce que
vérifie `test_portal_cannot_see_other_members`.

## Recette (spec §8)

Compte de test : utilisateur portail dédié (ex. `kb-test@eurekam.fr`).

| # | Test | Résultat attendu | Résultat sandbox |
|---|---|---|---|
| 1 | `/my` puis `/my/kb` | Carte KB visible, arborescence de niveau 1 affichée | _à faire_ |
| 2 | Ouvrir articles niveaux 1, 2, 3 + liens internes | Navigation OK, fil d'Ariane correct | _à faire_ |
| 3 | `/my/kb/article/21` | 404 | _à faire_ |
| 4 | `/knowledge/article/21` (portail) | 404 / redirection | _à faire_ |
| 5 | Aucune page ne montre d'autres utilisateurs portail | Aucun nom | _à faire_ |
| 6 | Interne (Gillian) édite via `/odoo/knowledge` | Inchangé | _à faire_ |
| 7 | Désinstallation du module | Aucun article public | _à faire_ |
| + | Déconnecté : `/knowledge/article/19` | Redirection login, en-tête `X-Robots-Tag` | _à faire_ |
| + | Images dans un article (portail) | Affichées (sinon : règle `ir.attachment`, spec §6.3) | _à faire_ |
| + | Tenter de republier un article de l'arbre | `UserError` | _à faire_ |
