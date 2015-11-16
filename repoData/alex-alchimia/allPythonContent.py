__FILENAME__ = engine
from sqlalchemy.engine.base import Engine

from twisted.internet.threads import deferToThreadPool


class TwistedEngine(object):
    def __init__(self, pool, dialect, url, reactor=None, **kwargs):
        if reactor is None:
            raise TypeError("Must provide a reactor")

        self._engine = Engine(pool, dialect, url, **kwargs)
        self._reactor = reactor

    def _defer_to_thread(self, f, *args, **kwargs):
        tpool = self._reactor.getThreadPool()
        return deferToThreadPool(self._reactor, tpool, f, *args, **kwargs)

    @property
    def dialect(self):
        return self._engine.dialect

    @property
    def _has_events(self):
        return self._engine._has_events

    @property
    def _execution_options(self):
        return self._engine._execution_options

    def _should_log_info(self):
        return self._engine._should_log_info()

    def connect(self):
        d = self._defer_to_thread(self._engine.connect)
        d.addCallback(TwistedConnection, self)
        return d

    def execute(self, *args, **kwargs):
        d = self._defer_to_thread(self._engine.execute, *args, **kwargs)
        d.addCallback(TwistedResultProxy, self)
        return d

    def has_table(self, table_name, schema=None):
        return self._defer_to_thread(
            self._engine.has_table, table_name, schema)

    def table_names(self, schema=None, connection=None):
        if connection is not None:
            connection = connection._connection
        return self._defer_to_thread(
            self._engine.table_names, schema, connection)


class TwistedConnection(object):
    def __init__(self, connection, engine):
        self._connection = connection
        self._engine = engine

    def execute(self, *args, **kwargs):
        d = self._engine._defer_to_thread(
            self._connection.execute, *args, **kwargs)
        d.addCallback(TwistedResultProxy, self._engine)
        return d

    def close(self, *args, **kwargs):
        return self._engine._defer_to_thread(
            self._connection.close, *args, **kwargs)

    @property
    def closed(self):
        return self._connection.closed

    def begin(self, *args, **kwargs):
        d = self._engine._defer_to_thread(
            self._connection.begin, *args, **kwargs)
        d.addCallback(TwistedTransaction, self._engine)
        return d

    def in_transaction(self):
        return self._connection.in_transaction()


class TwistedTransaction(object):
    def __init__(self, transaction, engine):
        self._transaction = transaction
        self._engine = engine

    def commit(self):
        return self._engine._defer_to_thread(self._transaction.commit)

    def rollback(self):
        return self._engine._defer_to_thread(self._transaction.rollback)

    def close(self):
        return self._engine._defer_to_thread(self._transaction.close)


class TwistedResultProxy(object):
    def __init__(self, result_proxy, engine):
        self._result_proxy = result_proxy
        self._engine = engine

    def fetchone(self):
        return self._engine._defer_to_thread(self._result_proxy.fetchone)

    def fetchall(self):
        return self._engine._defer_to_thread(self._result_proxy.fetchall)

    def scalar(self):
        return self._engine._defer_to_thread(self._result_proxy.scalar)

    def first(self):
        return self._engine._defer_to_thread(self._result_proxy.first)

    def keys(self):
        return self._engine._defer_to_thread(self._result_proxy.keys)

    @property
    def returns_rows(self):
        return self._result_proxy.returns_rows

    @property
    def rowcount(self):
        return self._result_proxy.rowcount

    @property
    def inserted_primary_key(self):
        return self._result_proxy.inserted_primary_key

########NEW FILE########
__FILENAME__ = strategy
from sqlalchemy.engine.strategies import DefaultEngineStrategy

from alchimia.engine import TwistedEngine


TWISTED_STRATEGY = "_twisted"


class TwistedEngineStrategy(DefaultEngineStrategy):
    """
    An EngineStrategy for use with Twisted. Many of the Engine's methods will
    return Deferreds instead of results. See the documentation of
    ``TwistedEngine`` for more details.
    """

    name = TWISTED_STRATEGY
    engine_cls = TwistedEngine

