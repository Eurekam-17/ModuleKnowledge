# Module Knowledge

Module Odoo 18 d'**Eurekam** qui donne aux clients hospitaliers connectés au portail un accès en
lecture seule à la base de connaissance Knowledge, sans publication publique des articles
(plus d'indexation Google) et sans révéler les autres clients.

Spécification complète : [CLAUDE.md](CLAUDE.md).

| Module | Rôle | Dépendances |
|---|---|---|
| [`eurekam_knowledge_portal`](module/eurekam_knowledge_portal/README.md) | Règle d'accès portail sur l'arborescence racine, pages `/my/kb`, dépublication et garde-fou anti-republication | `knowledge` (Entreprise), `portal` |

## Règles absolues

- **Aucun article de l'arborescence accessible sans connexion.**
- **Sandbox d'abord** : rien n'est installé en recette ou en production (`eurekam.odoo.com`)
  sans validation écrite de Loïc.
- Aucune donnée personnelle dans le dépôt ; le seul paramètre métier est l'id de l'article racine.

## Structure du dépôt

```
.
├── CLAUDE.md                          Spécification
├── README.md                          Ce fichier
└── module/
    └── eurekam_knowledge_portal/
```

## Tests

Tests ORM et HTTP dans `module/eurekam_knowledge_portal/tests/`. Ils ne s'exécutent ni en local
(pas d'Odoo sur le poste) ni sur la branche Staging `sandbox` d'Odoo.sh : les lancer sur une
branche *Development* ou une base locale, avec `--test-enable --test-tags /eurekam_knowledge_portal`.

## Déploiement

Même principe que `ModuleJiraOdoo` et `GestionContratMaintenance` : dépôt sous l'organisation
GitHub `Eurekam-17`, ajouté comme sous-module git dans le monorepo du prestataire
`ScalizerOrg/eurekam`, branche `sandbox` uniquement. Odoo.sh n'installe jamais un nouveau module
tout seul : l'installer depuis Apps après le build, puis régler le paramètre
`eurekam_knowledge_portal.root_article_id`.
