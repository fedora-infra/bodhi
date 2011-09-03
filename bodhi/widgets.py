from tw2.jqplugins.jqgrid import SQLAjqGridWidget
from bodhi.models import Release, Bug, Update, Package, Build, Comment, User

class BodhiGrid(SQLAjqGridWidget):
    id = 'bodhi_grid'
    excluded_columns = ['id']
    datetime_format = "%x %X"
    entity = None
    show_relations = False

    prmFilter = {'stringResult': True, 'searchOnEnter': False}

    options = {
        'pager': id + '_pager',
        'url': '/grid',
        'rowNum':15,
        'rowList':[15,150, 1500],
        'viewrecords':True,
        'imgpath': 'scripts/jqGrid/themes/green/images',
        'shrinkToFit': True,
        'height': 'auto',
    }

    def post_define(self, *args, **kw):
        if self.entity:
            self.options = self.options.copy()
            self.options['url'] = '/grid/%s' % self.entity.__name__
            self.id = 'bodhi_%s_grid' % self.entity.__name__

class UpdateGrid(BodhiGrid):
    entity = Update

class ReleaseGrid(BodhiGrid):
    entity = Release

class BugGrid(BodhiGrid):
    entity = Bug

class BuildGrid(BodhiGrid):
    entity = Build

class UserGrid(BodhiGrid):
    entity = User

class CommentGrid(BodhiGrid):
    entity = Comment
    excluded_columns = ['update']

class PackageGrid(BodhiGrid):
    entity = Package

widgets = {
    'Update': UpdateGrid,
    'Build': BuildGrid,
    'Release': ReleaseGrid,
    'User': UserGrid,
    'Bug': BugGrid,
    'Package': PackageGrid,
    'Comment': CommentGrid,
    }
