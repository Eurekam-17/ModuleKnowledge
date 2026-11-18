# -*- coding: utf-8 -*-
{
    'name': 'Eurekam Knowledge Portal',
    'version': '18.0.1.0.0',
    'category': 'Productivity/Knowledge',
    'summary': "Donne aux utilisateurs portail la lecture de la base de connaissance Eurekam.",
    'description': """
Accès en lecture seule, pour les utilisateurs portail connectés, à l'arborescence
« Base de connaissance » (article racine configurable via le paramètre système
``eurekam_knowledge_portal.root_article_id``), sans publication publique des articles
et sans exposer les autres clients.
""",
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
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
}
