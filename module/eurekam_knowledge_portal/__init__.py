# -*- coding: utf-8 -*-
from . import controllers
from . import models


def post_init_hook(env):
    """Règle n°1 : à l'installation, dépublie tous les descendants de l'article racine,
    puis invalide les liens de fichiers déjà diffusés (nouveaux jetons d'accès)."""
    Article = env['knowledge.article']
    Article._eurekam_kb_unpublish_tree()
    Article._eurekam_kb_rotate_attachment_tokens()
