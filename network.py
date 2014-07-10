from sql import Union, As, Column

from trytond.pool import Pool, PoolMeta
from trytond.model import ModelSQL, ModelView, DictSchemaMixin, fields
from trytond.transaction import Transaction
from trytond.pyson import Eval
from trytond.rpc import RPC
from trytond.ir.ui.menu import CLIENT_ICONS

__all__ = ['ItemType', 'ItemAttribute', 'ItemAttributeItemType', 'Item',
    'RelationType', 'ItemRelation', 'ItemRelationAll']
__metaclass__ = PoolMeta


class ItemType(ModelSQL, ModelView):
    'Network Item Type'
    __name__ = 'network.item.type'
    name = fields.Char('Name', required=True, translate=True)
    icon = fields.Selection('list_icons', 'Icon', translate=False)
    attributes = fields.Many2Many(
        'network.item.attribute-network.item.type-set', 'type', 'attribute',
        'Attributes')

    @staticmethod
    def list_icons():
        pool = Pool()
        Icon = pool.get('ir.ui.icon')
        return sorted(CLIENT_ICONS
            + [(name, name) for _, name in Icon.list_icons()])


class ItemAttribute(DictSchemaMixin, ModelSQL, ModelView):
    "Network Item Attribute"
    __name__ = 'network.item.attribute'
    types = fields.Many2Many('network.item.attribute-network.item.type-set',
        'attribute', 'type', 'Types')


class ItemAttributeItemType(ModelSQL):
    "Network Item Attribute - Network Item Type"
    __name__ = 'network.item.attribute-network.item.type-set'
    attribute = fields.Many2One('network.item.attribute', 'Attribute',
        ondelete='CASCADE', select=True, required=True)
    type = fields.Many2One('network.item.type', 'Item', ondelete='CASCADE',
        select=True, required=True)


class Item(ModelSQL, ModelView):
    'Network Item'
    __name__ = 'network.item'
    name = fields.Char('Name', select=True)
    code = fields.Char('Code', required=True, select=True, readonly=True)
    type = fields.Many2One('network.item.type', 'Type', required=True,
        ondelete='RESTRICT')
    active = fields.Boolean('Active')
    relations = fields.One2Many('network.relation.all', 'from_', 'Relations')
    notes = fields.Text('Notes')
    icon = fields.Function(fields.Selection('list_icons', 'Icon',
            translate=False), 'get_icon')
    attributes = fields.Dict('network.item.attribute', 'Attributes',
        domain=[
            ('types', '=', Eval('type')),
            ], depends=['type'])

    @classmethod
    def __setup__(cls):
        super(Item, cls).__setup__()
        cls._sql_constraints = [
            ('code_uniq', 'UNIQUE(code)',
                'The code of the network item must be unique.')
            ]
        # TODO: Update of cls.__rpc__ with list_icons can be removed on Tryton
        # 3.4. See: https://bugs.tryton.org/issue4043
        cls.__rpc__.update({
                'list_icons': RPC(),
                })

    @staticmethod
    def default_active():
        return True

    def get_icon(self, name):
        return self.type.icon

    @staticmethod
    def list_icons():
        pool = Pool()
        Icon = pool.get('ir.ui.icon')
        return sorted(CLIENT_ICONS
            + [(name, name) for _, name in Icon.list_icons()])

    @classmethod
    def create(cls, vlist):
        Sequence = Pool().get('ir.sequence')
        Configuration = Pool().get('network.configuration')

        vlist = [x.copy() for x in vlist]
        for values in vlist:
            if not values.get('code'):
                config = Configuration(1)
                values['code'] = Sequence.get_id(config.item_sequence.id)
        return super(Item, cls).create(vlist)

    def get_attribute(self, name):
        """
        Returns the value of the given attribute.

        Other modules may want to implement their own way of searching for a
        given attribute, for example by considering related items.
        """
        return self.attributes.get(name) if self.attributes else None


class RelationType(ModelSQL, ModelView):
    'Network Relation Type'
    __name__ = 'network.relation.type'

    name = fields.Char('Name', required=True, translate=True)
    reverse = fields.Many2One('network.relation.type', 'Reverse Relation')


class ItemRelation(ModelSQL):
    'Network Relation'
    __name__ = 'network.relation'

    from_ = fields.Many2One('network.item', 'From', required=True, select=True,
        ondelete='CASCADE')
    to = fields.Many2One('network.item', 'To', required=True, select=True,
        ondelete='CASCADE')
    type = fields.Many2One('network.relation.type', 'Type', required=True,
        select=True)


