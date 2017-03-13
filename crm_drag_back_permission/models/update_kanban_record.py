# -*- coding: utf-8 -*-
##############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#    Copyright (C) 2009-TODAY Cybrosys Technologies(<http://www.cybrosys.com>).
#    Author: Nilmar Shereef(<http://www.cybrosys.com>)
#    you can modify it under the terms of the GNU LESSER
#    GENERAL PUBLIC LICENSE (LGPL v3), Version 3.
#
#    It is forbidden to publish, distribute, sublicense, or sell copies
#    of the Software or modified copies of the Software.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU LESSER GENERAL PUBLIC LICENSE (LGPL v3) for more details.
#
#    You should have received a copy of the GNU LESSER GENERAL PUBLIC LICENSE
#    GENERAL PUBLIC LICENSE (LGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
from openerp import models, fields, api


class StageChange(models.Model):
    _inherit = 'crm.lead'

    stage_previous = fields.Integer(string="Previous stage", default=False)
    stage_next = fields.Integer(string="Next stage", default=False)
    stage_type = fields.Char()
    new_stage_id = fields.Selection([('previous', 'Previous'), ('current', 'Current'), ('next', 'Next')], readonly=True)
    previous = fields.Char(string="Previous Stage", compute='get_previous_stage')
    next_stage = fields.Char(string="Next Stage", compute='get_next_stage')

    current_lead = fields.Boolean(string="current lead", compute='get_lead')

    def on_change_user(self, cr, uid, ids, user_id, context=None):
        """ When changing the user, also set a team_id or restrict team id
            to the ones user_id is member of. """
        if not context:
            context = {}
        if user_id and context.get('team_id'):
            team = self.pool['crm.team'].browse(cr, uid, context['team_id'], context=context)
            if user_id in team.member_ids.ids:
                return {}
        temp = self.pool['crm.team']._get_default_team_id(cr, uid, context=context, user_id=user_id)
        u_id = self.pool.get('res.users').browse(cr, uid, [user_id], context=context)
        if u_id.has_group('base.group_sale_salesman_all_leads') and u_id.has_group(
                'base.group_sale_salesman') and u_id.has_group('base.group_sale_manager'):
            team_id = temp
        elif u_id.has_group('base.group_sale_salesman_all_leads') and u_id.has_group('base.group_sale_salesman'):
            team_id = self.pool.get('crm.team').search(cr, uid, [('user_id.id', '=', user_id)], context=context, limit=1)[0]
        elif u_id.has_group('base.group_sale_salesman'):
            team_id = u_id.sale_team_id.id
        return {'value': {'team_id': team_id}}

    @api.one
    def get_previous_stage(self):
        self.previous = self.env['crm.stage'].search([('id', '=', self.stage_previous)]).name

    @api.one
    def get_next_stage(self):
        self.next_stage = self.env['crm.stage'].search([('id', '=', self.stage_next)]).name

    @api.one
    def approve_oppor(self):
        self.write({'stage_id': self.env['crm.stage'].browse([self.stage_next]).id, 'stage_previous': self.stage_id.id, 'stage_next': 0, 'new_stage_id': ''})
        return

    @api.one
    def decline_oppor(self):
        self.write({'stage_id': self.env['crm.stage'].browse([self.stage_previous]).id, 'stage_previous': self.stage_id.id, 'stage_next': 0, 'new_stage_id': ''})
        return

    @api.multi
    def write(self, vals):
        if not vals.get('stage_previous') and vals.get('stage_id'):
            last_stage = self.browse(self.ids).stage_id

            if self.env['crm.stage'].browse([vals['stage_id']]).stage_order < last_stage.stage_order \
                    and not self.env['res.users'].browse(self._uid).has_group('base.group_sale_manager'):
                vals['stage_previous'] = last_stage.id
                vals['stage_next'] = vals['stage_id']
                vals['stage_type'] = "approval"
                vals['new_stage_id'] = 'current'

                to_approve = self.env['crm.stage'].search([('type', '=', 'approval'), ('name', '=', 'Waiting for approval')])
                if to_approve:
                    vals['stage_id'] = to_approve.id
                else:
                    values = {
                        'name': "Waiting for approval",
                        'type': "approval",
                        'stage_order': -1,
                    }
                    result = self.env['crm.stage'].create(values)
                    vals['stage_id'] = result.id
        elif vals.get('stage_id'):
            vals['stage_type'] = ""

        res = super(StageChange, self).write(vals)
        return res

    def get_approvals(self, cr, uid, context=None):
        tree_res = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'crm',
                                                                       'crm_case_tree_view_oppor')
        x = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'crm_drag_back_permission', 'action_waiting_approval_window')
        tree_id = tree_res and tree_res[1] or False
        form_res = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'crm',
                                                                       'crm_case_form_view_leads')
        form_id = form_res and form_res[1] or False
        approval_stage = self.pool.get('crm.lead')
        approvals = approval_stage.search(cr, uid, [('stage_id.type', '=', "approval")])
        user_obj = self.pool.get('res.users')
        u_id = user_obj.browse(cr, uid, uid, context=context)
        if u_id.has_group('base.group_sale_salesman_all_leads') and u_id.has_group(
                'base.group_sale_salesman') and u_id.has_group('base.group_sale_manager'):
            object_list = approvals
        elif u_id.has_group('base.group_sale_salesman_all_leads') and u_id.has_group('base.group_sale_salesman'):
            teams = self.pool.get('crm.team').search(cr, uid, [('user_id.id', '=', uid)])
            object_list = []
            if approvals:
                for obj in approvals:
                    if self.pool.get('crm.lead').browse(cr, uid, [obj]).team_id.id in teams:
                        object_list.append(obj)
        elif u_id.has_group('base.group_sale_salesman'):
            object_list = []
            if approvals:
                for obj in approvals:
                    if self.pool.get('crm.lead').browse(cr, uid, [obj]).user_id.id == uid:
                        object_list.append(obj)
        return {
            'model': 'ir.actions.act_window',
            'name': 'Waiting Approval',
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form,tree',
            'res_model': 'crm.lead',
            'views': [(tree_id, 'tree'), (form_id, 'form')],
            'domain': [('id', 'in', object_list)],
            'id': x[1],
        }


class NewStage(models.Model):
    _inherit = 'crm.stage'

    stage_order = fields.Integer(string='Order')
    type = fields.Selection([('lead', 'Lead'), ('opportunity', 'Opportunity'), ('both', 'Both'), ('approval', '')],
                            string='Type', required=True,
                            help="This field is used to distinguish stages related to Leads from stages related to "
                                 "Opportunities or to specify stages available for both types.")





