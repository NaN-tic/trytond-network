# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool
from .configuration import *
from .network import *

def register():
    Pool.register(
        Configuration,
        ItemType,
        ItemAttribute,
        ItemAttributeItemType,
        Item,
        RelationType,
        ItemRelation,
        ItemRelationAll,
        module='network', type_='model')
