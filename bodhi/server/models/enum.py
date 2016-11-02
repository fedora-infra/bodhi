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

# http://techspot.zzzeek.org/2011/01/14/the-enum-recipe

import re

from sqlalchemy.types import SchemaType, TypeDecorator, Enum


class EnumSymbol(object):
    """Define a fixed symbol tied to a parent class."""

    def __init__(self, cls_, name, value, description):
        self.cls_ = cls_
        self.name = name
        self.value = value
        self.description = description

    def __reduce__(self):
        """Allow unpickling to return the symbol
        linked to the DeclEnum class."""
        return getattr, (self.cls_, self.name)

    def __iter__(self):
        return iter([self.value, self.description])

    def __repr__(self):
        return "<%s>" % self.name

    def __unicode__(self):
        return unicode(self.description)

    def __json__(self, request=None):
        return self.description


class EnumMeta(type):
    """Generate new DeclEnum classes."""

    def __init__(cls, classname, bases, dict_):
        cls._reg = reg = cls._reg.copy()
        for k, v in dict_.items():
            if isinstance(v, tuple):
                sym = reg[v[0]] = EnumSymbol(cls, k, *v)
                setattr(cls, k, sym)
        return type.__init__(cls, classname, bases, dict_)

    def __iter__(cls):
        return iter(cls._reg.values())


class DeclEnum(object):
    """Declarative enumeration."""

    __metaclass__ = EnumMeta
    _reg = {}

    @classmethod
    def from_string(cls, value):
        try:
            return cls._reg[value]
        except KeyError:
            raise ValueError("Invalid value for %r: %r" % (cls.__name__, value))

    @classmethod
    def values(cls):
        return cls._reg.keys()

    @classmethod
    def db_type(cls):
        return DeclEnumType(cls)


class DeclEnumType(SchemaType, TypeDecorator):
    def __init__(self, enum):
        self.enum = enum
        self.impl = Enum(
            *enum.values(),
            name="ck%s" % re.sub('([A-Z])', lambda m: "_" + m.group(1).lower(), enum.__name__))

    def _set_table(self, table, column):
        self.impl._set_table(table, column)

    def copy(self):
        return DeclEnumType(self.enum)

    def process_bind_param(self, value, dialect):
        """
        :type value:   bodhi.server.models.enum.EnumSymbol
        :type dialect: sqlalchemy.engine.default.DefaultDialect
        """
        if value is None:
            return None
        return value.value

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return self.enum.from_string(value.strip())

    def create(self, bind=None, checkfirst=False):
        """Issue CREATE ddl for this type, if applicable."""
        super(DeclEnumType, self).create(bind, checkfirst)
        t = self.dialect_impl(bind.dialect)
        if t.impl.__class__ is not self.__class__ and isinstance(t, SchemaType):
            t.impl.create(bind=bind, checkfirst=checkfirst)

    def drop(self, bind=None, checkfirst=False):
        """Issue DROP ddl for this type, if applicable."""
        super(DeclEnumType, self).drop(bind, checkfirst)
        t = self.dialect_impl(bind.dialect)
        if t.impl.__class__ is not self.__class__ and isinstance(t, SchemaType):
            t.impl.drop(bind=bind, checkfirst=checkfirst)
