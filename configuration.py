#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, ModelSingleton, fields

__all__ = ['Configuration']


class Configuration(ModelSingleton, ModelSQL, ModelView):
    'Network Configuration'
    __name__ = 'network.configuration'

    item_sequence = fields.Property(fields.Many2One('ir.sequence',
            'Item Sequence', domain=[
                ('code', '=', 'network.item'),
                ]))