########NEW FILE########
__FILENAME__ = conf
# -*- coding: utf-8 -*-
#
# alchimia documentation build configuration file, created by
# sphinx-quickstart on Fri Sep  6 11:45:41 2013.
#
# This file is execfile()d with the current directory set to its containing dir.
#
# Note that not all possible configuration values are present in this
# autogenerated file.
#
# All configuration values have a default; values that are commented out
# serve to show the default.

import sys, os

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#sys.path.insert(0, os.path.abspath('.'))

# -- General configuration -----------------------------------------------------

# If your documentation needs a minimal Sphinx version, state it here.
#needs_sphinx = '1.0'

# Add any Sphinx extension module names here, as strings. They can be extensions
# coming with Sphinx (named 'sphinx.ext.*') or your custom ones.
extensions = ['sphinx.ext.autodoc', 'sphinx.ext.doctest', 'sphinx.ext.intersphinx']

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# The suffix of source filenames.
source_suffix = '.rst'

# The encoding of source files.
#source_encoding = 'utf-8-sig'

# The master toctree document.
master_doc = 'index'

# General information about the project.
project = u'alchimia'
copyright = u'2013, Alex Gaynor and David Reid'

# The language for content autogenerated by Sphinx. Refer to documentation
# for a list of supported languages.
#language = None

# There are two options for replacing |today|: either, you set today to some
# non-false value, then it is used:
#today = ''
# Else, today_fmt is used as the format for a strftime call.
#today_fmt = '%B %d, %Y'

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
exclude_patterns = ['_build']

# The reST default role (used for this markup: `text`) to use for all documents.
#default_role = None

# If true, '()' will be appended to :func: etc. cross-reference text.
#add_function_parentheses = True

# If true, the current module name will be prepended to all description
# unit titles (such as .. function::).
#add_module_names = True

# If true, sectionauthor and moduleauthor directives will be shown in the
# output. They are ignored by default.
#show_authors = False

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = 'sphinx'

# A list of ignored prefixes for module index sorting.
#modindex_common_prefix = []


# -- Options for HTML output ---------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
html_theme = 'default'

# Theme options are theme-specific and customize the look and feel of a theme
# further.  For a list of options available for each theme, see the
# documentation.
#html_theme_options = {}

# Add any paths that contain custom themes here, relative to this directory.
#html_theme_path = []

# The name for this set of Sphinx documents.  If None, it defaults to
# "<project> v<release> documentation".
#html_title = None

# A shorter title for the navigation bar.  Default is the same as html_title.
#html_short_title = None

# The name of an image file (relative to this directory) to place at the top
# of the sidebar.
#html_logo = None

# The name of an image file (within the static path) to use as favicon of the
# docs.  This file should be a Windows icon file (.ico) being 16x16 or 32x32
# pixels large.
#html_favicon = None

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']

# If not '', a 'Last updated on:' timestamp is inserted at every page bottom,
# using the given strftime format.
#html_last_updated_fmt = '%b %d, %Y'

# If true, SmartyPants will be used to convert quotes and dashes to
# typographically correct entities.
#html_use_smartypants = True

# Custom sidebar templates, maps document names to template names.
#html_sidebars = {}

# Additional templates that should be rendered to pages, maps page names to
# template names.
#html_additional_pages = {}

# If false, no module index is generated.
#html_domain_indices = True

# If false, no index is generated.
#html_use_index = True

# If true, the index is split into individual pages for each letter.
#html_split_index = False

# If true, links to the reST sources are added to the pages.
#html_show_sourcelink = True

# If true, "Created using Sphinx" is shown in the HTML footer. Default is True.
#html_show_sphinx = True

# If true, "(C) Copyright ..." is shown in the HTML footer. Default is True.
#html_show_copyright = True

# If true, an OpenSearch description file will be output, and all pages will
# contain a <link> tag referring to it.  The value of this option must be the
# base URL from which the finished HTML is served.
#html_use_opensearch = ''

