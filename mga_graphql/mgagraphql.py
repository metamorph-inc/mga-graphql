import xml.etree.ElementTree as ET
import _winreg as winreg
import os
import sys
import udm

import collections
import functools


# Memoize taken from https://wiki.python.org/moin/PythonDecoratorLibrary#Memoize
class memoized(object):
    """Decorator. Caches a function's return value each time it is called.
    If called later with the same arguments, the cached value is returned
    (not reevaluated).
    """

    def __init__(self, func):
        self.func = func
        self.cache = {}

    def __call__(self, *args):
        if not isinstance(args, collections.Hashable):
            # un-cacheable. a list, for instance.
            # better to not cache than blow up.
            return self.func(*args)
        if args in self.cache:
            return self.cache[args]
        else:
            value = self.func(*args)
            self.cache[args] = value
            return value

    def __repr__(self):
        """Return the function's docstring."""
        return self.func.__doc__

    def __get__(self, obj, objtype):
        """Support instance methods."""
        return functools.partial(self.__call__, obj)


class MgaGraphQlSchemaConverter(object):
    TEMPLATE_CLASS = """# auto-generated by mga-graphql
from mga_graphql.mgaclasses import *
from graphene import String, Int, Field, Boolean, List
{imports}


class {classname}({baseclasses}):
    {attributes}
"""

    TEMPLATE_IMPORT = """from .{classname} import {classname}"""

    RELPATH_DSML_CLASSES = 'dsmlclasses'

    MGA_CLASSES = ['MgaObject', 'MgaFco',
                   'MgaModel', 'MgaAtom',
                   'MgaReference', 'MgaSet',
                   'MgaFolder', 'MgaConnection']

    def __init__(self, udm_xml=None):
        self.parse_metamodel(udm_xml)

    def build_class_file(self, classname, baseclasses, attributes):
        if baseclasses:
            imports = '\n'.join([self.TEMPLATE_IMPORT.format(classname=bc)
                                 for bc in baseclasses
                                 if bc not in self.MGA_CLASSES])
            list_baseclasses = ', '.join(baseclasses)
        else:
            imports = ''
            list_baseclasses = ''

        if attributes:
            code_attributes = '\n    '.join(['{name} = {type}()'.format(name=k,
                                                                        type=v)
                                             for k, v in attributes.iteritems()])
        else:
            code_attributes = 'pass'

        code_class = self.TEMPLATE_CLASS.format(classname=classname,
                                                baseclasses=list_baseclasses,
                                                attributes=code_attributes,
                                                imports=imports)
        print (code_class)
        print ('\n')

        path_classfile = os.path.join(self.RELPATH_DSML_CLASSES, classname + '.py')
        with open(path_classfile, 'w') as cf:
            cf.writelines(code_class)

    TEMPLATE_QUERY_FILE = """# auto-generated by mga-graphql
import graphene
from mga_graphql.mgaclasses import *
from dsmlclasses import *
import udm


def load_data(path_mga, path_udm_xml):
    uml_diagram = udm.uml_diagram()
    meta_dn = udm.SmartDataNetwork(uml_diagram)
    meta_dn.open(path_udm_xml.encode('utf-8'), b'')
    dn = udm.SmartDataNetwork(meta_dn.root)
    dn.open(path_mga.encode('utf-8'), b'')

    # Need to make our own data structure for now.
    models = {{}}
    root = dn.root

    def visit(obj):
        type = obj.type.name

        if type == 'Compound':
            model = Compound(id=obj.id,
                             name=obj.name)
        else:
            model = MgaObject(id=obj.id,
                              name=obj.name)

        models[str(obj.id)] = model

        child_ids = []
        for child in obj.children():
            child_ids.append(visit(child))

        if type == 'Compound':
            model.children = child_ids

        return obj.id

    visit(dn.root)

    return models


class Query(graphene.ObjectType):
    {objects}
    

def run_server(d_models):
    schema = graphene.Schema(query=Query)

    from flask import Flask, render_template
    from flask_graphql import GraphQLView

    app = Flask(__name__)
    app.debug = False

    app.add_url_rule('/graphql',
                     view_func=GraphQLView.as_view('graphql',
                                                   schema=schema,
                                                   graphiql=True,
                                                   context={{
                                                       'session': Query,
                                                       'data': d_models
                                                   }}))

    @app.route('/')
    def index():
        return "Go to /graphql"

    app.run()
"""

    def build_query_file_entry(self, l_classes):
        template_objects = """
    {lowercase} = graphene.Field({classname}, id=graphene.String(),)
    def resolve_{lowercase}(self, info, id):
        return info.context['data'][id]
    
    all_{lowercase} = graphene.List({classname}, )
    def resolve_all_{lowercase}(self, info):
        return [v for k, v in info.context['data'].iteritems()
                if isinstance(v, {classname})]        
"""

        code_schema = self.TEMPLATE_QUERY_FILE.format(objects='\n'
                                                      .join([template_objects.format(lowercase=c.lower(),
                                                                                     classname=c)
                                                             for c in l_classes]))
        print (code_schema)

        path_schemafile = os.path.join('schema.py')
        with open(path_schemafile, 'w') as cf:
            cf.writelines(code_schema)

    def parse_metamodel(self, udm_xml):
        tree = ET.parse(udm_xml)
        root = tree.getroot()

        # Build classes for everything
        path_dsml_classes = self.RELPATH_DSML_CLASSES
        # if os.path.exists(path_dsml_classes):
        #     os.remove(path_dsml_classes)
        # os.mkdir(path_dsml_classes)

        # Build class dict
        m_classes = {clazz.get('_id'): clazz.get('name') for clazz in root.iter('Class')}

        # Build class code files
        for clazz in root.iter('Class'):
            name_class = clazz.get('name')

            # Skip Mga classes (already included)
            if name_class in self.MGA_CLASSES:
                continue

            # Get baseclasses
            baseclass_names = []
            basetypes = clazz.get('baseTypes')
            if basetypes:
                baseclass_names = [m_classes[id] for id in basetypes.split(' ')
                                   if m_classes[id] not in self.MGA_CLASSES]

            # Also flag the MGA basetype
            baseclass_names.append('Mga' + clazz.attrib['stereotype'])

            m_attr = {}
            for attr in clazz.iter('Attribute'):
                name_attr = attr.get('name')
                type_attr = attr.get('type')
                if type_attr == 'Integer':
                    m_attr[name_attr] = 'Int'
                else:
                    m_attr[name_attr] = type_attr

            if not baseclass_names:
                baseclass_names = ['MgaObject']

            self.build_class_file(name_class, baseclass_names, m_attr)

        l_dsml_classes = [v for k, v in m_classes.iteritems()
                          if v not in self.MGA_CLASSES]

        # Build dsmlclasses/__init__.py
        code_init = '\n'.join(["from .{cname} import {cname}".format(cname=cname)
                               for cname in l_dsml_classes])
        with open(os.path.join('dsmlclasses', '__init__.py'), 'w') as init:
            init.writelines(code_init)

        # Build schema file
        self.build_query_file_entry(l_dsml_classes)

        if False:
            pass
            # for clazz in root.iter('Class'):
            #     id_class = clazz.get('_id')
            #     uri_class = self.NS_METAMODEL[id_class]
            #     g_meta.add((uri_class, RDF.type, self.NS_GME['class']))
            #     g_meta.add((uri_class, self.NS_GME['id'], Literal(id_class)))
            #     g_meta.add((uri_class, self.NS_GME['name'], Literal(clazz.get('name'))))
            #     g_meta.add((uri_class, self.NS_GME['isAbstract'], Literal(clazz.get('isAbstract') == 'true')))
            #
            #     basetypes = clazz.get('baseTypes')
            #     if basetypes:
            #         for basetype_id in basetypes.split(' '):
            #             g_meta.add((uri_class, self.NS_GME['baseType'], self.NS_METAMODEL[basetype_id]))
            #
            #     stereotype = clazz.get('stereotype')
            #     if stereotype == 'Connection':
            #         g_meta.add((uri_class, RDF.type, self.NS_GME['association']))
            #         self._assoc_class_names.add(clazz.get('name'))
            #
            #     elif stereotype == 'Reference':
            #         association_id = clazz.get('associationRoles')
            #
            #         if association_id:
            #             if association_id.find(' ') > 0:
            #                 association_id = association_id.split()[0]
            #
            #             # We need to get the corresponding association.
            #             association = tree.find('.//AssociationRole[@_id="{}"]/..'.format(association_id))
            #
            #             rolename = None
            #             association_roles = association.findall('AssociationRole')
            #             for ar in association_roles:
            #                 id_ar = ar.get('_id')
            #                 if id_ar != id_class:
            #                     rolename = ar.get('name')
            #
            #             if rolename:
            #                 self._reference_class_roles[clazz.get('name')] = rolename

            #
            # @staticmethod
            # def convert(fco, udm_xml=None):
            #     v = MgaGraphQlSchemaConverter(udm_xml=udm_xml)
            #     v.visit(fco)
            #     return v.g
            #
            # @memoized
            # def build_obj_uri(self, obj_id):
            #     return self.NS_MODEL['id_' + str(obj_id)]
            #
            # @memoized
            # def build_type_uri(self, type_name):
            #     return self.NS_METAMODEL[type_name]
            #
            # # Many attribute values are repeated, so it's worthwhile to memoize
            # @memoized
            # def val_to_literal(self, value):
            #     return Literal(value)
            #
            # # These attribute URIs get built frequently, so it's worthwhile to memoize
            # @memoized
            # def build_attr_uri(self, name_attr):
            #     return self.NS_METAMODEL[name_attr]
            #
            # @memoized
            # def build_connection_role_uris(self, name_class):
            #     uri_src_role = self.NS_METAMODEL['src' + name_class]
            #     uri_dst_role = self.NS_METAMODEL['dst' + name_class]
            #     return uri_src_role, uri_dst_role
            #
            # @staticmethod
            # def ancestors(o):
            #     while o:
            #         yield o
            #         o = o.parent

    def visit(self, obj):
        pass

        uri_obj = self.build_obj_uri(obj.id)
        obj_type_name = obj.type.name
        uri_type = self.build_type_uri(obj_type_name)

        self.g.add((uri_obj, RDF.type, uri_type))

        ancestor_chain = list([a.name for a in self.ancestors(obj)])
        ancestor_chain.reverse()
        self.g.add((uri_obj, self.NS_GME['path'],
                    Literal('.'.join(ancestor_chain))))

        if obj.is_subtype:
            self.g.add((uri_obj, RDF.type, self.URI_GME_SUBTYPE))
        if obj.is_instance:
            self.g.add((uri_obj, RDF.type, self.URI_GME_INSTANCE))
        if not obj.archetype == udm.null:
            arch_uri = self.build_obj_uri(obj.archetype.id)
            self.g.add((uri_obj, self.URI_ARCHETYPE, arch_uri))

        if obj_type_name in self._assoc_class_names:
            src_attr = getattr(obj, 'src' + obj_type_name)
            dst_attr = getattr(obj, 'dst' + obj_type_name)

            src_uri = self.build_obj_uri(src_attr.id)
            dst_uri = self.build_obj_uri(dst_attr.id)

            uri_src_role, uri_dst_role = self.build_connection_role_uris(obj_type_name)

            self.g.add((uri_obj, uri_src_role, src_uri))
            self.g.add((uri_obj, uri_dst_role, dst_uri))

        # Attributes
        if obj_type_name in self._class_attributes:
            for name_attr in self._class_attributes[obj_type_name]:
                val_attr = getattr(obj, name_attr)
                literal_attr = self.val_to_literal(val_attr)
                self.g.add((uri_obj, self.build_attr_uri(name_attr), literal_attr))

        # References
        if obj_type_name in self._reference_class_roles:
            rolename = self._reference_class_roles[obj_type_name]
            referent = getattr(obj, rolename)
            uri_referent = self.build_obj_uri(referent.id)

            self.g.add((uri_obj, self.NS_GME.references, uri_referent))

        literal_name = Literal(obj.name)
        self.g.add((uri_obj, self.URI_GME_NAME, literal_name))
        self.g.add((uri_obj, self.URI_METAMODEL_NAME, literal_name))

        if not obj.parent == udm.null:
            parent_uri = self.build_obj_uri(obj.parent.id)
            self.g.add((uri_obj, self.URI_GME_PARENT, parent_uri))

        for child in obj.children():
            self.visit(child)
