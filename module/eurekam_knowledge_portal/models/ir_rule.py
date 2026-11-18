# -*- coding: utf-8 -*-
from odoo import api, models


class IrRule(models.Model):
    _inherit = 'ir.rule'

    @api.model
    def _eval_context(self):
        """Expose l'id de l'article racine aux domaines des ir.rule.

        Le contexte d'évaluation natif ne contient que ``user``, ``time``,
        ``company_ids`` et ``company_id`` : ``env`` n'y est pas disponible, d'où
        cette variable dédiée. Elle vaut 0 si le paramètre est absent ou invalide,
        ce qui rend le domaine ``child_of 0`` vide (fail-safe).

        Le cache de ``_compute_domain`` est vidé par ``ir.config_parameter`` à chaque
        modification d'un paramètre, donc un changement de racine est pris en compte
        immédiatement.
        """
        context = super()._eval_context()
        context['eurekam_kb_root_id'] = self.env['knowledge.article']._eurekam_kb_root_id()
        return context