# This is the file name suffix for HTML files (e.g. ".xhtml").
#html_file_suffix = None

# Output file base name for HTML help builder.
htmlhelp_basename = 'alchimiadoc'


# -- Options for LaTeX output --------------------------------------------------

latex_elements = {
# The paper size ('letterpaper' or 'a4paper').
#'papersize': 'letterpaper',

# The font size ('10pt', '11pt' or '12pt').
#'pointsize': '10pt',

# Additional stuff for the LaTeX preamble.
#'preamble': '',
}

# Grouping the document tree into LaTeX files. List of tuples
# (source start file, target name, title, author, documentclass [howto/manual]).
latex_documents = [
  ('index', 'alchimia.tex', u'alchimia Documentation',
   u'Alex Gaynor and David Reid', 'manual'),
]

# The name of an image file (relative to this directory) to place at the top of
# the title page.
#latex_logo = None

# For "manual" documents, if this is true, then toplevel headings are parts,
# not chapters.
#latex_use_parts = False

# If true, show page references after internal links.
#latex_show_pagerefs = False

# If true, show URL addresses after external links.
#latex_show_urls = False

# Documents to append as an appendix to all manuals.
#latex_appendices = []

# If false, no module index is generated.
#latex_domain_indices = True


# -- Options for manual page output --------------------------------------------

# One entry per manual page. List of tuples
# (source start file, name, description, authors, manual section).
man_pages = [
    ('index', 'alchimia', u'alchimia Documentation',
     [u'Alex Gaynor and David Reid'], 1)
]

# If true, show URL addresses after external links.
#man_show_urls = False


# -- Options for Texinfo output ------------------------------------------------

# Grouping the document tree into Texinfo files. List of tuples
# (source start file, target name, title, author,
#  dir menu entry, description, category)
texinfo_documents = [
  ('index', 'alchimia', u'alchimia Documentation',
   u'Alex Gaynor and David Reid', 'alchimia', 'One line description of project.',
   'Miscellaneous'),
]

# Documents to append as an appendix to all manuals.
#texinfo_appendices = []

# If false, no module index is generated.
#texinfo_domain_indices = True

# How to display URL addresses: 'footnote', 'no', or 'inline'.
#texinfo_show_urls = 'footnote'


# Example configuration for intersphinx: refer to the Python standard library.
intersphinx_mapping = {
    'http://docs.python.org/': None,
    'sqlalchemy': ('http://docs.sqlalchemy.org/en/latest/', None),
}

########NEW FILE########
__FILENAME__ = tasks
from invoke import task, run


@task
def release(version):
    """
    Version should be a string like '0.4' or '1.0'
    """
    run('git tag -s "{}"'.format(version))
    run('python setup.py sdist bdist_wheel')
    run('twine upload -s dist/alchimia-{}*'.format(version))

########NEW FILE########
__FILENAME__ = doubles
from twisted.internet.interfaces import IReactorThreads
from twisted.python.failure import Failure

from zope.interface import implementer


@implementer(IReactorThreads)
class FakeThreadedReactor(object):
    def getThreadPool(self):
        return FakeThreadPool()

    def callFromThread(self, f, *args, **kwargs):
        return f(*args, **kwargs)


class FakeThreadPool(object):
    def callInThreadWithCallback(self, cb, f, *args, **kwargs):
        try:
            result = f(*args, **kwargs)
        except Exception as e:
            cb(False, Failure(e))
        else:
            cb(True, result)

########NEW FILE########
__FILENAME__ = test_engine
import sqlalchemy
from sqlalchemy.engine import RowProxy
from sqlalchemy.exc import StatementError
from sqlalchemy.schema import CreateTable

from twisted.trial import unittest

from alchimia import TWISTED_STRATEGY
from alchimia.engine import (
    TwistedEngine, TwistedConnection, TwistedTransaction,
)

from .doubles import FakeThreadedReactor


def create_engine():
    return sqlalchemy.create_engine(
        "sqlite://", strategy=TWISTED_STRATEGY, reactor=FakeThreadedReactor()
    )


