# Copyright © 2011-2019 Red Hat, Inc. and others.
#
# This file is part of Bodhi.
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
"""Bodhi's base models."""

from datetime import datetime
import inspect
import sys

from sqlalchemy import Column, Integer, or_
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import class_mapper
from sqlalchemy.orm.properties import RelationshipProperty

from bodhi.server import Session
from bodhi.server.models import EnumSymbol


class BodhiBase(object):
    """
    Base class for the SQLAlchemy model base class.

    Attributes:
        __exclude_columns__ (tuple): A list of columns to exclude from JSON
        __include_extras__ (tuple): A list of methods or attrs to include in JSON
        __get_by__ (tuple): A list of columns that :meth:`.get` will query.
        id (int): An integer id that serves as the default primary key.
        query (sqlalchemy.orm.query.Query): a class property which produces a
            Query object against the class and the current Session when called.
    """

    __exclude_columns__ = ('id',)
    __include_extras__ = tuple()
    __get_by__ = ()

    id = Column(Integer, primary_key=True)

    query = Session.query_property()

    @classmethod
    def get(cls, id):
        """
        Return an instance of the model by using its __get_by__ attribute with id.

        Args:
            id (object): An attribute to look up the model by.
        Returns:
            BodhiBase or None: An instance of the model that matches the id, or ``None`` if no match
            was found.
        """
        return cls.query.filter(or_(
            getattr(cls, col) == id for col in cls.__get_by__
        )).first()

    def __getitem__(self, key):
        """
        Define a dictionary like interface for the models.

        Args:
            key (string): The name of an attribute you wish to retrieve from the model.
        Returns:
            object: The value of the attribute represented by key.
        """
        return getattr(self, key)

    def __repr__(self):
        """
        Return a string representation of this model.

        Returns:
            str: A string representation of this model.
        """
        return '<{0} {1}>'.format(self.__class__.__name__, self.__json__())

    def __json__(self, request=None, exclude=None, include=None):
        """
        Return a JSON representation of this model.

        Args:
            request (pyramid.request.Request or None): The current web request, or None.
            exclude (iterable or None): An iterable of strings naming the attributes to exclude from
                the JSON representation of the model. If None (the default), the class's
                __exclude_columns__ attribute will be used.
            include (iterable or None): An iterable of strings naming the extra attributes to
                include in the JSON representation of the model. If None (the default), the class's
                __include_extras__ attribute will be used.
        Returns:
            dict: A dict representation of the model suitable for serialization as JSON.
        """
        return self._to_json(self, request=request, exclude=exclude, include=include)

    @classmethod
    def _to_json(cls, obj, seen=None, request=None, exclude=None, include=None):
        """
        Return a JSON representation of obj.

        Args:
            obj (BodhiBase): The model to serialize.
            seen (list or None): A list of attributes we have already serialized. Used by this
                method to keep track of its state, as it uses recursion.
            request (pyramid.request.Request or None): The current web request, or None.
            exclude (iterable or None): An iterable of strings naming the attributes to exclude from
                the JSON representation of the model. If None (the default), the class's
                __exclude_columns__ attribute will be used.
            include (iterable or None): An iterable of strings naming the extra attributes to
                include in the JSON representation of the model. If None (the default), the class's
                __include_extras__ attribute will be used.
        Returns:
            dict: A dict representation of the model suitable for serialization.
        """
        if not seen:
            seen = []
        if not obj:
            return

        if exclude is None:
            exclude = getattr(obj, '__exclude_columns__', [])
        properties = list(class_mapper(type(obj)).iterate_properties)
        rels = [p.key for p in properties if isinstance(p, RelationshipProperty)]
        attrs = [p.key for p in properties if p.key not in rels]
        d = dict([(attr, getattr(obj, attr)) for attr in attrs
                  if attr not in exclude and not attr.startswith('_')])

        if include is None:
            include = getattr(obj, '__include_extras__', [])

        for name in include:
            attribute = getattr(obj, name)
            if callable(attribute):
                attribute = attribute(request)
            d[name] = attribute

        for attr in rels:
            if attr in exclude:
                continue
            target = getattr(type(obj), attr).property.mapper.class_
            if target in seen:
                continue
            d[attr] = cls._expand(obj, getattr(obj, attr), seen, request)

        for key, value in d.items():
            if isinstance(value, datetime):
                d[key] = value.strftime('%Y-%m-%d %H:%M:%S')
            if isinstance(value, EnumSymbol):
                d[key] = str(value)

        return d

    @classmethod
    def _expand(cls, obj, relation, seen, req):
        """
        Return the to_json or id of a sqlalchemy relationship.

        Args:
            obj (BodhiBase): The object we are trying to describe a relationship on.
            relation (object): A relationship attribute on obj we are trying to learn about.
            seen (list): A list of objects we have already recursed over.
            req (pyramid.request.Request): The current request.
        Returns:
            object: The to_json() or the id of a sqlalchemy relationship.
        """
        if hasattr(relation, 'all'):
            relation = relation.all()
        if hasattr(relation, '__iter__'):
            return [cls._expand(obj, item, seen, req) for item in relation]
        if type(relation) not in seen:
            return cls._to_json(relation, seen + [type(obj)], req)
        else:
            return relation.id

    @classmethod
    def grid_columns(cls):
        """
        Return the column names for the model, except for the excluded ones.

        Returns:
            list: A list of column names, with excluded ones removed.
        """
        columns = []
        exclude = getattr(cls, '__exclude_columns__', [])
        for col in cls.__table__.columns:
            if col.name in exclude:
                continue
            columns.append(col.name)
        return columns

    @classmethod
    def find_polymorphic_child(cls, identity):
        """
        Find a child of a polymorphic base class.

        For example, given the base Package class and the 'rpm' identity, this
        class method should return the RpmPackage class.

        This is accomplished by iterating over all classes in scope.
        Limiting that to only those which are an extension of the given base
        class.  Among those, return the one whose polymorphic_identity matches
        the value given.  If none are found, then raise a NameError.

        Args:
            identity (EnumSymbol): An instance of EnumSymbol used to identify the child.
        Returns:
            BodhiBase: The type-specific child class.
        Raises:
            KeyError: If this class is not polymorphic.
            NameError: If no child class is found for the given identity.
            TypeError: If identity is not an EnumSymbol.
        """
        if not isinstance(identity, EnumSymbol):
            raise TypeError("%r is not an instance of EnumSymbol" % identity)

        if 'polymorphic_on' not in getattr(cls, '__mapper_args__', {}):
            raise KeyError("%r is not a polymorphic model." % cls)

        classes = inspect.getmembers(sys.modules['bodhi.server.models'], inspect.isclass)
        children = (c for n, c in classes if issubclass(c, cls))
        for child in children:
            candidate = child.__mapper_args__.get('polymorphic_identity')
            if candidate is identity:
                return child

        error = "Found no child of %r with identity %r"
        raise NameError(error % (cls, identity))


Base = declarative_base(cls=BodhiBase)
metadata = Base.metadata
