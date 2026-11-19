# Liens cassés dans la base de connaissance (article 19)

Relevé du 2026-11-19 sur Recette (copie de la production : mêmes articles, mêmes ids).
Ces liens sont aussi cassés en production : ils ne viennent pas du module `eurekam_knowledge_portal`.

**Comment corriger** : dans Connaissances, ouvrir l'article, sélectionner le texte du lien, et le
remplacer par un lien vers l'article cible (bouton lien, ou commande `/article` dans l'éditeur).
Un lien interne s'écrit `/knowledge/article/<id>` : il fonctionne pour les collaborateurs et, avec
le module, pour les clients connectés.

## 1. Anciens liens vers le back-office (`/web#id=…&model=knowledge.article`) — 7 liens

Format d'adresse antérieur à Odoo 17, qui ouvre l'interface interne. Un client ne peut jamais
l'ouvrir.

| Article à corriger | Texte du lien | Article visé |
|---|---|---|
| 160 — Comment terminer la préparation en cas de blocage… | « terminer manuellement une préparation » | 159 — Est-il possible de terminer manuellement une préparation avant l'étape de présentation de l'étiquette de fin ? |
| 162 — Est-ce possible de prélever un volume de prescription dans une seringue inadaptée ? | « lien » | 161 — Comment prélever avec précision un volume de prescription ? |
| 176 — Qu'est ce que le « Volume théorique seulement »… | « décomposer un volume de prescription en plusieurs seringues sur Assist » | 161 — Comment prélever avec précision un volume de prescription ? (à confirmer : le texte du lien ne correspond pas tout à fait) |
| 182 — Comment activer une nouvelle seringue lors d'un changement de fournisseur ? | « message » | 156 — Comment présenter manuellement une seringue qui n'est pas compatible Drugcam ? |
| 184 — Pourquoi n'y a t-il pas de détection lors de la présentation de mon flacon ? | « Drugcam Barcode Reader ? » | 172 — Comment extraire le GTIN d'un datamatrix flacon avec Drugcam Barcode Reader ? |
| 184 — (même article) | « catalogue flacon » | 185 — Liste des flacons |
| 186 — Pourquoi la lecture de mon datamatrix flacon est-il toujours invalide… | « Drugcam Barcode Reader » | 172 — Comment extraire le GTIN d'un datamatrix flacon avec Drugcam Barcode Reader ? |

## 2. Liens vers l'ancienne base de connaissance (`support.eurekam.fr/#knowledge_base/…`) — 10 liens

Adresses de l'ancien outil de support (« answer/N ») qui n'existent plus : elles retombent sur la
page d'accueil du site. Les articles visés sont **proposés d'après le texte du lien**, à valider par
le Service Client.

| Article à corriger | Texte du lien | Ancienne réponse | Article proposé |
|---|---|---|---|
| 131 — Où consulter le catalogue flacon de Drugcam ? | « https://support.eurekam.fr » | page d'accueil | 185 — Liste des flacons |
| 132 — Qu'est ce qu'un numéro d'apprentissage ? | « catalogue » | answer/1 | 185 — Liste des flacons |
| 136 — Comment savoir si ma base de données flacons est bien à jour… | « catalogue flacon » | answer/1 | 185 — Liste des flacons |
| 136 — (même article) | « numéro de version » | answer/22 | 133 — Comment vérifier le numéro de version de ma base de données flacons sur Control ? |
| 137 — Comment intégrer une nouvelle spécialité qui n'existe pas dans le catalogue flacon ? | « catalogue » | answer/1 | 185 — Liste des flacons |
| 137 — (même article) | « vidéo d'apprentissage » | answer/16 | 130 — Comment faire une vidéo d'apprentissage de flacon ? |
| 137 — (même article) | « numéro de version » | answer/22 | 133 — Comment vérifier le numéro de version… |
| 191 — Comment désactiver la détection automatique de seringue sur les produits colorés ? | « indexations manuelles sur Assist » | answer/40 | 155 — Comment ajouter des étapes (indexation manuelle) en cours de préparation ? |
| 170 — Comment extraire le GTIN d'une poche avec Drugcam Barcode Reader ? | lien posé sur une image | answer/41 | à identifier |

Les articles **145** (« Comment présenter tous les flacons avant de les reconstituer ? ») et **182**
mentionnent aussi `support.eurekam.fr` : à relire.

## 3. Liens écrits en dur vers la production — 2 liens

| Article à corriger | Texte du lien | Correction |
|---|---|---|
| 19 — Base de connaissance | « [EN] - Knowledge database » (et un second lien sans texte) | remplacer `https://eurekam.odoo.com/knowledge/article/463` par un lien interne vers l'article 463 |

Sans gravité pour les clients (l'article 19 n'est pas affiché tel quel dans le portail), mais ces
liens envoient vers la production depuis la sandbox et Recette.

## Non concernés

Les 60 liens internes au format `/knowledge/article/<id>` fonctionnent.