class TestEngineCreation(object):
    def test_simple_create_engine(self):
        engine = sqlalchemy.create_engine(
            "sqlite://",
            strategy=TWISTED_STRATEGY,
            reactor=FakeThreadedReactor()
        )
        assert isinstance(engine, TwistedEngine)


class TestEngine(unittest.TestCase):
    def test_connect(self):
        engine = create_engine()
        d = engine.connect()
        connection = self.successResultOf(d)
        assert isinstance(connection, TwistedConnection)

    def test_execute(self):
        engine = create_engine()
        d = engine.execute("SELECT 42")
        result = self.successResultOf(d)
        d = result.scalar()
        assert self.successResultOf(d) == 42

    def test_table_names(self):
        engine = create_engine()
        d = engine.table_names()
        assert self.successResultOf(d) == []
        d = engine.execute("CREATE TABLE mytable (id int)")
        self.successResultOf(d)
        d = engine.table_names()
        assert self.successResultOf(d) == ['mytable']

    def test_table_names_with_connection(self):
        # There's no easy way to tell which connection was actually used, so
        # this test just provides coverage for the code path.
        engine = create_engine()
        conn = self.successResultOf(engine.connect())
        d = engine.table_names(connection=conn)
        assert self.successResultOf(d) == []
        d = conn.execute("CREATE TABLE mytable (id int)")
        self.successResultOf(d)
        d = engine.table_names(connection=conn)
        assert self.successResultOf(d) == ['mytable']

    def test_has_table(self):
        engine = create_engine()
        d = engine.has_table('mytable')
        assert self.successResultOf(d) is False
        d = engine.execute("CREATE TABLE mytable (id int)")
        self.successResultOf(d)
        d = engine.has_table('mytable')
        assert self.successResultOf(d) is True


class TestConnection(unittest.TestCase):
    def get_connection(self):
        engine = create_engine()
        return self.successResultOf(engine.connect())

    def execute_fetchall(self, conn, query_obj):
        result = self.successResultOf(conn.execute(query_obj))
        return self.successResultOf(result.fetchall())

    def test_execute(self):
        conn = self.get_connection()
        d = conn.execute("SELECT 42")
        result = self.successResultOf(d)
        d = result.scalar()
        assert self.successResultOf(d) == 42

    def test_close(self):
        conn = self.get_connection()
        assert not conn.closed
        result = self.successResultOf(conn.execute("SELECT 42"))
        assert self.successResultOf(result.scalar()) == 42

        self.successResultOf(conn.close())
        assert conn.closed
        failure = self.failureResultOf(
            conn.execute("SELECT 42"), StatementError)
        assert "This Connection is closed" in str(failure)

    def test_in_transaction(self):
        conn = self.get_connection()
        assert not conn.in_transaction()

        transaction = self.successResultOf(conn.begin())
        assert isinstance(transaction, TwistedTransaction)
        assert conn.in_transaction()

        self.successResultOf(transaction.close())
        assert not conn.in_transaction()

    def test_nested_transaction(self):
        conn = self.get_connection()
        assert not conn.in_transaction()

        trx1 = self.successResultOf(conn.begin())
        assert conn.in_transaction()
        trx2 = self.successResultOf(conn.begin())
        assert conn.in_transaction()

        self.successResultOf(trx2.close())
        assert conn.in_transaction()
        self.successResultOf(trx1.close())
        assert not conn.in_transaction()

    def test_transaction_commit(self):
        metadata = sqlalchemy.MetaData()
        tbl = sqlalchemy.Table(
            'mytable', metadata,
            sqlalchemy.Column("id", sqlalchemy.Integer(), primary_key=True),
            sqlalchemy.Column("num", sqlalchemy.Integer()),
        )

        conn = self.get_connection()
        self.successResultOf(conn.execute(CreateTable(tbl)))
        trx = self.successResultOf(conn.begin())
        self.successResultOf(conn.execute(tbl.insert().values(num=42)))
        rows = self.execute_fetchall(conn, tbl.select())
        assert len(rows) == 1

        self.successResultOf(trx.commit())
        rows = self.execute_fetchall(conn, tbl.select())
        assert len(rows) == 1

    def test_transaction_rollback(self):
        metadata = sqlalchemy.MetaData()
        tbl = sqlalchemy.Table(
            'mytable', metadata,
            sqlalchemy.Column("id", sqlalchemy.Integer(), primary_key=True),
            sqlalchemy.Column("num", sqlalchemy.Integer()),
        )

        conn = self.get_connection()
        self.successResultOf(conn.execute(CreateTable(tbl)))
        trx = self.successResultOf(conn.begin())
        self.successResultOf(conn.execute(tbl.insert().values(num=42)))
        rows = self.execute_fetchall(conn, tbl.select())
        assert len(rows) == 1

        self.successResultOf(trx.rollback())
        rows = self.execute_fetchall(conn, tbl.select())
        assert len(rows) == 0


