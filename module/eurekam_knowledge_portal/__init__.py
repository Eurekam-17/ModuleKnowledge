# -*- coding: utf-8 -*-
from . import controllers
from . import models


def post_init_hook(env):
    """Règle n°1 : à l'installation, dépublie tous les descendants de l'article racine."""
    env['knowledge.article']._eurekam_kb_unpublish_tree()
