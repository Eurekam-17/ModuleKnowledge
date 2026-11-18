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

## Autres bases de connaissance

- **Bases par langue.** Le français est la base 19 elle-même. Les autres langues ont chacune
  une rubrique **sous** la racine 19, déclarée dans le paramètre
  `eurekam_knowledge_portal.lang_root_articles` (aujourd'hui `en:463`, « [EN] - Knowledge
  database »). Tri selon la langue du **compte** client (`res.users.lang`, champ Langue de la
  fiche contact) :
  - compte en français : la base 19 **sans** les rubriques de langue, interface en français ;
  - compte dans une langue déclarée : **uniquement** sa rubrique, qui devient l'accueil de
    `/my/kb`, interface dans sa langue ;
  - toute autre langue : la rubrique **anglaise** (langue de repli), interface en anglais.
  Un client qui suit un lien vers un article d'une autre langue obtient une 404. C'est un tri de
  présentation : la règle d'accès couvre toujours toute la base 19. Paramètre vide ou `aucun` :
  pas de tri, tout le monde voit toute la base. Une rubrique hors de la base 19 est ignorée.

  **Ajouter une langue** (ex. l'allemand), sans toucher au code :
  1. Dans Connaissances, créer sous l'article 19 une rubrique « [DE] - Wissensdatenbank » et y
     placer les articles et manuels en allemand ; noter son id (dans l'URL).
  2. *Paramètres → Langues* : activer l'allemand s'il ne l'est pas.
  3. *Paramètres → Technique → Paramètres système* : compléter
     `eurekam_knowledge_portal.lang_root_articles`, par ex. `en:463, de:520`.
  4. Mettre les clients concernés en allemand (fiche contact, champ Langue).
  Les libellés d'interface existent déjà en **fr, en, de, it, es** (`KB_LABELS` dans
  `controllers/portal.py` ; de, it et es sont à faire relire par un natif). Pour une autre
  langue (ex. néerlandais), ajouter un dictionnaire à `KB_LABELS` : sinon l'interface est en
  anglais, le contenu restant celui de sa rubrique.
- **Mc Kesson Knowledge base (334)** et **IT HEALTH Knowledge base (494)** sont des racines
  distinctes, partagées **nominativement** (membres Knowledge, dont des contacts portail). Le
  module ne les touche pas : leurs membres les consultent via le portail Knowledge natif, depuis
  la carte « Connaissances » de `/my`. Pour un client, cette carte ne compte que les articles
  partagés avec lui hors de la base 19 : elle n'apparaît donc que pour les membres de ces bases.
  `/knowledge/article/<id>` n'est redirigé vers `/my/kb` que pour les articles de la base 19.
  Rappel : dans ce mode natif, chaque membre voit la liste des autres membres (choix assumé par
  l'équipe pour ces deux bases).

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

## ⚠️ Prérequis : retirer la base de l'Assistance publique

En production, l'article 19 est la base « Connaissances » de l'équipe d'assistance
**Service Client**, affichée publiquement sur `/helpdesk/service-client-1`
(`website_helpdesk_knowledge`). Odoo interdit de dépublier un article utilisé par une équipe :
tant que c'est le cas, **l'installation du module est refusée** avec un message explicatif.

Avant l'installation : *Assistance → Configuration → Équipes → Service Client*, décocher
« Connaissances » et enregistrer. Odoo laisse alors l'article rattaché à l'équipe dans un champ
masqué (`website_article_id`), ce qui suffit à bloquer la dépublication : le module retire
lui-même ce lien résiduel, uniquement sur les équipes où « Connaissances » est déjà décoché. La page d'assistance
publique n'affiche alors plus la base de connaissance ; les clients la retrouvent connectés sur
`/my/kb` (un lien est ajouté sur leurs pages de tickets). Le module ne fait pas ce changement
lui-même : retirer une fonction publique est une décision métier (choix du 2026-11-18).

Une fois le module installé, réactiver « Connaissances » sur l'équipe avec cet article est bloqué
par le garde-fou anti-republication.

Après l'installation, sur le site « Support Eurekam » (fait sur la sandbox le 2026-11-18, à refaire
en production) : le menu « FAQ » (`website.menu` n°12) et le lien « Knowledge base » de la page
d'accueil (`website.homepage`, vue n°5899) pointaient vers
`/helpdesk/service-sav-1/knowledge/home?auto_unfold=1`. Sans base rattachée à l'équipe, Knowledge y
affiche le premier article encore publié (l'article 21, une page de test). Les faire pointer vers
`/my/kb`, et dépublier l'article 21.

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

Compte de test sur la sandbox : `kb-test@eurekam.fr` (utilisateur portail n°850, mot de passe dans
`config/kb_test_account.local.json`, ignoré par git). Recette du 2026-11-18, version 18.0.1.0.2.

| # | Test | Résultat attendu | Résultat sandbox |
|---|---|---|---|
| 1 | `/my` puis `/my/kb` | Carte KB visible, arborescence de niveau 1 affichée | ✅ carte affichée, 9 rubriques |
| 2 | Ouvrir des articles + liens internes | Navigation OK, fil d'Ariane correct | ✅ (vérifié au niveau 1 ; niveaux 2-3 à confirmer par l'équipe) |
| 3 | `/my/kb/article/21` | 404 | ✅ 404 |
| 4 | `/knowledge/article/21` (portail) | 404 / redirection | ✅ redirigé vers `/my/kb/article/21`, 404 |
| 5 | Aucune page ne montre d'autres utilisateurs | Aucun nom | ✅ ; par RPC le compte ne voit que lui-même, aucun membre d'article |
| 6 | Interne édite via `/odoo/knowledge` | Inchangé | ✅ `/knowledge/article/19` en admin → `/odoo/knowledge/19` (après correctif 18.0.1.0.1) |
| 7 | Désinstallation du module | Aucun article public | _à faire_ |
| + | Déconnecté : `/knowledge/article/19`, `/my/kb/article/19` | Redirection login | ✅ |
| + | Images dans un article (portail) | Affichées | ✅ (articles 454, 455, 456) |
| + | Fichiers intégrés (manuels PDF) | Téléchargeables | ✅ après correctif 18.0.1.0.2 (16 liens sur « Manuels utilisateur ») |
| + | Lien KB sur `/my/tickets` | Bouton présent | ✅ |
| + | Republier un article de l'arbre | `UserError` | _à faire_ |
| + | Portail Knowledge natif (`/knowledge/home`) | Rien d'exposé | ✅ vide (« Pas encore d'article ») |
| + | Compte en français (18.0.1.0.5) | Base 19 sans la rubrique [EN] | ✅ 8 rubriques, 75 articles ; `/my/kb/article/463` → 404 |
| + | Compte en anglais (18.0.1.0.5) | Rubrique [EN] seule, interface anglaise | ✅ 5 rubriques, 24 articles, « Contents », « Updated on », manuels EN téléchargeables ; article FR 204 → 404 |
| + | Base McKesson (`/knowledge/article/334`, interne) | Comportement natif | ✅ ouvre l'article dans Knowledge |
| + | Carte native « Connaissances » pour un client sans partage nominatif | Masquée | ✅ compteur 0 |
| + | Migration 18.0.1.0.6 | `en_root_article_id` → `lang_root_articles` | ✅ ancien paramètre supprimé, nouveau = `en:463` |
| + | Compte en français (18.0.1.0.6) | Inchangé | ✅ 8 rubriques, carte et bouton tickets en français |
| + | Compte en allemand sans rubrique DE | Repli sur l'anglais | _à faire_ (couvert par `test_language_without_section_falls_back_to_english`) |

Anomalies trouvées pendant la recette, corrigées :
- 18.0.1.0.1 : `/knowledge/article/<id>` en erreur 500 pour tous (signature de
  `redirect_to_article` en arguments nommés dans `website_knowledge`).
- 18.0.1.0.2 : les 41 fichiers intégrés (`data-embedded="file"`) n'étaient rendus que par le
  JavaScript de Knowledge, donc invisibles côté portail ; la date affichée était celle de
  l'installation.

Points ouverts : l'article 21 (hors arborescence) est encore publié, donc public ; la carte native
« Connaissances » de `/my` mène les clients à une page vide.