class TestResultProxy(unittest.TestCase):
    def create_default_table(self):
        engine = create_engine()
        d = engine.execute("CREATE TABLE testtable (id int)")
        self.successResultOf(d)
        return engine

    def test_fetchone(self):
        engine = create_engine()
        d = engine.execute("SELECT 42")
        result = self.successResultOf(d)
        d = result.fetchone()
        row = self.successResultOf(d)
        assert isinstance(row, RowProxy)
        assert row[0] == 42

    def test_fetchall(self):
        engine = create_engine()
        d = engine.execute("SELECT 10")
        result = self.successResultOf(d)
        d = result.fetchall()
        rows = self.successResultOf(d)
        assert len(rows) == 1
        assert rows[0][0] == 10

    def test_first(self):
        engine = self.create_default_table()
        d = engine.execute("INSERT INTO testtable (id) VALUES (2)")
        self.successResultOf(d)
        d = engine.execute("INSERT INTO testtable (id) VALUES (3)")
        self.successResultOf(d)
        d = engine.execute("SELECT * FROM testtable ORDER BY id ASC")
        result = self.successResultOf(d)
        d = result.first()
        row = self.successResultOf(d)
        assert len(row) == 1
        assert row[0] == 2

    def test_keys(self):
        engine = create_engine()
        d = engine.execute("CREATE TABLE testtable (id int, name varchar)")
        self.successResultOf(d)
        d = engine.execute("SELECT * FROM testtable")
        result = self.successResultOf(d)
        d = result.keys()
        keys = self.successResultOf(d)
        assert len(keys) == 2
        assert 'id' in keys
        assert 'name' in keys

    def test_returns_rows(self):
        engine = self.create_default_table()
        d = engine.execute("INSERT INTO testtable values (2)")
        result = self.successResultOf(d)
        assert not result.returns_rows
        d = engine.execute("SELECT * FROM testtable")
        result = self.successResultOf(d)
        assert result.returns_rows

    def test_rowcount(self):
        engine = self.create_default_table()
        d = engine.execute("INSERT INTO testtable VALUES (1)")
        self.successResultOf(d)
        d = engine.execute("INSERT INTO testtable VALUES (2)")
        self.successResultOf(d)
        d = engine.execute("INSERT INTO testtable VALUES (3)")
        self.successResultOf(d)
        d = engine.execute("UPDATE testtable SET id = 7 WHERE id < 3")
        result = self.successResultOf(d)
        assert result.rowcount == 2
        d = engine.execute("DELETE from testtable")
        result = self.successResultOf(d)
        assert result.rowcount == 3

    def test_inserted_primary_key(self):
        metadata = sqlalchemy.MetaData()
        tbl = sqlalchemy.Table(
            'testtable', metadata,
            sqlalchemy.Column("id", sqlalchemy.Integer(), primary_key=True),
        )
        engine = self.create_default_table()
        d = engine.execute(tbl.insert().values())
        result = self.successResultOf(d)
        assert result.inserted_primary_key == [1]

########NEW FILE########