class ItemRelationAll(ItemRelation, ModelView):
    'Network Item Relation'
    __name__ = 'network.relation.all'

    @classmethod
    def table_query(cls):
        pool = Pool()
        Relation = pool.get('network.relation')
        Type = pool.get('network.relation.type')

        relation = Relation.__table__()
        type = Type.__table__()

        tables = {
            None: (relation, None)
            }
        reverse_tables = {
            None: (relation, None),
            'type': {
                None: (type, (relation.type == type.id) &
                    (type.reverse != None)),
                },
            }

        columns = []
        reverse_columns = []
        for name, field in Relation._fields.iteritems():
            if hasattr(field, 'get'):
                continue
            column, reverse_column = cls._get_column(tables, reverse_tables,
                name)
            columns.append(column)
            reverse_columns.append(reverse_column)

        def convert_from(table, tables):
            right, condition = tables[None]
            if table:
                table = table.join(right, condition=condition)
            else:
                table = right
            for k, sub_tables in tables.iteritems():
                if k is None:
                    continue
                table = convert_from(table, sub_tables)
            return table

        query = convert_from(None, tables).select(*columns)
        reverse_query = convert_from(None, reverse_tables).select(
            *reverse_columns)
        return Union(query, reverse_query, all_=True)

    @classmethod
    def _get_column(cls, tables, reverse_tables, name):
        table, _ = tables[None]
        reverse_table, _ = reverse_tables[None]
        if name == 'id':
            return As(table.id * 2, name), As(reverse_table.id * 2 + 1, name)
        elif name == 'from_':
            return table.from_, reverse_table.to.as_(name)
        elif name == 'to':
            return table.to, reverse_table.from_.as_(name)
        elif name == 'type':
            reverse_type, _ = reverse_tables[name][None]
            return table.type, reverse_type.reverse.as_(name)
        else:
            return Column(table, name), Column(reverse_table, name)

    @staticmethod
    def convert_instances(relations):
        "Converts network.relation.all instances to network.relation "
        pool = Pool()
        Relation = pool.get('network.relation')
        return Relation.browse([x.id // 2 for x in relations])

    @property
    def reverse_id(self):
        if self.id % 2:
            return self.id - 1
        else:
            return self.id + 1

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        Relation = pool.get('network.relation')
        relations = Relation.create(vlist)
        return cls.browse([r.id * 2 for r in relations])

    @classmethod
    def write(cls, all_records, values):
        pool = Pool()
        Relation = pool.get('network.relation')

        # Increase transaction counter
        Transaction().counter += 1

        # Clean local cache
        for record in all_records:
            for record_id in (record.id, record.reverse_id):
                local_cache = record._local_cache.get(record_id)
                if local_cache:
                    local_cache.clear()

        # Clean cursor cache
        for cache in Transaction().cursor.cache.itervalues():
            if cls.__name__ in cache:
                for record in all_records:
                    for record_id in (record.id, record.reverse_id):
                        if record_id in cache[cls.__name__]:
                            cache[cls.__name__][record_id].clear()

        reverse_values = values.copy()
        if 'from_' in values and 'to' in values:
            reverse_values['from_'], reverse_values['to'] = \
                reverse_values['to'], reverse_values['from_']
        elif 'from_' in values:
            reverse_values['to'] = reverse_values.pop('from_')
        elif 'to' in values:
            reverse_values['from_'] = reverse_values.pop('to')
        straight_relations = [r for r in all_records if not r.id % 2]
        reverse_relations = [r for r in all_records if r.id % 2]
        if straight_relations:
            Relation.write(cls.convert_instances(straight_relations),
                values)
        if reverse_relations:
            Relation.write(cls.convert_instances(reverse_relations),
                reverse_values)

    @classmethod
    def delete(cls, relations):
        pool = Pool()
        Relation = pool.get('network.relation')

        # Increase transaction counter
        Transaction().counter += 1

        # Clean cursor cache
        for cache in Transaction().cursor.cache.values():
            for cache in (cache, cache.get('_language_cache', {}).values()):
                if cls.__name__ in cache:
                    for record in relations:
                        for record_id in (record.id, record.reverse_id):
                            if record_id in cache[cls.__name__]:
                                del cache[cls.__name__][record_id]

        Relation.delete(cls.convert_instances(relations))
