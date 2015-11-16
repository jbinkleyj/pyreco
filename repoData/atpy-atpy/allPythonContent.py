__FILENAME__ = asciitables
from __future__ import print_function, division

import os

from .decorators import auto_download_to_file, auto_decompress_to_fileobj

# Thanks to Moritz Guenther for providing the initial code used to create this file

from astropy.io import ascii


def read_cds(self, filename, **kwargs):
    '''
    Read data from a CDS table (also called Machine Readable Tables) file

        Required Arguments:

            *filename*: [ string ]
                The file to read the table from

        Keyword Arguments are passed to astropy.io.ascii
    '''
    read_ascii(self, filename, Reader=ascii.Cds, **kwargs)


def read_daophot(self, filename, **kwargs):
    '''
    Read data from a DAOphot table

        Required Arguments:

            *filename*: [ string ]
                The file to read the table from

        Keyword Arguments are passed to astropy.io.ascii
    '''
    read_ascii(self, filename, Reader=ascii.Daophot, **kwargs)

def read_latex(self, filename, **kwargs):
    '''
    Read data from a Latex table

        Required Arguments:

            *filename*: [ string ]
                The file to read the table from

        Keyword Arguments are passed to astropy.io.ascii
    '''
    read_ascii(self, filename, Reader=ascii.Latex, **kwargs)


def write_latex(self, filename, **kwargs):
    '''
    Write data to a Latex table

        Required Arguments:

            *filename*: [ string ]
                The file to write the table to

        Keyword Arguments are passed to astropy.io.ascii
    '''
    write_ascii(self, filename, Writer=ascii.Latex, **kwargs)



def read_rdb(self, filename, **kwargs):
    '''
    Read data from an RDB table

        Required Arguments:

            *filename*: [ string ]
                The file to read the table from

        Keyword Arguments are passed to astropy.io.ascii
    '''
    read_ascii(self, filename, Reader=ascii.Rdb, **kwargs)


def write_rdb(self, filename, **kwargs):
    '''
    Write data to an RDB table

        Required Arguments:

            *filename*: [ string ]
                The file to write the table to

        Keyword Arguments are passed to astropy.io.ascii
    '''
    write_ascii(self, filename, Writer=ascii.Rdb, **kwargs)


# astropy.io.ascii can handle file objects
@auto_download_to_file
@auto_decompress_to_fileobj
def read_ascii(self, filename, **kwargs):
    '''
    Read a table from an ASCII file using astropy.io.ascii

    Optional Keyword Arguments:

        Reader - Reader class (default= BasicReader )
        Inputter - Inputter class
        delimiter - column delimiter string
        comment - regular expression defining a comment line in table
        quotechar - one-character string to quote fields containing special characters
        header_start - line index for the header line not counting comment lines
        data_start - line index for the start of data not counting comment lines
        data_end - line index for the end of data (can be negative to count from end)
        converters - dict of converters
        data_Splitter - Splitter class to split data columns
        header_Splitter - Splitter class to split header columns
        names - list of names corresponding to each data column
        include_names - list of names to include in output (default=None selects all names)
        exclude_names - list of names to exlude from output (applied after include_names)

    Note that the Outputter argument is not passed to astropy.io.ascii.

    See the astropy.io.ascii documentation at http://docs.astropy.org/en/latest/io/ascii/index.html for more details.
    '''

    self.reset()

    if 'Outputter' in kwargs:
        kwargs.pop('Outputter')
    table = ascii.read(filename, **kwargs)

    for name in table.colnames:
        self.add_column(name, table[name])


def write_ascii(self, filename, **kwargs):
    '''
    Read a table from an ASCII file using astropy.io.ascii

    Optional Keyword Arguments:

        Writer - Writer class (default= Basic)
        delimiter - column delimiter string
        write_comment - string defining a comment line in table
        quotechar - one-character string to quote fields containing special characters
        formats - dict of format specifiers or formatting functions
        names - list of names corresponding to each data column
        include_names - list of names to include in output (default=None selects all names)
        exclude_names - list of names to exlude from output (applied after include_names)

    See the astropy.io.ascii documentation at http://docs.astropy.org/en/latest/io/ascii/index.html for more details.
    '''

    if 'overwrite' in kwargs:
        overwrite = kwargs.pop('overwrite')
    else:
        overwrite = False

    if type(filename) is str and os.path.exists(filename):
        if overwrite:
            os.remove(filename)
        else:
            raise Exception("File exists: %s" % filename)

    ascii.write(self.data, filename, **kwargs)

########NEW FILE########
__FILENAME__ = basetable
from __future__ import print_function, division

# Need to depracate fits_read, etc.

import string
import warnings
from copy import deepcopy

import numpy as np
import numpy.ma as ma

from .exceptions import VectorException
from .structhelper import append_field, drop_fields
from .odict import odict
from . import registry
from .masked import __masked__

default_format = {}
default_format[None.__class__] = '16.9e'
default_format[np.bool_] = '1i'
default_format[np.int8] = '3i'
default_format[np.uint8] = '3i'
default_format[np.int16] = '5i'
default_format[np.uint16] = '5i'
default_format[np.int32] = '12i'
default_format[np.uint32] = '12i'
default_format[np.int64] = '22i'
default_format[np.uint64] = '23i'
default_format[np.float32] = '16.8e'
default_format[np.float64] = '25.17e'
default_format[np.str] = 's'
default_format[np.string_] = 's'
default_format[np.uint8] = 's'
default_format[str] = 's'
default_format[np.unicode_] = 's'


class ColumnHeader(object):

    def __init__(self, dtype, unit=None, description=None, null=None, format=None):
        self.__dict__['dtype'] = dtype
        self.unit = unit
        self.description = description
        self.__dict__['null'] = null
        self.format = format

    def __setattr__(self, attribute, value):
        if attribute in ['unit', 'description', 'format']:
            self.__dict__[attribute] = value
        elif attribute in ['null', 'dtype']:
            raise Exception("Cannot change %s through the columns object" % attribute)
        else:
            raise AttributeError(attribute)

    def __repr__(self):
        s = "type=%s" % str(self.dtype)
        if self.unit:
            s += ", unit=%s" % str(self.unit)
        if self.null:
            s += ", null=%s" % str(self.null)
        if self.description:
            s += ", description=%s" % self.description
        return s

    def __eq__(self, other):
        if self.dtype != other.dtype:
            return False
        if self.unit != other.unit:
            return False
        if self.description != other.description:
            return False
        if self.null != other.null:
            if np.isnan(self.null):
                if not np.isnan(other.null):
                    return False
            else:
                return False
        if self.format != other.format:
            return False
        return True

    def __ne__(self, other):
        return not self.__eq__(other)


class Table(object):

    def fits_read(self, *args, **kwargs):
        warnings.warn("WARNING: fits_read is deprecated; use read instead")
        kwargs['type'] = 'fits'
        self.read(*args, **kwargs)

    def vo_read(self, *args, **kwargs):
        warnings.warn("WARNING: vo_read is deprecated; use read instead")
        kwargs['type'] = 'vo'
        self.read(*args, **kwargs)

    def sql_read(self, *args, **kwargs):
        warnings.warn("WARNING: sql_read is deprecated; use read instead")
        kwargs['type'] = 'sql'
        self.read(*args, **kwargs)

    def ipac_read(self, *args, **kwargs):
        warnings.warn("WARNING: ipac_read is deprecated; use read instead")
        kwargs['type'] = 'ipac'
        self.read(*args, **kwargs)

    def fits_write(self, *args, **kwargs):
        warnings.warn("WARNING: fits_write is deprecated; use write instead")
        kwargs['type'] = 'fits'
        self.write(*args, **kwargs)

    def vo_write(self, *args, **kwargs):
        warnings.warn("WARNING: vo_write is deprecated; use write instead")
        kwargs['type'] = 'vo'
        self.write(*args, **kwargs)

    def sql_write(self, *args, **kwargs):
        warnings.warn("WARNING: sql_write is deprecated; use write instead")
        kwargs['type'] = 'sql'
        self.write(*args, **kwargs)

    def ipac_write(self, *args, **kwargs):
        warnings.warn("WARNING: ipac_write is deprecated; use write instead")
        kwargs['type'] = 'ipac'
        self.write(*args, **kwargs)

    def __repr__(self):
        s = "<Table name='%s' rows=%i fields=%i>" % (self.table_name, self.__len__(), len(self.columns))
        return s

    def __init__(self, *args, **kwargs):
        '''
        Create a table instance

        Optional Arguments:

            If no arguments are given, and empty table is created

            If one or more arguments are given they are passed to the
            Table.read() method.

        Optional Keyword Arguments (independent of table type):

            *name*: [ string ]
                The table name

            *masked*: [ True | False ]
                Whether to use masked arrays. WARNING: this feature is
                experimental and will only work correctly with the svn version
                of numpy post-revision 8025. Note that this overrides the
                default set by atpy.set_masked_default.
        '''

        self.reset()

        if 'name' in kwargs:
            self.table_name = kwargs.pop('name')
        else:
            self.table_name = None

        if 'masked' in kwargs:
            self._masked = kwargs.pop('masked')
        else:
            self._masked = __masked__

        if len(args) + len(kwargs) > 0:
            self.read(*args, **kwargs)

        return

    def read(self, *args, **kwargs):
        '''
        Read in a table from a file/database.

        Optional Keyword Arguments (independent of table type):

            *verbose*: [ True | False ]
                Whether to print out warnings when reading (default is True)

            *type*: [ string ]
                The read method attempts to automatically guess the
                file/database format based on the arguments supplied. The type
                can be overridden by setting this argument.
        '''

        if 'verbose' in kwargs:
            verbose = kwargs['verbose']
        else:
            verbose = True

        if 'type' in kwargs:
            table_type = kwargs.pop('type').lower()
        elif isinstance(args[0], basestring):
            table_type = registry._determine_type(args[0], verbose)
        else:
            raise Exception('Could not determine table type')

        original_filters = warnings.filters[:]

        if verbose:
            warnings.simplefilter("always")
        else:
            warnings.simplefilter("ignore")

        try:

            if verbose:
                warnings.simplefilter("always")
            else:
                warnings.simplefilter("ignore")

            if table_type in registry._readers:
                registry._readers[table_type](self, *args, **kwargs)
            else:
                raise Exception("Unknown table type: " + table_type)

        finally:
            warnings.filters = original_filters

        return

    def write(self, *args, **kwargs):
        '''
        Write out a table to a file/database.

        Optional Keyword Arguments (independent of table type):

            *verbose*: [ True | False ]
                Whether to print out warnings when writing (default is True)

            *type*: [ string ]
                The read method attempts to automatically guess the
                file/database format based on the arguments supplied. The type
                can be overridden by setting this argument.
        '''

        if 'verbose' in kwargs:
            verbose = kwargs.pop('verbose')
        else:
            verbose = True

        if 'type' in kwargs:
            table_type = kwargs.pop('type').lower()
        elif type(args[0]) == str:
            table_type = registry._determine_type(args[0], verbose)
        else:
            raise Exception('Could not determine table type')

        original_filters = warnings.filters[:]

        if verbose:
            warnings.simplefilter("always")
        else:
            warnings.simplefilter("ignore")

        try:

            if table_type in registry._writers:
                registry._writers[table_type](self, *args, **kwargs)
            else:
                raise Exception("Unknown table type: " + table_type)

        finally:
            warnings.filters = original_filters

        return

    def __getattr__(self, attribute):

        if attribute == 'names':
            return self.__dict__['data'].dtype.names
        elif attribute == 'units':
            print("WARNING: Table.units is deprecated - use Table.columns to access this information")
            return dict([(name, self.columns[name].unit) for name in self.names])
        elif attribute == 'types':
            print("WARNING: Table.types is deprecated - use Table.columns to access this information")
            return dict([(name, self.columns[name].type) for name in self.names])
        elif attribute == 'nulls':
            print("WARNING: Table.nulls is deprecated - use Table.columns to access this information")
            return dict([(name, self.columns[name].null) for name in self.names])
        elif attribute == 'formats':
            print("WARNING: Table.formats is deprecated - use Table.columns to access this information")
            return dict([(name, self.columns[name].format) for name in self.names])
        elif attribute == 'shape':
            return (len(self.data), len(self.names))
        else:
            try:
                return self.__dict__['data'][attribute]
            except:
                raise AttributeError(attribute)

    def __getitem__(self, item):
        return self.data[item]

    def __setitem__(self, item, value):
        if 'data' in self.__dict__:
            if isinstance(self.data, np.ndarray):
                if item in self.data.dtype.names:
                    self.data[item] = value
                    return
        raise ValueError("Column %s does not exist" % item)

    def keys(self):
        return self.data.dtype.names

    def append(self, table):
        for colname in self.columns:
            if self.columns.keys != table.columns.keys:
                raise Exception("Column names do not match")
            if self.columns[colname].dtype.type != table.columns[colname].dtype.type:
                raise Exception("Column types do not match")
        self.data = np.hstack((self.data, table.data))

    def __setattr__(self, attribute, value):
        if 'data' in self.__dict__:
            if isinstance(self.data, np.ndarray):
                if attribute in self.data.dtype.names:
                    self.data[attribute] = value
                    return
        self.__dict__[attribute] = value

    def __len__(self):
        if len(self.columns) == 0:
            return 0
        else:
            return len(self.data)

    def reset(self):
        '''
        Empty the table
        '''
        self.keywords = odict()
        self.comments = []
        self.columns = odict()
        self.data = None
        self._primary_key = None
        return

    def _raise_vector_columns(self):
        names = []
        for name in self.names:
            if self.data[name].ndim > 1:
                names.append(name)
        if names:
            names = string.join(names, ", ")
            raise VectorException(names)
        return

    def _setup_table(self, n_rows, dtype, units=None, descriptions=None, formats=None, nulls=None):

        if self._masked:
            self.data = ma.zeros(n_rows, dtype=dtype)
        else:
            self.data = np.zeros(n_rows, dtype=dtype)

        for i in range(len(dtype)):

            if units is None:
                unit = None
            else:
                unit = units[i]

            if descriptions is None:
                description = None
            else:
                description = descriptions[i]

            if formats is None or format in ['e', 'g', 'f']:
                if dtype[i].subdtype:
                    format = default_format[dtype[i].subdtype[0].type]
                else:
                    format = default_format[dtype[i].type]
            else:
                format = formats[i]

            # Backward compatibility with tuple-style format
            if type(format) in [tuple, list]:
                format = string.join([str(x) for x in format], "")

            if format == 's':
                format = '%is' % self.data.itemsize

            if nulls is None:
                null = None
            else:
                null = nulls[i]

            column = ColumnHeader(dtype[i], unit=unit, description=description, null=null, format=format)

            self.columns[dtype.names[i]] = column

    def add_empty_column(self, name, dtype, unit='', null='', \
        description='', format=None, column_header=None, shape=None, before=None, after=None, \
        position=None):
        '''
        Add an empty column to the table. This only works if there
        are already existing columns in the table.

        Required Arguments:

            *name*: [ string ]
                The name of the column to add

            *dtype*: [ numpy type ]
                Numpy type of the column. This is the equivalent to
                the dtype= argument in numpy.array

        Optional Keyword Arguments:

            *unit*: [ string ]
                The unit of the values in the column

            *null*: [ same type as data ]
                The values corresponding to 'null', if not NaN

            *description*: [ string ]
                A description of the content of the column

            *format*: [ string ]
                The format to use for ASCII printing

            *column_header*: [ ColumnHeader ]
                The metadata from an existing column to copy over. Metadata
                includes the unit, null value, description, format, and dtype.
                For example, to create a column 'b' with identical metadata to
                column 'a' in table 't', use:

                    >>> t.add_column('b', column_header=t.columns[a])

            *shape*: [ tuple ]
                Tuple describing the shape of the empty column that is to be
                added. If a one element tuple is specified, it is the number
                of rows. If a two element tuple is specified, the first is the
                number of rows, and the second is the width of the column.

            *before*: [ string ]
                Column before which the new column should be inserted

            *after*: [ string ]
                Column after which the new column should be inserted

            *position*: [ integer ]
                Position at which the new column should be inserted (0 = first
                column)
        '''
        if shape:
            data = np.zeros(shape, dtype=dtype)
        elif self.__len__() > 0:
            data = np.zeros(self.__len__(), dtype=dtype)
        else:
            raise Exception("Table is empty, you need to use the shape= argument to specify the dimensions of the first column")

        self.add_column(name, data, unit=unit, null=null, \
            description=description, format=format, column_header=column_header, before=before, \
            after=after, position=position)

    def add_column(self, name, data, unit='', null='', description='', \
        format=None, dtype=None, column_header=None, before=None, after=None, position=None, mask=None, fill=None):
        '''
        Add a column to the table

        Required Arguments:

            *name*: [ string ]
                The name of the column to add

            *data*: [ numpy array ]
                The column data

        Optional Keyword Arguments:

            *unit*: [ string ]
                The unit of the values in the column

            *null*: [ same type as data ]
                The values corresponding to 'null', if not NaN

            *description*: [ string ]
                A description of the content of the column

            *format*: [ string ]
                The format to use for ASCII printing

            *dtype*: [ numpy type ]
                Numpy type to convert the data to. This is the equivalent to
                the dtype= argument in numpy.array

            *column_header*: [ ColumnHeader ]
                The metadata from an existing column to copy over. Metadata
                includes the unit, null value, description, format, and dtype.
                For example, to create a column 'b' with identical metadata to
                column 'a' in table 't', use:

                    >>> t.add_column('b', column_header=t.columns[a])

            *before*: [ string ]
                Column before which the new column should be inserted

            *after*: [ string ]
                Column after which the new column should be inserted

            *position*: [ integer ]
                Position at which the new column should be inserted (0 = first
                column)

            *mask*: [ numpy array ]
                An array of booleans, with the same dimensions as the data,
                indicating whether or not to mask values.

            *fill*: [ value ]
                If masked arrays are used, this value is used as the fill
                value in the numpy masked array.
        '''

        if column_header is not None:

            if dtype is not None:
                warnings.warn("dtype= argument overriden by column_header=")
            dtype = column_header.dtype

            if unit != '':
                warnings.warn("unit= argument overriden by column_header=")
            unit = column_header.unit

            if null != '':
                warnings.warn("null= argument overriden by column_header=")
            null = column_header.null

            if description != '':
                warnings.warn("description= argument overriden by column_header=")
            description = column_header.description

            if format is not None:
                warnings.warn("format= argument overriden by column_header=")
            format = column_header.format

        if self._masked:
            if null:
                warnings.warn("null= argument can only be used if Table does not use masked arrays (ignored)")
            data = ma.array(data, dtype=dtype, mask=mask, fill_value=fill)
        else:
            if np.any(mask):
                warnings.warn("mask= argument can only be used if Table uses masked arrays (ignored)")
            data = np.array(data, dtype=dtype)

        dtype = data.dtype

        if dtype.type == np.object_:

            if len(data) == 0:
                longest = 0
            else:
                longest = len(max(data, key=len))

            if self._masked:
                data = ma.array(data, dtype='|%iS' % longest)
            else:
                data = np.array(data, dtype='|%iS' % longest)

            dtype = data.dtype

        if data.ndim > 1:
            newdtype = (name, data.dtype, (data.shape[1],))
        else:
            newdtype = (name, data.dtype)

        if before:
            try:
                position = list(self.names).index(before)
            except:
                raise Exception("Column %s does not exist" % before)
        elif after:
            try:
                position = list(self.names).index(after) + 1
            except:
                raise Exception("Column %s does not exist" % before)

        if len(self.columns) > 0:
            self.data = append_field(self.data, data, dtype=newdtype, position=position, masked=self._masked)
        else:
            if self._masked:
                self.data = ma.array(zip(data), dtype=[newdtype], mask=zip(data.mask), fill_value=data.fill_value)
            else:
                self.data = np.array(zip(data), dtype=[newdtype])

        if not format or format in ['e', 'g', 'f']:
            format = default_format[dtype.type]

        # Backward compatibility with tuple-style format
        if type(format) in [tuple, list]:
            format = string.join([str(x) for x in format], "")

        if format == 's':
            format = '%is' % data.itemsize

        column = ColumnHeader(dtype, unit=unit, description=description, null=null, format=format)

        if not np.equal(position, None):
            self.columns.insert(position, name, column)
        else:
            self.columns[name] = column

        return

    def remove_column(self, remove_name):
        print("WARNING: remove_column is deprecated - use remove_columns instead")
        self.remove_columns([remove_name])
        return

    def remove_columns(self, remove_names):
        '''
        Remove several columns from the table

        Required Argument:

            *remove_names*: [ list of strings ]
                A list containing the names of the columns to remove
        '''

        if type(remove_names) == str:
            remove_names = [remove_names]

        for remove_name in remove_names:
            self.columns.pop(remove_name)

        self.data = drop_fields(self.data, remove_names, masked=self._masked)

        # Remove primary key if needed
        if self._primary_key in remove_names:
            self._primary_key = None

        return

    def keep_columns(self, keep_names):
        '''
        Keep only specific columns in the table (remove the others)

        Required Argument:

            *keep_names*: [ list of strings ]
                A list containing the names of the columns to keep.
                All other columns will be removed.
        '''

        if type(keep_names) == str:
            keep_names = [keep_names]

        remove_names = list(set(self.names) - set(keep_names))

        if len(remove_names) == len(self.names):
            raise Exception("No columns to keep")

        self.remove_columns(remove_names)

        return

    def rename_column(self, old_name, new_name):
        '''
        Rename a column from the table

        Require Arguments:

            *old_name*: [ string ]
                The current name of the column.

            *new_name*: [ string ]
                The new name for the column
        '''

        if new_name in self.names:
            raise Exception("Column " + new_name + " already exists")

        if not old_name in self.names:
            raise Exception("Column " + old_name + " not found")

        # tuple.index was only introduced in Python 2.6, so need to use list()
        pos = list(self.names).index(old_name)
        self.data.dtype.names = self.names[:pos] + (new_name, ) + self.names[pos + 1:]

        if self._masked:
            self.data.mask.dtype.names = self.data.dtype.names[:]

        self.columns.rename(old_name, new_name)

        # Update primary key if needed
        if self._primary_key == old_name:
            self._primary_key = new_name

        return

    def describe(self):
        '''
        Prints a description of the table
        '''

        if self.data is None:
            print("Table is empty")
            return

        if self.table_name:
            print("Table : " + self.table_name)
        else:
            print("Table has no name")

        # Find maximum column widths
        len_name_max, len_unit_max, len_datatype_max, \
            len_formats_max = 4, 4, 4, 6

        for name in self.names:
            len_name_max = max(len(name), len_name_max)
            len_unit_max = max(len(str(self.columns[name].unit)), len_unit_max)
            len_datatype_max = max(len(str(self.columns[name].dtype)), \
                len_datatype_max)
            len_formats_max = max(len(self.columns[name].format), len_formats_max)

        # Print out table

        format = "| %" + str(len_name_max) + \
               "s | %" + str(len_unit_max) + \
               "s | %" + str(len_datatype_max) + \
               "s | %" + str(len_formats_max) + "s |"

        len_tot = len_name_max + len_unit_max + len_datatype_max + \
            len_formats_max + 13

        print("-" * len_tot)
        print(format % ("Name", "Unit", "Type", "Format"))
        print("-" * len_tot)

        for name in self.names:
            print(format % (name, str(self.columns[name].unit), \
                str(self.columns[name].dtype), self.columns[name].format))

        print("-" * len_tot)

        return

    def sort(self, keys):
        '''
        Sort the table according to one or more keys. This operates
        on the existing table (and does not return a new table).

        Required arguments:

            *keys*: [ string | list of strings ]
                The key(s) to order by
        '''
        if not type(keys) == list:
            keys = [keys]
        self.data.sort(order=keys)

    def row(self, row_number, python_types=False):
        '''
        Returns a single row

        Required arguments:

            *row_number*: [ integer ]
                The row number (the first row is 0)

        Optional Keyword Arguments:

            *python_types*: [ True | False ]
                Whether to return the row elements with python (True)
                or numpy (False) types.
        '''

        if python_types:
            return list(self.data[row_number].tolist())
        else:
            return self.data[row_number]

    def rows(self, row_ids):
        '''
        Select specific rows from the table and return a new table instance

        Required Argument:

            *row_ids*: [ list | np.int array ]
                A python list or numpy array specifying which rows to select,
                and in what order.

        Returns:

            A new table instance, containing only the rows selected
        '''
        return self.where(np.array(row_ids, dtype=int))

    def where(self, mask):
        '''
        Select matching rows from the table and return a new table instance

        Required Argument:

            *mask*: [ np.bool array ]
                A boolean array with the same length as the table.

        Returns:

            A new table instance, containing only the rows selected
        '''

        new_table = self.__class__()

        new_table.table_name = deepcopy(self.table_name)

        new_table.columns = deepcopy(self.columns)
        new_table.keywords = deepcopy(self.keywords)
        new_table.comments = deepcopy(self.comments)

        new_table.data = self.data[mask]

        return new_table

    def add_comment(self, comment):
        '''
        Add a comment to the table

        Required Argument:

            *comment*: [ string ]
                The comment to add to the table
        '''

        self.comments.append(comment.strip())
        return

    def add_keyword(self, key, value):
        '''
        Add a keyword/value pair to the table

        Required Arguments:

            *key*: [ string ]
                The name of the keyword

            *value*: [ string | float | integer | bool ]
                The value of the keyword
        '''

        if type(value) == str:
            value = value.strip()
        self.keywords[key.strip()] = value
        return

    def set_primary_key(self, key):
        '''
        Set the name of the table column that should be used as a unique
        identifier for the record. This is the same as primary keys in SQL
        databases. A primary column cannot contain NULLs and must contain only
        unique quantities.

        Required Arguments:

            *key*: [ string ]
                The column to use as a primary key
        '''

        if not key in self.names:
            raise Exception("No such column: %s" % key)
        else:
            if self.columns[key].null != '':
                if np.any(self.data[key] == self.columns[key].null):
                    raise Exception("Primary key column cannot contain null values")
            elif len(np.unique(self.data[key])) != len(self.data[key]):
                raise Exception("Primary key column cannot contain duplicate values")
            else:
                self._primary_key = key

        return


class TableSet(object):

    def fits_read(self, *args, **kwargs):
        warnings.warn("WARNING: fits_read is deprecated; use read instead")
        kwargs['type'] = 'fits'
        self.read(*args, **kwargs)

    def vo_read(self, *args, **kwargs):
        warnings.warn("WARNING: vo_read is deprecated; use read instead")
        kwargs['type'] = 'vo'
        self.read(*args, **kwargs)

    def sql_read(self, *args, **kwargs):
        warnings.warn("WARNING: sql_read is deprecated; use read instead")
        kwargs['type'] = 'sql'
        self.read(*args, **kwargs)

    def ipac_read(self, *args, **kwargs):
        warnings.warn("WARNING: ipac_read is deprecated; use read instead")
        kwargs['type'] = 'ipac'
        self.read(*args, **kwargs)

    def fits_write(self, *args, **kwargs):
        warnings.warn("WARNING: fits_write is deprecated; use write instead")
        kwargs['type'] = 'fits'
        self.write(*args, **kwargs)

    def vo_write(self, *args, **kwargs):
        warnings.warn("WARNING: vo_write is deprecated; use write instead")
        kwargs['type'] = 'vo'
        self.write(*args, **kwargs)

    def sql_write(self, *args, **kwargs):
        warnings.warn("WARNING: sql_write is deprecated; use write instead")
        kwargs['type'] = 'sql'
        self.write(*args, **kwargs)

    def ipac_write(self, *args, **kwargs):
        warnings.warn("WARNING: ipac_write is deprecated; use write instead")
        kwargs['type'] = 'ipac'
        self.write(*args, **kwargs)

    def reset(self):
        '''
        Empty the table set
        '''
        self.tables = odict()
        self.keywords = {}
        self.comments = []
        return

    def __init__(self, *args, **kwargs):
        '''
        Create a table set instance

        Optional Arguments:

            If no arguments are given, an empty table set will be created.

            If one of the arguments is a list or a Table instance, then only
            this argument will be used.

            If one or more arguments are present, they are passed to the read
            method

        Optional Keyword Arguments (independent of table type):

            *masked*: [ True | False ]
                Whether to use masked arrays. WARNING: this feature is
                experimental and will only work correctly with the svn version
                of numpy post-revision 8025. Note that this overrides the
                default set by atpy.set_masked_default.


        '''

        self.reset()

        if len(args) == 1:

            arg = args[0]

            if type(arg) == list:
                for table in arg:
                    self.append(table)
                return

            elif isinstance(arg, TableSet):
                for table in arg.tables:
                    self.append(table)
                return

        # Pass arguments to read
        if len(args) + len(kwargs) > 0:
            self.read(*args, **kwargs)

        return

    def read(self, *args, **kwargs):
        '''
        Read in a table set from a file/database.

        Optional Keyword Arguments (independent of table type):

            *verbose*: [ True | False ]
                Whether to print out warnings when reading (default is True)

            *type*: [ string ]
                The read method attempts to automatically guess the
                file/database format based on the arguments supplied. The type
                can be overridden by setting this argument.
        '''

        if 'verbose' in kwargs:
            verbose = kwargs['verbose']
        else:
            verbose = True

        if 'type' in kwargs:
            table_type = kwargs.pop('type').lower()
        elif type(args[0]) == str:
            table_type = registry._determine_type(args[0], verbose)
        else:
            raise Exception('Could not determine table type')

        original_filters = warnings.filters[:]

        if verbose:
            warnings.simplefilter("always")
        else:
            warnings.simplefilter("ignore")

        try:

            if verbose:
                warnings.simplefilter("always")
            else:
                warnings.simplefilter("ignore")

            if table_type in registry._set_readers:
                registry._set_readers[table_type](self, *args, **kwargs)
            else:
                raise Exception("Unknown table type: " + table_type)

        finally:
            warnings.filters = original_filters

        return

    def write(self, *args, **kwargs):
        '''
        Write out a table set to a file/database.

        Optional Keyword Arguments (independent of table type):

            *verbose*: [ True | False ]
                Whether to print out warnings when writing (default is True)

            *type*: [ string ]
                The read method attempts to automatically guess the
                file/database format based on the arguments supplied. The type
                can be overridden by setting this argument.
        '''

        if 'verbose' in kwargs:
            verbose = kwargs.pop('verbose')
        else:
            verbose = True

        if 'type' in kwargs:
            table_type = kwargs.pop('type').lower()
        elif type(args[0]) == str:
            table_type = registry._determine_type(args[0], verbose)
        else:
            raise Exception('Could not determine table type')

        original_filters = warnings.filters[:]

        if verbose:
            warnings.simplefilter("always")
        else:
            warnings.simplefilter("ignore")

        try:

            if table_type in registry._set_writers:
                registry._set_writers[table_type](self, *args, **kwargs)
            else:
                raise Exception("Unknown table type: " + table_type)

        finally:
            warnings.filters = original_filters

        return

    def __getitem__(self, item):
        return self.tables[item]

    def __getattr__(self, attribute):

        for table in self.tables:
            if attribute == self.tables[table].table_name:
                return self.tables[table]

        raise AttributeError(attribute)

    def append(self, table):
        '''
        Append a table to the table set

        Required Arguments:

            *table*: [ a table instance ]
                This can be a table of any type, which will be converted
                to a table of the same type as the parent set (e.g. adding
                a single VOTable to a FITSTableSet will convert the VOTable
                to a FITSTable inside the set)
        '''

        table_key = table.table_name

        if table_key in self.tables:
            for i in range(1, 10001):
                if not "%s.%05i" % (table_key, i) in self.tables:
                    table_key = "%s.%05i" % (table_key, i)
                    warnings.warn("There is already a table named %s in the TableSet. Renaming to %s" % (table.table_name, table_key))
                    break
        elif table_key is None:
            for i in range(1, 10001):
                if not "Untitled.%05i" % i in self.tables:
                    table_key = "Untitled.%05i" % i
                    warnings.warn("Table has no name. Setting to %s" % table_key)
                    break

        self.tables[table_key] = table
        return

    def describe(self):
        '''
        Describe all the tables in the set
        '''
        for table in self.tables:
            table.describe()
        return

    def add_comment(self, comment):
        '''
        Add a comment to the table set

        Required Argument:

            *comment*: [ string ]
                The comment to add to the table
        '''

        self.comments.append(comment.strip())
        return

    def add_keyword(self, key, value):
        '''
        Add a keyword/value pair to the table set

        Required Arguments:

            *key*: [ string ]
                The name of the keyword

            *value*: [ string | float | integer | bool ]
                The value of the keyword
        '''

        if type(value) == str:
            value = value.strip()
        self.keywords[key.strip()] = value
        return

########NEW FILE########
__FILENAME__ = decorator
from __future__ import print_function

##########################     LICENCE     ###############################

# Copyright (c) 2005-2012, Michele Simionato
# All rights reserved.

# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:

#   Redistributions of source code must retain the above copyright 
#   notice, this list of conditions and the following disclaimer.
#   Redistributions in bytecode form must reproduce the above copyright
#   notice, this list of conditions and the following disclaimer in
#   the documentation and/or other materials provided with the
#   distribution. 

# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# HOLDERS OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS
# OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR
# TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE
# USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH
# DAMAGE.

"""
Decorator module, see http://pypi.python.org/pypi/decorator
for the documentation.
"""

__version__ = '3.4.0'

__all__ = ["decorator", "FunctionMaker", "contextmanager"]

import sys, re, inspect
if sys.version >= '3':
    from inspect import getfullargspec
    def get_init(cls):
        return cls.__init__
else:
    class getfullargspec(object):
        "A quick and dirty replacement for getfullargspec for Python 2.X"
        def __init__(self, f):
            self.args, self.varargs, self.varkw, self.defaults = \
                inspect.getargspec(f)
            self.kwonlyargs = []
            self.kwonlydefaults = None
        def __iter__(self):
            yield self.args
            yield self.varargs
            yield self.varkw
            yield self.defaults
    def get_init(cls):
        return cls.__init__.__func__

DEF = re.compile('\s*def\s*([_\w][_\w\d]*)\s*\(')

# basic functionality
class FunctionMaker(object):
    """
    An object with the ability to create functions with a given signature.
    It has attributes name, doc, module, signature, defaults, dict and
    methods update and make.
    """
    def __init__(self, func=None, name=None, signature=None,
                 defaults=None, doc=None, module=None, funcdict=None):
        self.shortsignature = signature
        if func:
            # func can be a class or a callable, but not an instance method
            self.name = func.__name__
            if self.name == '<lambda>': # small hack for lambda functions
                self.name = '_lambda_' 
            self.doc = func.__doc__
            self.module = func.__module__
            if inspect.isfunction(func):
                argspec = getfullargspec(func)
                self.annotations = getattr(func, '__annotations__', {})
                for a in ('args', 'varargs', 'varkw', 'defaults', 'kwonlyargs',
                          'kwonlydefaults'):
                    setattr(self, a, getattr(argspec, a))
                for i, arg in enumerate(self.args):
                    setattr(self, 'arg%d' % i, arg)
                if sys.version < '3': # easy way
                    self.shortsignature = self.signature = \
                        inspect.formatargspec(
                        formatvalue=lambda val: "", *argspec)[1:-1]
                else: # Python 3 way
                    allargs = list(self.args)
                    allshortargs = list(self.args)
                    if self.varargs:
                        allargs.append('*' + self.varargs)
                        allshortargs.append('*' + self.varargs)
                    elif self.kwonlyargs:
                        allargs.append('*') # single star syntax
                    for a in self.kwonlyargs:
                        allargs.append('%s=None' % a)
                        allshortargs.append('%s=%s' % (a, a))
                    if self.varkw:
                        allargs.append('**' + self.varkw)
                        allshortargs.append('**' + self.varkw)
                    self.signature = ', '.join(allargs)
                    self.shortsignature = ', '.join(allshortargs)
                self.dict = func.__dict__.copy()
        # func=None happens when decorating a caller
        if name:
            self.name = name
        if signature is not None:
            self.signature = signature
        if defaults:
            self.defaults = defaults
        if doc:
            self.doc = doc
        if module:
            self.module = module
        if funcdict:
            self.dict = funcdict
        # check existence required attributes
        assert hasattr(self, 'name')
        if not hasattr(self, 'signature'):
            raise TypeError('You are decorating a non function: %s' % func)

    def update(self, func, **kw):
        "Update the signature of func with the data in self"
        func.__name__ = self.name
        func.__doc__ = getattr(self, 'doc', None)
        func.__dict__ = getattr(self, 'dict', {})
        func.__defaults__ = getattr(self, 'defaults', ())
        func.__kwdefaults__ = getattr(self, 'kwonlydefaults', None)
        func.__annotations__ = getattr(self, 'annotations', None)
        callermodule = sys._getframe(3).f_globals.get('__name__', '?')
        func.__module__ = getattr(self, 'module', callermodule)
        func.__dict__.update(kw)

    def make(self, src_templ, evaldict=None, addsource=False, **attrs):
        "Make a new function from a given template and update the signature"
        src = src_templ % vars(self) # expand name and signature
        evaldict = evaldict or {}
        mo = DEF.match(src)
        if mo is None:
            raise SyntaxError('not a valid function template\n%s' % src)
        name = mo.group(1) # extract the function name
        names = set([name] + [arg.strip(' *') for arg in 
                             self.shortsignature.split(',')])
        for n in names:
            if n in ('_func_', '_call_'):
                raise NameError('%s is overridden in\n%s' % (n, src))
        if not src.endswith('\n'): # add a newline just for safety
            src += '\n' # this is needed in old versions of Python
        try:
            code = compile(src, '<string>', 'single')
            # print >> sys.stderr, 'Compiling %s' % src
            exec(code, evaldict)
        except:
            print('Error in generated code:', file=sys.stderr)
            print(src, file=sys.stderr)
            raise
        func = evaldict[name]
        if addsource:
            attrs['__source__'] = src
        self.update(func, **attrs)
        return func

    @classmethod
    def create(cls, obj, body, evaldict, defaults=None,
               doc=None, module=None, addsource=True, **attrs):
        """
        Create a function from the strings name, signature and body.
        evaldict is the evaluation dictionary. If addsource is true an attribute
        __source__ is added to the result. The attributes attrs are added,
        if any.
        """
        if isinstance(obj, str): # "name(signature)"
            name, rest = obj.strip().split('(', 1)
            signature = rest[:-1] #strip a right parens            
            func = None
        else: # a function
            name = None
            signature = None
            func = obj
        self = cls(func, name, signature, defaults, doc, module)
        ibody = '\n'.join('    ' + line for line in body.splitlines())
        return self.make('def %(name)s(%(signature)s):\n' + ibody, 
                        evaldict, addsource, **attrs)
  
def decorator(caller, func=None):
    """
    decorator(caller) converts a caller function into a decorator;
    decorator(caller, func) decorates a function using a caller.
    """
    if func is not None: # returns a decorated function
        evaldict = func.__globals__.copy()
        evaldict['_call_'] = caller
        evaldict['_func_'] = func
        return FunctionMaker.create(
            func, "return _call_(_func_, %(shortsignature)s)",
            evaldict, undecorated=func, __wrapped__=func)
    else: # returns a decorator
        if inspect.isclass(caller):
            name = caller.__name__.lower()
            callerfunc = get_init(caller)
            doc = 'decorator(%s) converts functions/generators into ' \
                'factories of %s objects' % (caller.__name__, caller.__name__)
            fun = getfullargspec(callerfunc).args[1] # second arg
        elif inspect.isfunction(caller):
            name = '_lambda_' if caller.__name__ == '<lambda>' \
                else caller.__name__
            callerfunc = caller
            doc = caller.__doc__
            fun = getfullargspec(callerfunc).args[0] # first arg
        else: # assume caller is an object with a __call__ method
            name = caller.__class__.__name__.lower()
            callerfunc = caller.__call__.__func__
            doc = caller.__call__.__doc__
            fun = getfullargspec(callerfunc).args[1] # second arg
        evaldict = callerfunc.__globals__.copy()
        evaldict['_call_'] = caller
        evaldict['decorator'] = decorator
        return FunctionMaker.create(
            '%s(%s)' % (name, fun), 
            'return decorator(_call_, %s)' % fun,
            evaldict, undecorated=caller, __wrapped__=caller,
            doc=doc, module=caller.__module__)

######################### contextmanager ########################

def __call__(self, func):
    'Context manager decorator'
    return FunctionMaker.create(
        func, "with _self_: return _func_(%(shortsignature)s)",
        dict(_self_=self, _func_=func), __wrapped__=func)

try: # Python >= 3.2

    from contextlib import _GeneratorContextManager 
    ContextManager = type(
        'ContextManager', (_GeneratorContextManager,), dict(__call__=__call__))

except ImportError: # Python >= 2.5

    from contextlib import GeneratorContextManager
    def __init__(self, f, *a, **k):
        return GeneratorContextManager.__init__(self, f(*a, **k))
    ContextManager = type(
        'ContextManager', (GeneratorContextManager,), 
        dict(__call__=__call__, __init__=__init__))
    
contextmanager = decorator(ContextManager)

########NEW FILE########
__FILENAME__ = decorators
from __future__ import print_function, division

import sys

if sys.version_info[0] > 2:
    from urllib.request import Request, urlopen
else:
    from urllib2 import Request, urlopen

import tempfile
import gzip
import bz2

from .decorator import decorator


def auto_download_to_file(f):
    return decorator(_auto_download_to_file, f)


def _auto_download_to_file(read, table, filename, *args, **kwargs):

    if isinstance(filename, basestring):

        # Check whether filename is in fact a URL
        for protocol in ['http', 'ftp']:

            if filename.lower().startswith('%s://' % protocol):

                # Retrieve file
                req = Request(filename)
                response = urlopen(req)
                result = response.read()

                # Write it out to a temporary file
                output = tempfile.NamedTemporaryFile()
                output.write(result)
                output.flush()

                # Call read method
                return read(table, output.name, *args, **kwargs)

    # Otherwise just proceed as usual
    return read(table, filename, *args, **kwargs)


def auto_decompress_to_fileobj(f):
    return decorator(_auto_decompress_to_fileobj, f)


def _auto_decompress_to_fileobj(read, table, filename, *args, **kwargs):

    if isinstance(filename, basestring):

        # Read in first few characters from file to determine compression
        header = open(filename, 'rb').read(4)

        if header[:2] == '\x1f\x8b':  # gzip compression
            return read(table, gzip.GzipFile(filename), *args, **kwargs)
        elif header[:3] == 'BZh':  # bzip compression
            return read(table, bz2.BZ2File(filename), *args, **kwargs)
        else:
            return read(table, filename, *args, **kwargs)

    return read(table, filename, *args, **kwargs)


def auto_fileobj_to_file(f):
    return decorator(_auto_fileobj_to_file, f)


def _auto_fileobj_to_file(read, table, filename, *args, **kwargs):

    if hasattr(filename, 'read'):  # is a file object

        # Write it out to a temporary file
        output = tempfile.NamedTemporaryFile()
        output.write(filename.read())
        output.flush()

        # Update filename
        filename = output.name

    return read(table, filename, *args, **kwargs)

########NEW FILE########
__FILENAME__ = exceptions
from __future__ import print_function, division

class ExistingTableException(Exception):

    def __init__(self):
        pass

    def __str__(self):
        return "Table already exists - use overwrite to replace existing table"


class TableException(Exception):

    def __init__(self, tables, arg):
        self.tables = tables
        self.arg = arg

    def __str__(self):

        table_list = ""
        for table in self.tables:

            if type(table) == int:
                table_list += "    " + self.arg + \
                    "=%i : %s\n" % (table, self.tables[table])
            elif type(table) == str:
                table_list += "    " + self.arg + \
                    "=%s\n" % table
            else:
                raise Exception("Unexpected table index type: %s" %
                                                            str(type(table)))

        message = "There is more than one table in the requested file. " + \
            "Please specify the table desired with the " + self.arg + \
            "= argument. The available tables are:\n\n" + table_list

        return message


class VectorException(Exception):

    def __init__(self, value):
        self.value = value

    def __str__(self):
        return "This table contains vector columns:\n\n" + \
        self.value + "\n\n" + \
        "but the output format selected does not. Remove these " + \
        "columns using the remove_columns() method and try again."

########NEW FILE########
__FILENAME__ = fitstable
from __future__ import print_function, division

import os

import numpy as np
from astropy.io import fits

from .exceptions import TableException
from .helpers import smart_dtype, smart_mask
from .decorators import auto_download_to_file, auto_fileobj_to_file


standard_keys = ['XTENSION', 'NAXIS', 'NAXIS1', 'NAXIS2', 'TFIELDS', \
    'PCOUNT', 'GCOUNT', 'BITPIX', 'EXTNAME']

# Define type conversion dictionary
type_dict = {}
type_dict[np.bool_] = "L"
type_dict[np.int8] = "B"
type_dict[np.uint8] = "B"
type_dict[np.int16] = "I"
type_dict[np.uint16] = "I"
type_dict[np.int32] = "J"
type_dict[np.uint32] = "J"
type_dict[np.int64] = "K"
type_dict[np.uint64] = "K"
type_dict[np.float32] = "E"
type_dict[np.float64] = "D"
type_dict[np.str] = "A"
type_dict[np.string_] = "A"
type_dict[str] = "A"


def _list_tables(filename):
    hdulist = fits.open(filename)
    tables = {}
    for i, hdu in enumerate(hdulist[1:]):
        if hdu.header['XTENSION'] in ['BINTABLE', 'ASCIITABLE', 'TABLE']:
            tables[i + 1] = hdu.name
    hdulist.close()
    return tables


# PyFITS can handle compression, so no decompression detection
@auto_download_to_file
@auto_fileobj_to_file
def read(self, filename, hdu=None, memmap=False, verbose=True):
    '''
    Read a table from a FITS file

    Required Arguments:

        *filename*: [ string ]
            The FITS file to read the table from

    Optional Keyword Arguments:

        *hdu*: [ integer ]
            The HDU to read from the FITS file (this is only required
            if there are more than one table in the FITS file)

        *memmap*: [ bool ]
            Whether PyFITS should use memory mapping
    '''

    self.reset()

    # If no hdu is requested, check that there is only one table
    if not hdu:
        tables = _list_tables(filename)
        if len(tables) == 0:
            raise Exception("No tables in file")
        elif len(tables) == 1:
            hdu = tables.keys()[0]
        else:
            raise TableException(tables, 'hdu')

    hdulist = fits.open(filename, memmap=memmap)
    hdu = hdulist[hdu]

    table = hdu.data
    header = hdu.header
    columns = hdu.columns

    # Construct dtype for table

    dtype = []

    for i in range(len(hdu.data.dtype)):

        name = hdu.data.dtype.names[i]
        type = hdu.data.dtype[name]
        if type.subdtype:
            type, shape = type.subdtype
        else:
            shape = ()

        # Get actual FITS format and zero-point
        format, bzero = hdu.columns[i].format, hdu.columns[i].bzero

        # Remove numbers from format, to find just type
        format = format.strip("1234567890.")

        if type.type is np.string_ and format in ['I', 'F', 'E', 'D']:
            if format == 'I':
                type = np.int64
            elif format in ['F', 'E']:
                type = np.float32
            elif format == 'D':
                type = np.float64

        if format == 'X' and type.type == np.uint8:
            type = np.bool
            if len(shape) == 1:
                shape = (shape[0] * 8,)

        if format == 'L':
            type = np.bool

        if bzero and format in ['B', 'I', 'J']:
            if format == 'B' and bzero == -128:
                dtype.append((name, np.int8, shape))
            elif format == 'I' and bzero == - np.iinfo(np.int16).min:
                dtype.append((name, np.uint16, shape))
            elif format == 'J' and bzero == - np.iinfo(np.int32).min:
                dtype.append((name, np.uint32, shape))
            else:
                dtype.append((name, type, shape))
        else:
            dtype.append((name, type, shape))

    dtype = np.dtype(dtype)

    if self._masked:
        self._setup_table(len(hdu.data), dtype, units=columns.units)
    else:
        self._setup_table(len(hdu.data), dtype, units=columns.units, \
                          nulls=columns.nulls)

    # Populate the table

    for i, name in enumerate(columns.names):

        format, bzero = hdu.columns[i].format[-1], hdu.columns[i].bzero

        if bzero and format in ['B', 'I', 'J']:
            data = np.rec.recarray.field(hdu.data, i)
            if format == 'B' and bzero == -128:
                data = (data.astype(np.int16) + bzero).astype(np.int8)
            elif format == 'I' and bzero == - np.iinfo(np.int16).min:
                data = (data.astype(np.int32) + bzero).astype(np.uint16)
            elif format == 'J' and bzero == - np.iinfo(np.int32).min:
                data = (data.astype(np.int64) + bzero).astype(np.uint32)
            else:
                data = table.field(name)
        else:
            data = table.field(name)

        self.data[name][:] = data[:]

        if self._masked:
            if columns.nulls[i] == 'NAN.0':
                null = np.nan
            elif columns.nulls[i] == 'INF.0':
                null = np.inf
            else:
                null = columns.nulls[i]
            self.data[name].mask = smart_mask(data, null)
            self.data[name].set_fill_value(null)

    for key in header.keys():
        if not key[:4] in ['TFOR', 'TDIS', 'TDIM', 'TTYP', 'TUNI'] and \
            not key in standard_keys:
            self.add_keyword(key, header[key])

    try:
        header['COMMENT']
    except KeyError:
        pass
    else:
        # PyFITS used to define header['COMMENT'] as the last comment read in
        # (which was a string), but now defines it as a _HeaderCommentaryCards
        # object
        if isinstance(header['COMMENT'], basestring):
            for comment in header.get_comment():
                if isinstance(comment, fits.Card):
                    self.add_comment(comment.value)
                else:
                    self.add_comment(comment)
        else:
            for comment in header['COMMENT']:
                if isinstance(comment, fits.Card):
                    self.add_comment(comment.value)
                else:
                    self.add_comment(comment)

    if hdu.name:
        self.table_name = str(hdu.name)

    hdulist.close()

    return


def _to_hdu(self):
    '''
    Return the current table as a astropy.io.fits HDU object
    '''

    columns = []

    for name in self.names:

        if self._masked:
            data = self.data[name].filled()
            null = self.data[name].fill_value
            if data.ndim > 1:
                null = null[0]
            if type(null) in [np.bool_, np.bool]:
                null = bool(null)
        else:
            data = self.data[name]
            null = self.columns[name].null

        unit = self.columns[name].unit
        dtype = self.columns[name].dtype
        elemwidth = None

        if unit == None:
            unit = ''

        if data.ndim > 1:
            elemwidth = str(data.shape[1])

        column_type = smart_dtype(dtype)

        if column_type == np.string_:
            elemwidth = dtype.itemsize

        if column_type in type_dict:
            if elemwidth:
                format = str(elemwidth) + type_dict[column_type]
            else:
                format = type_dict[column_type]
        else:
            raise Exception("cannot use numpy type " + str(column_type))

        if column_type == np.uint16:
            bzero = - np.iinfo(np.int16).min
        elif column_type == np.uint32:
            bzero = - np.iinfo(np.int32).min
        elif column_type == np.uint64:
            raise Exception("uint64 unsupported")
        elif column_type == np.int8:
            bzero = -128
        else:
            bzero = None

        columns.append(fits.Column(name=name, format=format, unit=unit, \
            null=null, array=data, bzero=bzero))

    hdu = fits.new_table(fits.ColDefs(columns))
    try:
        hdu.name = self.table_name
    except:
        hdu.name = ''

    for key in self.keywords:

        if len(key) > 8:
            keyname = "hierarch " + key
        else:
            keyname = key

        try:  # PyFITS 3.x
            hdu.header[keyname] = self.keywords[key]
        except KeyError:  # PyFITS 2.x
            hdu.header.update(keyname, self.keywords[key])

    for comment in self.comments:
        hdu.header.add_comment(comment)

    return hdu


def write(self, filename, overwrite=False):
    '''
    Write the table to a FITS file

    Required Arguments:

        *filename*: [ string ]
            The FITS file to write the table to

    Optional Keyword Arguments:

        *overwrite*: [ True | False ]
            Whether to overwrite any existing file without warning
    '''

    if os.path.exists(filename):
        if overwrite:
            os.remove(filename)
        else:
            raise Exception("File exists: %s" % filename)

    try:
        _to_hdu(self).writeto(filename)
    except:
        _to_hdu(self).writeto(filename, output_verify='silentfix')


# PyFITS can handle compression, so no decompression detection
@auto_download_to_file
@auto_fileobj_to_file
def read_set(self, filename, memmap=False, verbose=True):
    '''
    Read all tables from a FITS file

    Required Arguments:

        *filename*: [ string ]
            The FITS file to read the tables from

    Optional Keyword Arguments:

        *memmap*: [ bool ]
            Whether PyFITS should use memory mapping
    '''

    self.reset()

    # Read in primary header
    header = fits.getheader(filename, 0)

    for key in header.keys():
        if not key[:4] in ['TFOR', 'TDIS', 'TDIM', 'TTYP', 'TUNI'] and \
            not key in standard_keys:
            self.add_keyword(key, header[key])

    try:
        header['COMMENT']
    except KeyError:
        pass
    else:
        # PyFITS used to define header['COMMENT'] as the last comment read in
        # (which was a string), but now defines it as a _HeaderCommentaryCards
        # object
        if isinstance(header['COMMENT'], basestring):
            for comment in header.get_comment():
                if isinstance(comment, fits.Card):
                    self.add_comment(comment.value)
                else:
                    self.add_comment(comment)
        else:
            for comment in header['COMMENT']:
                if isinstance(comment, fits.Card):
                    self.add_comment(comment.value)
                else:
                    self.add_comment(comment)


    # Read in tables one by one
    from .basetable import Table
    for hdu in _list_tables(filename):
        table = Table()
        read(table, filename, hdu=hdu, memmap=memmap, verbose=verbose)
        self.append(table)


def write_set(self, filename, overwrite=False):
    '''
    Write the tables to a FITS file

    Required Arguments:

        *filename*: [ string ]
            The FITS file to write the tables to

    Optional Keyword Arguments:

        *overwrite*: [ True | False ]
            Whether to overwrite any existing file without warning
    '''

    if os.path.exists(filename):
        if overwrite:
            os.remove(filename)
        else:
            raise Exception("File exists: %s" % filename)

    primary = fits.PrimaryHDU()
    for key in self.keywords:

        if len(key) > 8:
            keyname = "hierarch " + key
        else:
            keyname = key

        try:  # PyFITS 3.x
            primary.header[keyname] = self.keywords[key]
        except KeyError:  # PyFITS 2.x
            primary.header.update(keyname, self.keywords[key])

    for comment in self.comments:
        primary.header.add_comment(comment)

    hdulist = [primary]
    for table_key in self.tables:
        hdulist.append(_to_hdu(self.tables[table_key]))
    hdulist = fits.HDUList(hdulist)
    hdulist.writeto(filename)

########NEW FILE########
__FILENAME__ = hdf5table
from __future__ import print_function, division

import os

import numpy as np

try:
    asstr = np.compat.asstr
except AttributeError:  # For Numpy 1.4.1
    import sys
    if sys.version_info[0] >= 3:
        def asstr(s):
            if isinstance(s, bytes):
                return s.decode('latin1')
            return str(s)
    else:
        asstr = str

from .exceptions import TableException
from .decorators import auto_download_to_file, auto_decompress_to_fileobj, auto_fileobj_to_file


try:
    import h5py
    h5py_installed = True
except:
    h5py_installed = False

STRING_TYPES = [bytes, np.string_, str]


try:
    STRING_TYPES.append(np.bytes_)
except AttributeError:
    pass


try:
    STRING_TYPES.append(unicode)
except NameError:
    pass


def _check_h5py_installed():
    if not h5py_installed:
        raise Exception("Cannot read/write HDF5 files - h5py required")


def _get_group(filename, group="", append=False):

    if append:
        f = h5py.File(filename, 'a')
    else:
        f = h5py.File(filename, 'w')

    if group:
        if append:
            if group in f.keys():
                g = f[group]
            else:
                g = f.create_group(group)
        else:
            g = f.create_group(group)
    else:
        g = f

    return f, g


def _create_required_groups(g, path):
    '''
    Given a file or group handle, and a path, make sure that the specified
    path exists and create if necessary.
    '''
    for dirname in path.split('/'):
        if not dirname in g:
            g = g.create_group(dirname)
        else:
            g = g[dirname]


def _list_tables(file_handle):
    list_of_names = []
    file_handle.visit(list_of_names.append)
    tables = {}
    for item in list_of_names:
        if isinstance(file_handle[item], h5py.highlevel.Dataset):
            if file_handle[item].dtype.names:
                tables[item] = item
    return tables


@auto_download_to_file
@auto_decompress_to_fileobj
@auto_fileobj_to_file
def read(self, filename, table=None, verbose=True):
    '''
    Read a table from an HDF5 file

    Required Arguments:

        *filename*: [ string ]
            The HDF5 file to read the table from

          OR

        *file or group handle*: [ h5py.highlevel.File | h5py.highlevel.Group ]
            The HDF5 file handle or group handle to read the table from

    Optional Keyword Arguments:

        *table*: [ string ]
            The name of the table to read from the HDF5 file (this is only
            required if there are more than one table in the file)
    '''

    _check_h5py_installed()

    self.reset()

    if isinstance(filename, h5py.highlevel.File) or isinstance(filename, h5py.highlevel.Group):
        f, g = None, filename
    else:
        if not os.path.exists(filename):
            raise Exception("File not found: %s" % filename)
        f = h5py.File(filename, 'r')
        g = f['/']

    # If no table is requested, check that there is only one table
    if table is None:
        tables = _list_tables(g)
        if len(tables) == 1:
            table = tables.keys()[0]
        else:
            raise TableException(tables, 'table')

    # Set the table name
    self.table_name = str(table)

    self._setup_table(len(g[table]), g[table].dtype)

    # Add columns to table
    for name in g[table].dtype.names:
        self.data[name][:] = g[table][name][:]

    for attribute in g[table].attrs:
        # Due to a bug in HDF5, in order to get this to work in Python 3, we
        # need to encode string values in utf-8
        if type(g[table].attrs[attribute]) in STRING_TYPES:
            self.add_keyword(attribute, asstr(g[table].attrs[attribute]))
        else:
            self.add_keyword(attribute, g[table].attrs[attribute])


    if f is not None:
        f.close()


@auto_download_to_file
@auto_decompress_to_fileobj
@auto_fileobj_to_file
def read_set(self, filename, pedantic=False, verbose=True):
    '''
    Read all tables from an HDF5 file

    Required Arguments:

        *filename*: [ string ]
            The HDF5 file to read the tables from
    '''

    _check_h5py_installed()

    self.reset()

    if isinstance(filename, h5py.highlevel.File) or isinstance(filename, h5py.highlevel.Group):
        f, g = None, filename
    else:
        if not os.path.exists(filename):
            raise Exception("File not found: %s" % filename)
        f = h5py.File(filename, 'r')
        g = f['/']

    for keyword in g.attrs:
        # Due to a bug in HDF5, in order to get this to work in Python 3, we
        # need to encode string values in utf-8
        if type(g.attrs[keyword]) in STRING_TYPES:
            self.keywords[keyword] = asstr(g.attrs[keyword])
        else:
            self.keywords[keyword] = g.attrs[keyword]

    from .basetable import Table
    for table in _list_tables(g):
        t = Table()
        read(t, filename, table=table, verbose=verbose)
        self.append(t)

    if f is not None:
        f.close()

def write(self, filename, compression=False, group="", append=False,
          overwrite=False, ignore_groups=False):
    '''
    Write the table to an HDF5 file

    Required Arguments:

        *filename*: [ string ]
            The HDF5 file to write the table to

          OR

        *file or group handle*: [ h5py.highlevel.File | h5py.highlevel.Group ]
            The HDF5 file handle or group handle to write the table to

    Optional Keyword Arguments:

        *compression*: [ True | False ]
            Whether to compress the table inside the HDF5 file

        *group*: [ string ]
            The group to write the table to inside the HDF5 file

        *append*: [ True | False ]
            Whether to append the table to an existing HDF5 file

        *overwrite*: [ True | False ]
            Whether to overwrite any existing file without warning

        *ignore_groups*: [ True | False ]
            With this option set to True, groups are removed from table names.
            With this option set to False, tables are placed in groups that
            are present in the table name, and the groups are created if
            necessary.
    '''

    _check_h5py_installed()

    if isinstance(filename, h5py.highlevel.File) or isinstance(filename, h5py.highlevel.Group):
        f, g = None, filename
        if group:
            if group in g:
                g = g[group]
            else:
                g = g.create_group(group)
    else:
        if os.path.exists(filename) and not append:
            if overwrite:
                os.remove(filename)
            else:
                raise Exception("File exists: %s" % filename)

        f, g = _get_group(filename, group=group, append=append)

    if self.table_name:
        name = self.table_name
    else:
        name = "Table"

    if ignore_groups:
        name = os.path.basename(name)
    else:
        path = os.path.dirname(name)
        if path:
            _create_required_groups(g, path)

    if name in g.keys():
        raise Exception("Table %s/%s already exists" % (group, name))

    dset = g.create_dataset(name, data=self.data, compression=compression)

    for keyword in self.keywords:
        # Due to a bug in HDF5, in order to get this to work in Python 3, we
        # need to encode string values in utf-8. In addition, we have to use
        # np.string_ to ensure that fixed-length attributes are used.
        if isinstance(self.keywords[keyword], basestring):
            dset.attrs[keyword] = np.string_(self.keywords[keyword])
        else:
            dset.attrs[keyword] = self.keywords[keyword]

    if f is not None:
        f.close()


def write_set(self, filename, compression=False, group="", append=False,
              overwrite=False, ignore_groups=False, **kwargs):
    '''
    Write the tables to an HDF5 file

    Required Arguments:

        *filename*: [ string ]
            The HDF5 file to write the tables to

          OR

        *file or group handle*: [ h5py.highlevel.File | h5py.highlevel.Group ]
            The HDF5 file handle or group handle to write the tables to

    Optional Keyword Arguments:

        *compression*: [ True | False ]
            Whether to compress the tables inside the HDF5 file

        *group*: [ string ]
            The group to write the table to inside the HDF5 file

        *append*: [ True | False ]
            Whether to append the tables to an existing HDF5 file

        *overwrite*: [ True | False ]
            Whether to overwrite any existing file without warning

        *ignore_groups*: [ True | False ]
            With this option set to True, groups are removed from table names.
            With this option set to False, tables are placed in groups that
            are present in the table name, and the groups are created if
            necessary.
    '''

    _check_h5py_installed()

    if isinstance(filename, h5py.highlevel.File) or isinstance(filename, h5py.highlevel.Group):
        f, g = None, filename
        if group:
            if group in g:
                g = g[group]
            else:
                g = g.create_group(group)
    else:
        if os.path.exists(filename) and not append:
            if overwrite:
                os.remove(filename)
            else:
                raise Exception("File exists: %s" % filename)

        f, g = _get_group(filename, group=group, append=append)

    for keyword in self.keywords:
        # Due to a bug in HDF5, in order to get this to work in Python 3, we
        # need to encode string values in utf-8. In addition, we have to use
        # np.string_ to ensure that fixed-length attributes are used.
        if isinstance(self.keywords[keyword], basestring):
            g.attrs[keyword] = np.string_(self.keywords[keyword])
        else:
            g.attrs[keyword] = self.keywords[keyword]


    for i, table_key in enumerate(self.tables):

        if self.tables[table_key].table_name:
            name = self.tables[table_key].table_name
        else:
            name = "Table_%02i" % i

        if ignore_groups:
            name = os.path.basename(name)
        else:
            path = os.path.dirname(name)
            if path:
                _create_required_groups(g, path)

        if name in g.keys():
            raise Exception("Table %s/%s already exists" % (group, name))

        dset = g.create_dataset(name, data=self.tables[table_key].data, compression=compression)

        for keyword in self.tables[table_key].keywords:
            # Due to a bug in HDF5, in order to get this to work in Python 3, we
            # need to encode string values in utf-8. In addition, we have to use
            # np.string_ to ensure that fixed-length attributes are used.
            if isinstance(self.tables[table_key].keywords[keyword], basestring):
                dset.attrs[keyword] = np.string_(self.tables[table_key].keywords[keyword])
            else:
                dset.attrs[keyword] = self.tables[table_key].keywords[keyword]

    if f is not None:
        f.close()

########NEW FILE########
__FILENAME__ = helpers
from __future__ import print_function, division

import numpy as np


def smart_mask(array, null):
    if type(null) in [float, np.float32, np.float64]:
        if np.isnan(null):
            return np.isnan(array)
        else:
            return array == null
    else:
        return array == null


def smart_dtype(dtype):
    if dtype.subdtype:
        return dtype.subdtype[0].type
    else:
        return dtype.type


def format_length(format):
    if '.' in format:
        return int(format.split('.')[0])
    else:
        return int(format[:-1])

########NEW FILE########
__FILENAME__ = htmltable
from __future__ import print_function, division

import numpy as np


def write(self, filename):

    f = open(filename, 'wb')

    f.write("<html>\n")
    f.write("  <head>\n")
    f.write("  </head>\n")
    f.write("  <body>\n")
    f.write("    <table border=1>\n")

    f.write("    <tr>\n")
    for name in self.names:
        f.write("      <td><b>%s</b></td>\n" % name)
    f.write("    </tr>\n")

    f.write("    <tr>\n")
    for name in self.names:
        f.write("      <td><i>%s</i></td>\n" % self.columns[name].unit)
    f.write("    </tr>\n")

    for i in range(self.__len__()):

        f.write("    <tr>\n")

        for name in self.names:

            if self.columns[name].dtype == np.uint64:
                item = (("%" + self.columns[name].format) % long(self.data[name][i]))
            else:
                item = (("%" + self.columns[name].format) % self.data[name][i])

            f.write("      <td>%s</td>\n" % item.strip())

        f.write("    </tr>\n")

    f.write("    </table>\n")
    f.write("  </body>\n")
    f.write("  </html>\n")

    f.close()

########NEW FILE########
__FILENAME__ = ipactable
from __future__ import print_function, division

import os
import sys
import numpy as np
import warnings

from .helpers import smart_mask, format_length
from .decorators import auto_download_to_file, auto_decompress_to_fileobj, auto_fileobj_to_file

# Define type conversion from IPAC table to numpy arrays
type_dict = {}
type_dict['i'] = np.int64
type_dict['int'] = np.int64
type_dict['integer'] = np.int64
type_dict['long'] = np.int64
type_dict['double'] = np.float64
type_dict['float'] = np.float32
type_dict['real'] = np.float32
type_dict['char'] = np.str
type_dict['date'] = np.str

type_rev_dict = {}
type_rev_dict[np.bool_] = "int"
type_rev_dict[np.int8] = "int"
type_rev_dict[np.int16] = "int"
type_rev_dict[np.int32] = "int"
type_rev_dict[np.int64] = "int"
type_rev_dict[np.uint8] = "int"
type_rev_dict[np.uint16] = "int"
type_rev_dict[np.uint32] = "int"
type_rev_dict[np.uint64] = "int"
type_rev_dict[np.float32] = "float"
type_rev_dict[np.float64] = "double"
type_rev_dict[np.str] = "char"
type_rev_dict[np.string_] = "char"
type_rev_dict[str] = "char"

invalid = {}
invalid[np.int32] = -np.int64(2**31-1)
invalid[np.int64] = -np.int64(2**63-1)
invalid[np.float32] = np.float32(np.nan)
invalid[np.float64] = np.float64(np.nan)


@auto_download_to_file
@auto_decompress_to_fileobj
@auto_fileobj_to_file
def read(self, filename, definition=3, verbose=False, smart_typing=False):
    '''
    Read a table from a IPAC file

    Required Arguments:

        *filename*: [ string ]
            The IPAC file to read the table from

    Optional Keyword Arguments:

        *definition*: [ 1 | 2 | 3 ]

            The definition to use to read IPAC tables:

            1: any character below a pipe symbol belongs to the
               column on the left, and any characters below the
               first pipe symbol belong to the first column.
            2: any character below a pipe symbol belongs to the
               column on the right.
            3: no characters should be present below the pipe
               symbols (default).

        *smart_typing*: [ True | False ]

            Whether to try and save memory by using the smallest
            integer type that can contain a column. For example,
            a column containing only values between 0 and 255 can
            be stored as an unsigned 8-bit integer column. The
            default is false, so that all integer columns are
            stored as 64-bit integers.
    '''

    if not definition in [1, 2, 3]:
        raise Exception("definition should be one of 1/2/3")

    self.reset()

    # Open file for reading
    f = open(filename, 'r')

    line = f.readline()

    # Read in comments and keywords
    while True:

        char1 = line[0:1]
        char2 = line[1:2]

        if char1 != '\\':
            break

        if char2==' ' or not '=' in line: # comment
            self.add_comment(line[1:])
        else:          # keyword
            pos = line.index('=')
            key, value = line[1:pos], line[pos + 1:]
            value = value.replace("'", "").replace('"', '')
            key, value = key.strip(), value.strip()
            self.add_keyword(key, value)

        line = f.readline()


    # Column headers

    l = 0
    units = {}
    nulls = {}

    while True:

        char1 = line[0:1]

        if char1 != "|":
            break

        if l==0: # Column names

            line = line.replace('-', ' ').strip()

            # Find all pipe symbols
            pipes = []
            for i, c in enumerate(line):
                if c=='|':
                    pipes.append(i)

            # Find all names
            names = line.replace(" ", "").split("|")[1:-1]

        elif l==1: # Data types

            line = line.replace('-', ' ').strip()

            types = dict(zip(names, \
                line.replace(" ", "").split("|")[1:-1]))

        elif l==2: # Units

            units = dict(zip(names, \
                line.replace(" ", "").split("|")[1:-1]))

        else: # Null values

            nulls = dict(zip(names, \
                line.replace(" ", "").split("|")[1:-1]))

        line = f.readline()
        l = l + 1

    if len(pipes) != len(names) + 1:
        raise "An error occured while reading the IPAC table"

    if len(units)==0:
        for name in names:
            units[name]=''

    if len(nulls)==0:
        nulls_given = False
        for name in names:
            nulls[name]=''
    else:
        nulls_given = True

    # Pre-compute numpy column types
    numpy_types = {}
    for name in names:
        numpy_types[name] = type_dict[types[name]]

    # Data

    array = {}
    for name in names:
        array[name] = []


    while True:

        if line.strip() == '':
            break

        for i in range(len(pipes)-1):

            first, last = pipes[i] + 1, pipes[i + 1]

            if definition==1:
                last = last + 1
                if first==1:
                    first=0
            elif definition==2:
                first = first - 1

            if i + 1==len(pipes)-1:
                item = line[first:].strip()
            else:
                item = line[first:last].strip()

            if item.lower() == 'null' and nulls[names[i]] != 'null':
                if nulls[names[i]] == '':
                    if verbose:
                        warnings.warn("WARNING: found unexpected 'null' value. Setting null value for column "+names[i]+" to 'null'")
                    nulls[names[i]] = 'null'
                    nulls_given = True
                else:
                    raise Exception("null value for column "+names[i]+" is set to "+nulls[i]+" but found value 'null'")
            array[names[i]].append(item)

        line = f.readline()

    # Check that null values are of the correct type
    if nulls_given:
        for name in names:
            try:
                n = numpy_types[name](nulls[name])
                nulls[name] = n
            except:
                n = invalid[numpy_types[name]]
                for i, item in enumerate(array[name]):
                    if item == nulls[name]:
                        array[name][i] = n
                if verbose:
                    if len(str(nulls[name]).strip()) == 0:
                        warnings.warn("WARNING: empty null value for column "+name+" set to "+str(n))
                    else:
                        warnings.warn("WARNING: null value for column "+name+" changed from "+str(nulls[name])+" to "+str(n))
                nulls[name] = n

    # Convert to numpy arrays
    for name in names:

        if smart_typing:

            dtype = None

            low = min(array[name])
            high = max(array[name])

            if types[name] in ['i', 'int', 'integer']:
                low, high = long(low), long(high)
                for nt in [np.uint8, np.int8, np.uint16, np.int16, np.uint32, np.int32, np.uint64, np.int64]:
                    if low >= np.iinfo(nt).min and high <= np.iinfo(nt).max:
                        dtype = nt
                        break
            elif types[name] in ['long']:
                low, high = long(low), long(high)
                for nt in [np.uint64, np.int64]:
                    if low >= np.iinfo(nt).min and high <= np.iinfo(nt).max:
                        dtype = nt
                        break
            elif types[name] in ['float', 'real']:
                low, high = float(low), float(high)
                for nt in [np.float32, np.float64]:
                    if low >= np.finfo(nt).min and high <= np.finfo(nt).max:
                        dtype = nt
                        break
            else:
                dtype = type_dict[types[name]]

        else:
            dtype = type_dict[types[name]]

            # If max integer is larger than 2**63 then use uint64
            if dtype == np.int64:
                if max([long(x) for x in array[name]]) > 2**63:
                    dtype = np.uint64
                    warnings.warn("using type uint64 for column %s" % name)

        array[name] = np.array(array[name], dtype=dtype)

        if smart_typing:
            if np.min(array) >= 0 and np.max(array) <= 1:
                array = array == 1

        if self._masked:
            self.add_column(name, array[name], \
                mask=smart_mask(array[name], nulls[name]), unit=units[name], \
                fill=nulls[name])
        else:
            self.add_column(name, array[name], \
                null=nulls[name], unit=units[name])


def write(self, filename, overwrite=False):
    '''
    Write the table to an IPAC file

    Required Arguments:

        *filename*: [ string ]
            The IPAC file to write the table to
    '''

    self._raise_vector_columns()

    if os.path.exists(filename):
        if overwrite:
            os.remove(filename)
        else:
            raise Exception("File exists: %s" % filename)

    # Open file for writing
    f = open(filename, 'w')

    for key in self.keywords:
        value = self.keywords[key]
        f.write("\\" + key + "=" + str(value) + "\n")

    for comment in self.comments:
        f.write("\\ " + comment + "\n")

    # Compute width of all columns

    width = {}
    format = {}

    line_names = ""
    line_types = ""
    line_units = ""
    line_nulls = ""

    width = {}

    for name in self.names:

        dtype = self.columns[name].dtype

        coltype = type_rev_dict[dtype.type]
        colunit = self.columns[name].unit

        if self._masked:
            colnull = self.data[name].fill_value
        else:
            colnull = self.columns[name].null

        if colnull:
            colnull = ("%" + self.columns[name].format) % colnull
        else:
            colnull = ''

        # Adjust the format for each column

        width[name] = format_length(self.columns[name].format)

        max_width = max(len(name), len(coltype), len(colunit), \
            len(colnull))

        if max_width > width[name]:
            width[name] = max_width

        sf = "%" + str(width[name]) + "s"
        line_names = line_names + "|" + (sf % name)
        line_types = line_types + "|" + (sf % coltype)
        line_units = line_units + "|" + (sf % colunit)
        line_nulls = line_nulls + "|" + (sf % colnull)

    line_names = line_names + "|\n"
    line_types = line_types + "|\n"
    line_units = line_units + "|\n"
    line_nulls = line_nulls + "|\n"

    f.write(line_names)
    f.write(line_types)
    if len(line_units.replace("|", "").strip()) > 0:
        f.write(line_units)
    if len(line_nulls.replace("|", "").strip()) > 0:
        f.write(line_nulls)

    for i in range(self.__len__()):

        line = ""

        for name in self.names:
            if self.columns[name].dtype == np.uint64:
                item = (("%" + self.columns[name].format) % long(self.data[name][i]))
            elif sys.version_info[0] >= 3 and self.columns[name].dtype.type == np.bytes_:
                item = (("%" + self.columns[name].format) % self.data[name][i].decode('utf-8'))
            else:
                item = (("%" + self.columns[name].format) % self.data[name][i])
            item = ("%" + str(width[name]) + "s") % item

            if len(item) > width[name]:
                raise Exception('format for column %s (%s) is not wide enough to contain data' % (name, self.columns[name].format))

            line = line + " " + item

        line = line + " \n"

        f.write(line)

    f.close()

########NEW FILE########
__FILENAME__ = irsa_service
from __future__ import print_function, division

import warnings
import urllib

import sys
if sys.version_info[0] > 2:
    from urllib.request import Request, urlopen
else:
    from urllib2 import Request, urlopen

import tempfile
import string
from xml.etree.ElementTree import ElementTree

'''

API from

 http://irsa.ipac.caltech.edu/applications/Gator/GatorAid/irsa/catsearch.html

The URL of the IRSA catalog query service, CatQuery, is

 http://irsa.ipac.caltech.edu/cgi-bin/Gator/nph-query

The service accepts the following keywords, which are analogous to the search
fields on the Gator search form:


spatial     Required    Type of spatial query: Cone, Box, Polygon, and NONE

polygon                 Convex polygon of ra dec pairs, separated by comma(,)
                        Required if spatial=polygon

radius                  Cone search radius
                        Optional if spatial=Cone, otherwise ignore it
                        (default 10 arcsec)

radunits                Units of a Cone search: arcsec, arcmin, deg.
                        Optional if spatial=Cone
                        (default='arcsec')

size                    Width of a box in arcsec
                        Required if spatial=Box.

objstr                  Target name or coordinate of the center of a spatial
                        search center. Target names must be resolved by
                        SIMBAD or NED.

                        Required only when spatial=Cone or spatial=Box.

                        Examples: 'M31'
                                  '00 42 44.3 -41 16 08'
                                  '00h42m44.3s -41d16m08s'

catalog     Required    Catalog name in the IRSA database management system.

outfmt      Optional    Defines query's output format.
                        6 - returns a program interface in XML
                        3 - returns a VO Table (XML)
                        2 - returns SVC message
                        1 - returns an ASCII table
                        0 - returns Gator Status Page in HTML (default)

desc        Optional    Short description of a specific catalog, which will
                        appear in the result page.

order       Optional    Results ordered by this column.

constraint  Optional    User defined query constraint(s)
                        Note: The constraint should follow SQL syntax.

onlist      Optional    1 - catalog is visible through Gator web interface
                        (default)

                        0 - catalog has been ingested into IRSA but not yet
                        visible through web interface.

                        This parameter will generally only be set to 0 when
                        users are supporting testing and evaluation of new
                        catalogs at IRSA's request.

If onlist=0, the following parameters are required:

    server              Symbolic DataBase Management Server (DBMS) name

    database            Name of Database.

    ddfile              The data dictionary file is used to get column
                        information for a specific catalog.

    selcols             Target column list with value separated by a comma(,)

                        The input list always overwrites default selections
                        defined by a data dictionary.

    outrows             Number of rows retrieved from database.

                        The retrieved row number outrows is always less than or
                        equal to available to be retrieved rows under the same
                        constraints.
'''


def read(self, spatial, catalog, objstr=None, radius=None,
         units='arcsec', size=None, polygon=None):
    '''
    Query the NASA/IPAC Infrared Science Archive (IRSA)

    Required Arguments:

        *spatial* [ 'Cone' | 'Box' | 'Polygon' ]
            The type of query to execute

        *catalog* [ string ]
            One of the catalogs listed by ``atpy.irsa_service.list_catalogs()``

    Optional Keyword Arguments:

        *objstr* [ str ]
            This string gives the position of the center of the cone or box if
            performing a cone or box search. The string can give coordinates
            in various coordinate systems, or the name of a source that will
            be resolved on the server (see `here
            <http://irsa.ipac.caltech.edu/search_help.html>`_ for more
            details). Required if spatial is 'Cone' or 'Box'.

        *radius* [ float ]
            The radius for the cone search. Required if spatial is 'Cone'

        *units* [ 'arcsec' | 'arcmin' | 'deg' ]
            The units for the cone search radius. Defaults to 'arcsec'.

        *size* [ float ]
            The size of the box to search in arcseconds. Required if spatial
            is 'Box'.

        *polygon* [ list of tuples ]
            The list of (ra, dec) pairs, in decimal degrees, outlinining the
            polygon to search in. Required if spatial is 'Polygon'
     '''
    base_url = 'http://irsa.ipac.caltech.edu/cgi-bin/Gator/nph-query'

    self.reset()

    # Convert to lowercase
    spatial = spatial.capitalize()

    # Set basic options
    options = {}
    options['spatial'] = spatial
    options['catalog'] = catalog
    options['outfmt'] = 3

    if spatial == "Cone":

        if not radius:
            raise Exception("radius is required for Cone search")
        options['radius'] = radius

        if not units:
            raise Exception("units is required for Cone search")
        if units not in ['arcsec', 'arcmin', 'deg']:
            raise Exception("units should be one of arcsec/arcmin/deg")
        options['radunits'] = units

        if not objstr:
            raise Exception("objstr is required for Cone search")
        options['objstr'] = objstr

    elif spatial == "Box":

        if not size:
            raise Exception("size is required for Box search")
        options['size'] = size

        if not objstr:
            raise Exception("objstr is required for Cone search")
        options['objstr'] = objstr

    elif spatial == "Polygon":

        if not polygon:
            raise Exception("polygon is required for Polygon search")
        pairs = []
        for pair in polygon:
            if pair[1] > 0:
                pairs.append(str(pair[0]) + '+' + str(pair[1]))
            else:
                pairs.append(str(pair[0]) + str(pair[1]))
        options['polygon'] = string.join(pairs, ',')

    elif spatial == "None":

        options['spatial'] = 'NONE'

    else:

        raise Exception("spatial should be one of cone/box/polygon/none")

    # Construct query URL
    url = base_url + "?" + \
          string.join(["%s=%s" % (x, urllib.quote_plus(str(options[x]))) for x in options], "&")

    # Request page
    req = Request(url)
    response = urlopen(req)
    result = response.read()

    # Check if results were returned
    if 'The catalog is not on the list' in result:
        raise Exception("Catalog not found")

    # Check that object name was not malformed
    if 'Either wrong or missing coordinate/object name' in result:
        raise Exception("Malformed coordinate/object name")

    # Check that the results are not of length zero
    if len(result) == 0:
        raise Exception("The IRSA server sent back an empty reply")

    # Write table to temporary file
    output = tempfile.NamedTemporaryFile()
    output.write(result)
    output.flush()

    # Read it in using ATpy VO reader
    self.read(output.name, type='vo', verbose=False)

    # Set table name
    self.table_name = "IRSA_query"

    # Check if table is empty
    if len(self) == 0:
        warnings.warn("Query returned no results, so the table will be empty")

    # Remove temporary file
    output.close()


def list_catalogs():

    url = 'http://irsa.ipac.caltech.edu/cgi-bin/Gator/nph-scan?mode=xml'

    req = Request(url)
    response = urlopen(req)

    tree = ElementTree()

    for catalog in tree.parse(response).findall('catalog'):
        catname = catalog.find('catname').text
        desc = catalog.find('desc').text
        print("%30s  %s" % (catname, desc))

########NEW FILE########
__FILENAME__ = latextable
from __future__ import print_function, division


class LaTeXTable(object):

    def latex_write(self, filename):

        # Open file for writing
        f = open(filename, 'wb')

        for i in range(self.__len__()):

            line = ""

            for j, name in enumerate(self.names):
                if j > 0:
                    line += ' & '
                line += (("%" + self.columns[name].format) % self.data[name][i])

            line = line + " \\\\ \n"

            f.write(line)

        f.close()

########NEW FILE########
__FILENAME__ = masked
import os
import warnings

import sys
if sys.version_info[0] == 2:
    from ConfigParser import SafeConfigParser
else:
    from configparser import SafeConfigParser

__masked__ = False


def set_masked_default(choice):
    'Set whether tables should be masked or not by default (True or False)'
    global __masked__
    __masked__ = choice

filename = os.path.expanduser('~/.atpyrc')
config = SafeConfigParser()
config.read(filename)
if config.has_option('general', 'masked_default'):
    if config.getboolean('general', 'masked_default'):
        warnings.warn(".atpyrc file found - masked arrays are ON by default")
        set_masked_default(True)
    else:
        warnings.warn(".atpyrc file found - masked arrays are OFF by default")
        set_masked_default(False)

########NEW FILE########
__FILENAME__ = odict
from __future__ import print_function, division

import numpy as np

class odict(object):

    def __init__(self):
        self.keys = []
        self.values = []

    def __setitem__(self, key, value):
        if type(key) == int:
            if key > len(self.keys) - 1:
                raise Exception("Element %i does not exist" % key)
            else:
                self.values[key] = value
        elif type(key) in [str, np.string_, unicode]:
            if key in self.keys:
                index = self.keys.index(key)
                self.values[index] = value
            else:
                self.keys.append(key)
                self.values.append(value)
        else:
            raise Exception("Wrong type for key: %s" % type(key))

    def __getitem__(self, key):
        if type(key) == int:
            return self.values[key]
        elif type(key) in [str, np.string_]:
            index = self.keys.index(key)
            return self.values[index]
        else:
            raise Exception("Wrong type for key: %s" % type(key))

    def __repr__(self):
        string = "{"
        for i, key in enumerate(self.keys):
            if i > 0:
                string += ", "
            string += "\n%s : %s" % (key, self.values[i])
        string += "\n}"
        return string

    def __contains__(self, key):
        return key in self.keys

    def pop(self, key):
        index = self.keys.index(key)
        self.keys.pop(index)
        self.values.pop(index)

    def __len__(self):
        return len(self.keys)

    def rename(self, oldkey, newkey):
        index = self.keys.index(oldkey)
        self.keys[index] = newkey
        return

    def insert(self, position, key, value):
        self.keys.insert(position, key)
        self.values.insert(position, value)
        return

    def __iter__(self):
        return iter(self.keys)

    def items(self):
        return zip(self.keys, self.values)

########NEW FILE########
__FILENAME__ = rechelper
from __future__ import print_function, division

import numpy as np


def append_field(rec, data, dtype=None, position='undefined'):
    newdtype = rec.dtype.descr
    if position == 'undefined':
        newdtype.append(dtype)
    else:
        newdtype.insert(position, dtype)
    newdtype = np.dtype(newdtype)
    newrec = np.recarray(rec.shape, dtype=newdtype)
    for field in rec.dtype.fields:
        newrec[field] = rec[field]
    newrec[dtype[0]] = data
    return newrec


def drop_fields(rec, names):

    names = set(names)

    newdtype = np.dtype([(name, rec.dtype[name]) for name in rec.dtype.names
                       if name not in names])

    newrec = np.recarray(rec.shape, dtype=newdtype)

    for field in newdtype.fields:
        newrec[field] = rec[field]

    return newrec

########NEW FILE########
__FILENAME__ = registry
_readers = {}
_writers = {}
_set_readers = {}
_set_writers = {}
_extensions = {}


def register_reader(ttype, function, override=False):
    '''
    Register a table reader function.

    Required Arguments:

        *ttype*: [ string ]
            The table type identifier. This is the string that will be used to
            specify the table type when reading.

        *function*: [ function ]
            The function to read in a single table.

    Optional Keyword Arguments:

        *override*: [ True | False ]
            Whether to override any existing type if already present.
    '''

    if not ttype in _readers or override:
        _readers[ttype] = function
    else:
        raise Exception("Type %s is already defined" % ttype)


def register_writer(ttype, function, override=False):
    '''
    Register a table writer function.

    Required Arguments:

        *ttype*: [ string ]
            The table type identifier. This is the string that will be used to
            specify the table type when writing.

        *function*: [ function ]
            The function to write out a single table.

    Optional Keyword Arguments:

        *override*: [ True | False ]
            Whether to override any existing type if already present.
    '''

    if not ttype in _writers or override:
        _writers[ttype] = function
    else:
        raise Exception("Type %s is already defined" % ttype)


def register_set_reader(ttype, function, override=False):
    '''
    Register a table set reader function.

    Required Arguments:

        *ttype*: [ string ]
            The table type identifier. This is the string that will be used to
            specify the table type when reading.

        *function*: [ function ]
            The function to read in a table set.

    Optional Keyword Arguments:

        *override*: [ True | False ]
            Whether to override any existing type if already present.
    '''

    if not ttype in _set_readers or override:
        _set_readers[ttype] = function
    else:
        raise Exception("Type %s is already defined" % ttype)


def register_set_writer(ttype, function, override=False):
    '''
    Register a table set writer function.

    Required Arguments:

        *ttype*: [ string ]
            The table type identifier. This is the string that will be used to
            specify the table type when writing.

        *function*: [ function ]
            The function to write out a table set.

    Optional Keyword Arguments:

        *override*: [ True | False ]
            Whether to override any existing type if already present.
    '''

    if not ttype in _set_writers or override:
        _set_writers[ttype] = function
    else:
        raise Exception("Type %s is already defined" % ttype)


def register_extensions(ttype, extensions, override=False):
    '''
    Associate file extensions with a specific table type

    Required Arguments:

        *ttype*: [ string ]
            The table type identifier. This is the string that is used to
            specify the table type when reading.

        *extensions*: [ string or list or tuple ]
            List of valid extensions for the table type - used for auto type
            selection. All extensions should be given in lowercase as file
            extensions are converted to lowercase before checking against this
            list. If a single extension is given, it can be specified as a
            string rather than a list of strings

    Optional Keyword Arguments:

        *override*: [ True | False ]
            Whether to override any extensions if already present.
    '''

    if type(extensions) == str:
        extensions = [extensions]

    for extension in extensions:
        if not extension in _extensions or override:
            _extensions[extension] = ttype
        else:
            raise Exception("Extension %s is already defined" % extension)


def _determine_type(string, verbose):

    if not isinstance(string, basestring):
        raise Exception('Could not determine table type (non-string argument)')

    s = str(string).lower()

    if not '.' in s:
        extension = s
    else:
        extension = s.split('.')[-1]
        if extension.lower() in ['gz', 'bz2', 'bzip2']:
            extension = s.split('.')[-2]

    if extension in _extensions:
        table_type = _extensions[extension]
        if verbose:
            print("Auto-detected table type: %s" % table_type)
    else:
        raise Exception('Could not determine table type for extension %s' % extension)

    return table_type

from . import fitstable

register_reader('fits', fitstable.read)
register_writer('fits', fitstable.write)
register_set_reader('fits', fitstable.read_set)
register_set_writer('fits', fitstable.write_set)
register_extensions('fits', ['fit', 'fits'])

from . import votable

register_reader('vo', votable.read)
register_writer('vo', votable.write)
register_set_reader('vo', votable.read_set)
register_set_writer('vo', votable.write_set)
register_extensions('vo', ['xml', 'vot'])

from . import ipactable

register_reader('ipac', ipactable.read)
register_writer('ipac', ipactable.write)
register_extensions('ipac', ['ipac', 'tbl'])

from . import sqltable

register_reader('sql', sqltable.read)
register_writer('sql', sqltable.write)
register_set_reader('sql', sqltable.read_set)
register_set_writer('sql', sqltable.write_set)
register_extensions('sql', ['sqlite', 'postgres', 'mysql', 'db'])

from . import asciitables

register_reader('cds', asciitables.read_cds)
register_reader('mrt', asciitables.read_cds)

register_reader('latex', asciitables.read_latex)
register_writer('latex', asciitables.write_latex)

register_reader('rdb', asciitables.read_rdb)
register_writer('rdb', asciitables.write_rdb)
register_extensions('rdb', ['rdb'])

register_reader('daophot', asciitables.read_daophot)

register_reader('ascii', asciitables.read_ascii)
register_writer('ascii', asciitables.write_ascii)

from . import hdf5table

register_reader('hdf5', hdf5table.read)
register_set_reader('hdf5', hdf5table.read_set)
register_writer('hdf5', hdf5table.write)
register_set_writer('hdf5', hdf5table.write_set)
register_extensions('hdf5', ['hdf5', 'h5'])

from . import irsa_service

register_reader('irsa', irsa_service.read)

from . import vo_conesearch

register_reader('vo_conesearch', vo_conesearch.read)

from . import htmltable

register_writer('html', htmltable.write)
register_extensions('html', ['html', 'htm'])

########NEW FILE########
__FILENAME__ = sqlhelper
from __future__ import print_function, division

from distutils import version
import numpy as np
import warnings
import math
import sys

# SQLite

import sqlite3

# SQLite

MySQLdb_minimum_version = version.LooseVersion('1.2.2')

try:
    import MySQLdb
    import MySQLdb.constants.FIELD_TYPE as mysqlft
    if version.LooseVersion(MySQLdb.__version__) < MySQLdb_minimum_version:
        raise
    MySQLdb_installed = True
except:
    MySQLdb_installed = False

mysql_types = {}
if MySQLdb_installed:
    for variable in list(dir(mysqlft)):
        if variable[0] != '_':
            code = mysqlft.__getattribute__(variable)
            mysql_types[code] = variable


def _check_MySQLdb_installed():
    if not MySQLdb_installed:
        raise Exception("Cannot read/write MySQL tables - MySQL-python " + \
            MySQLdb_minimum_version.vstring + " or later required")

 # SQLite

PyGreSQL_minimum_version = version.LooseVersion('3.8.1')

try:
    import pgdb
    PyGreSQL_installed = True
except:
    PyGreSQL_installed = False


def _check_PyGreSQL_installed():
    if not PyGreSQL_installed:
        raise Exception("Cannot read/write PostGreSQL tables - PyGreSQL " + \
            PyGreSQL_minimum_version.vstring + " or later required")

# Type conversion dictionary

type_dict = {}

type_dict[np.bool_] = "BOOL"

type_dict[np.uint8] = "TINYINT"
type_dict[np.uint16] = "SMALLINT"
type_dict[np.uint32] = "INT"
type_dict[np.uint64] = "BIGINT"

type_dict[np.int8] = "TINYINT"
type_dict[np.int16] = "SMALLINT"
type_dict[np.int32] = "INT"
type_dict[np.int64] = "BIGINT"

type_dict[np.float32] = "FLOAT"

type_dict[np.float64] = "DOUBLE PRECISION"

type_dict[np.str] = "TEXT"
type_dict[np.string_] = "TEXT"
type_dict[str] = "TEXT"

# Reverse type conversion dictionary

type_dict_rev = {}

type_dict_rev['bool'] = np.bool_

type_dict_rev['tiny'] = np.int8
type_dict_rev['tinyint'] = np.int8

type_dict_rev['short'] = np.int16
type_dict_rev['smallint'] = np.int16
type_dict_rev['int2'] = np.int16

type_dict_rev['int'] = np.int32
type_dict_rev['int4'] = np.int32
type_dict_rev['integer'] = np.int32

type_dict_rev['int8'] = np.int64
type_dict_rev['bigint'] = np.int64
type_dict_rev['long'] = np.int64
type_dict_rev['longlong'] = np.int64

type_dict_rev['float'] = np.float32
type_dict_rev['float4'] = np.float32

type_dict_rev['float8'] = np.float64
type_dict_rev['double'] = np.float64
type_dict_rev['double precision'] = np.float64

type_dict_rev['real'] = np.float64

type_dict_rev['text'] = np.str
type_dict_rev['varchar'] = np.str
type_dict_rev['blob'] = np.str
type_dict_rev['timestamp'] = np.str
type_dict_rev['datetime'] = np.str
type_dict_rev['date'] = np.str
type_dict_rev['var_string'] = np.str
type_dict_rev['decimal'] = np.str
type_dict_rev['numeric'] = np.str
type_dict_rev['enum'] = np.str


# Define symbol to use in insert statement

insert_symbol = {}
insert_symbol['sqlite'] = "?"
insert_symbol['mysql'] = "%s"
insert_symbol['postgres'] = "%s"

# Define quote symbol for column names

quote = {}
quote['sqlite'] = '`'
quote['mysql'] = '`'
quote['postgres'] = '"'


def numpy_type(sql_type):
    '''
    Returns the numpy type corresponding to an SQL type

    Required arguments:

        *sql_type*: [ string ]
            The SQL type to find the numpy type for
    '''
    unsigned = 'unsigned' in sql_type
    sql_type = sql_type.split('(')[0].lower()
    if not sql_type in type_dict_rev:
        print("WARNING: need to define reverse type for " + str(sql_type))
        print("         Please report this on the ATpy forums!")
        print("         This type has been converted to a string")
        sql_type = 'text'
    dtype = type_dict_rev[sql_type]
    if unsigned:
        if dtype == np.int8:
            return np.uint8
        elif dtype == np.int16:
            return np.uint16
        elif dtype == np.int32:
            return np.uint32
        elif dtype == np.int64:
            return np.uint64
        else:
            raise Exception("Unexpected unsigned attribute for non-integer column")
    else:
        return dtype


def list_tables(cursor, dbtype):
    '''
    List all tables in a given SQL database

    Required Arguments:

        *cursor*: [ DB API cursor object ]
            A cursor for the current database in the DB API formalism

        *dbtype*: [ 'sqlite' | 'mysql' | 'postgres' ]
            The type of database
    '''
    tables = {}
    if dbtype=='sqlite':
        table_names = cursor.execute("select name from sqlite_master where \
            type = 'table'").fetchall()
        if len(table_names) == 1:
            table_names = table_names[0]
        for i, table_name in enumerate(table_names):
            if type(table_name) == tuple:
                table_name = table_name[0]
            if sys.version_info[0] > 2:
                tables[table_name] = table_name
            else:
                tables[str(table_name.encode())] = str(table_name.encode())
    elif dbtype=='mysql':
        cursor.execute('SHOW TABLES;')
        for i, table_name in enumerate(cursor):
            tables[str(table_name[0])] = str(table_name[0])
    elif dbtype=='postgres':
        cursor.execute("SELECT table_name FROM information_schema.tables \
            WHERE table_schema NOT IN ('pg_catalog', 'information_schema');")
        for i, table_name in enumerate(cursor.fetchall()):
            tables[str(table_name[0])] = str(table_name[0])
    else:
        raise Exception('dbtype should be one of sqlite/mysql/postgres')
    return tables


def column_info(cursor, dbtype, table_name):
    '''
    List all columns in a given SQL table

    Required Arguments:

        *cursor*: [ DB API cursor object ]
            A cursor for the current database in the DB API formalism

        *dbtype*: [ 'sqlite' | 'mysql' | 'postgres' ]
            The type of database

        *table_name*: [ string ]
            The name of the table to get column information about
    '''
    names, types, primary_keys = [], [], []
    if dbtype=='sqlite':
        for column in cursor.execute('pragma table_info(' + \
            table_name + ')').fetchall():
            names.append(str(column[1]))
            if "INT" in column[2]:
                types.append(np.int64)
            else:
                types.append(numpy_type(column[2]))
            if column[5] == 1:
                primary_keys.append(str(column[1]))
    elif dbtype=='mysql':
        cursor.execute('DESCRIBE ' + table_name)
        for column in cursor:
            types.append(numpy_type(column[1]))
            names.append(str(column[0]))
            if column[3] == 'PRI':
                primary_keys.append(str(column[0]))
    elif dbtype=='postgres':
        cursor.execute('SELECT * FROM ' + table_name + ' WHERE 1=0')
        for column in cursor.description:
            types.append(numpy_type(column[1]))
            names.append(str(column[0]))
    return names, types, primary_keys


def column_info_desc(dbtype, description, column_types_dict):

    names, types = [], []
    if dbtype=='sqlite':
        for column in description:
            names.append(column[0])
            types.append(column_types_dict[column[0]])
    elif dbtype=='mysql':
        for column in description:
            names.append(column[0])
            types.append(numpy_type(mysql_types[column[1]]))
    elif dbtype=='postgres':
        for column in description:
            names.append(column[0])
            types.append(numpy_type(column[1]))
    return names, types


def connect_database(dbtype, *args, **kwargs):
    '''
    Connect to a database and return a connection handle

    Required Arguments:

    *dbtype*: [ 'sqlite' | 'mysql' | 'postgres' ]
        The type of database

    All other arguments are passed to the relevant modules, specifically:
        - sqlite3.connect() for SQLite
        - MySQLdb.connect() for MySQL
        - pgdb.connect() for PostgreSQL
    '''
    if dbtype == 'sqlite':
        connection = sqlite3.connect(*args, **kwargs)
    elif dbtype == 'mysql':
        _check_MySQLdb_installed()
        connection = MySQLdb.connect(*args, **kwargs)
    elif dbtype == 'postgres':
        _check_PyGreSQL_installed()
        connection = pgdb.connect(*args, **kwargs)
    else:
        raise Exception('dbtype should be one of sqlite/mysql/postgres')
    cursor = connection.cursor()
    return connection, cursor


def drop_table(cursor, table_name):
    '''
    Drop a table form a given SQL database

    Required Arguments:

        *cursor*: [ DB API cursor object ]
            A cursor for the current database in the DB API formalism

        *table_name*: [ string ]
            The name of the table to get column information about
    '''
    cursor.execute('DROP TABLE ' + table_name + ';')
    return


def create_table(cursor, dbtype, table_name, columns, primary_key=None):
    '''
    Create a table in an SQL database

    Required Arguments:

        *cursor*: [ DB API cursor object ]
            A cursor for the current database in the DB API formalism

        *dbtype*: [ 'sqlite' | 'mysql' | 'postgres' ]
            The type of database

        *table_name*: [ string ]
            The name of the table to get column information about

        *columns*: [ list of tuples ]
            The names and types of all the columns

    Optional Arguments:

        *primary_key* [ string ]
            The column to use as a primary key
    '''

    query = 'create table ' + table_name + ' ('

    for i, column in enumerate(columns):
        if i > 0:
            query += ", "
        column_name = column[0]
        column_type = type_dict[column[1]]

        # PostgreSQL does not support TINYINT
        if dbtype == 'postgres' and column_type == 'TINYINT':
            column_type = 'SMALLINT'

        # PostgreSQL does not support unsigned integers
        if dbtype == 'postgres':
            if column[1] == np.uint16:
                warnings.warn("uint16 unsupported - converting to int32")
                column_type = type_dict[np.int32]
            elif column[1] == np.uint32:
                warnings.warn("uint32 unsupported - converting to int64")
                column_type = type_dict[np.int64]
            elif column[1] == np.uint64:
                raise Exception("uint64 unsupported")

        # MySQL can take an UNSIGNED attribute
        if dbtype == 'mysql' and column[1] in [np.uint8, np.uint16, np.uint32, np.uint64]:
            column_type += " UNSIGNED"

        # SQLite only has one integer type
        if dbtype == 'sqlite' and "INT" in column_type:
            column_type = "INTEGER"

        # SQLite doesn't support uint64
        if dbtype == 'sqlite' and column[1] == np.uint64:
            raise Exception("SQLite tables do not support unsigned 64-bit ints")

        if dbtype == 'postgres' and column[1] == np.float32:
            column_type = "REAL"

        query += quote[dbtype] + column_name + quote[dbtype] + " " + \
            column_type

    if primary_key:
        query += ", PRIMARY KEY (%s%s%s)" % \
                 (quote[dbtype],primary_key,quote[dbtype])

    query += ")"

    cursor.execute(query)

    return


def insert_row(cursor, dbtype, table_name, row, fixnan=False):
    '''
    Insert a row into an SQL database (assumes all columns are specified)

    Required Arguments:

        *cursor*: [ DB API cursor object ]
            A cursor for the current database in the DB API formalism

        *dbtype*: [ 'sqlite' | 'mysql' | 'postgres' ]
            The type of database

        *table_name*: [ string ]
            The name of the table to get column information about

        *row*: [ tuple ]
            A tuple containing all the values to insert into the row
    '''
    query = 'insert into ' + table_name + ' values ('
    query += (insert_symbol[dbtype] + ', ') * (len(row) - 1)
    query += insert_symbol[dbtype] + ")"

    if fixnan:
        if dbtype=='postgres':
            for i,e in enumerate(row):
                if type(e) == float:
                    if math.isnan(e):
                        row[i] = str(e)
        elif dbtype=='mysql':
            for i,e in enumerate(row):
                if type(e) == float:
                    if math.isnan(e):
                        row[i] = None

    cursor.execute(query, row)
    return

########NEW FILE########
__FILENAME__ = sqltable
from __future__ import print_function, division

# NOTE: docstring is long and so only written once!
#       It is copied for the other routines

import warnings

import numpy as np

from . import sqlhelper as sql
from .exceptions import TableException, ExistingTableException

invalid = {}
invalid[np.uint8] = np.iinfo(np.uint8).max
invalid[np.uint16] = np.iinfo(np.uint16).max
invalid[np.uint32] = np.iinfo(np.uint32).max
invalid[np.uint64] = np.iinfo(np.int64).max
invalid[np.int8] = np.iinfo(np.int8).max
invalid[np.int16] = np.iinfo(np.int16).max
invalid[np.int32] = np.iinfo(np.int32).max
invalid[np.int64] = np.iinfo(np.int64).max
invalid[np.float32] = np.float32(np.nan)
invalid[np.float64] = np.float64(np.nan)


def read(self, dbtype, *args, **kwargs):
    '''
    Required Arguments:

        *dbtype*: [ 'sqlite' | 'mysql' | 'postgres' ]
            The SQL database type

    Optional arguments (only for Table.read() class):

        *table*: [ string ]
            The name of the table to read from the database (this is only
            required if there are more than one table in the database). This
            is not required if the query= argument is specified, except if
            using an SQLite database.

        *query*: [ string ]
            An arbitrary SQL query to construct a table from. This can be
            any valid SQL command provided that the result is a single
            table.

    The remaining arguments depend on the database type:

    * SQLite:

        Arguments are passed to sqlite3.connect(). For a full list of
        available arguments, see the help page for sqlite3.connect(). The
        main arguments are listed below.

        Required arguments:

            *dbname*: [ string ]
                The name of the database file

    * MySQL:

        Arguments are passed to MySQLdb.connect(). For a full list of
        available arguments, see the documentation for MySQLdb. The main
        arguments are listed below.

        Optional arguments:

            *host*: [ string ]
                The host to connect to (default is localhost)

            *user*: [ string ]
                The user to conenct as (default is current user)

            *passwd*: [ string ]
                The user password (default is blank)

            *db*: [ string ]
                The name of the database to connect to (no default)

            *port* [ integer ]
                The port to connect to (default is 3306)

    * PostGreSQL:

        Arguments are passed to pgdb.connect(). For a full list of
        available arguments, see the help page for pgdb.connect(). The
        main arguments are listed below.

        *host*: [ string ]
            The host to connect to (default is localhost)

        *user*: [ string ]
            The user to conenct as (default is current user)

        *password*: [ string ]
            The user password (default is blank)

        *database*: [ string ]
            The name of the database to connect to (no default)
    '''

    if 'table' in kwargs:
        table = kwargs.pop('table')
    else:
        table = None

    if 'verbose' in kwargs:
        verbose = kwargs.pop('verbose')
    else:
        verbose = True

    if 'query' in kwargs:
        query = kwargs.pop('query')
    else:
        query = None

    # Erase existing content
    self.reset()

    connection, cursor = sql.connect_database(dbtype, *args, **kwargs)

    # If no table is requested, check that there is only one table

    table_names = sql.list_tables(cursor, dbtype)

    if len(table_names) == 0:
        raise Exception("No table in selected database")

    if not query or dbtype == 'sqlite':

        if table==None:
            if len(table_names) == 1:
                table_name = table_names.keys()[0]
            else:
                raise TableException(table_names, 'table')
        else:
            table_name = table_names[table]

        # Find overall names and types for the table
        column_names, column_types, primary_keys = sql.column_info(cursor, dbtype, \
            str(table_name))

        self.table_name = table_name

    else:

        column_names = []
        column_types = []
        primary_keys = []

        self.table_name = "sql_query"

    if query:

        # Execute the query
        cursor.execute(query)

        if dbtype == 'sqlite':
            column_types_dict = dict(zip(column_names, column_types))
        else:
            column_types_dict = None

        # Override column names and types
        column_names, column_types = sql.column_info_desc(dbtype, cursor.description, column_types_dict)

    else:

        cursor = connection.cursor()

        cursor.execute('select * from ' + table_name)

    results = cursor.fetchall()

    if results:
        results = np.rec.fromrecords(list(results), \
                        names = column_names)
    else:
        raise Exception("SQL query did not return any records")

    for i, column in enumerate(results.dtype.names):

        if self._masked:

            if results[column].dtype.type == np.object_:
                mask = np.equal(results[column], None)
                if column_types[i] == np.str:
                    results[column][mask] = "NULL"
                else:
                    results[column][mask] = 0.
                mask = mask.astype(np.object_)
            else:
                mask = None

            self.add_column(column, results[column], dtype=column_types[i], mask=mask)

        else:

            if column_types[i] in invalid:
                null = invalid[column_types[i]]
                results[column][np.equal(np.array(results[column], dtype=np.object), None)] = null
            else:
                null = 'None'

            self.add_column(column, results[column], dtype=column_types[i], null=null)

    # Set primary key if present
    if len(primary_keys) == 1:
        self.set_primary_key(primary_keys[0])
    elif len(primary_keys) > 1:
        warnings.warn("ATpy does not yet support multiple primary keys in a single table - ignoring primary key information")


def write(self, dbtype, *args, **kwargs):

    self._raise_vector_columns()

    # Check if table overwrite is requested
    if 'overwrite' in kwargs:
        overwrite = kwargs.pop('overwrite')
    else:
        overwrite = False

    # Open the connection
    connection, cursor = sql.connect_database(dbtype, *args, **kwargs)

    # Check that table name is set
    if not self.table_name:
        raise Exception("Table name is not set")
    else:
        table_name = str(self.table_name)

    # Check that table name is ok
    # todo

    # lowercase because pgsql automatically converts
    # table names to lower case

    # Check if table already exists

    existing_tables = sql.list_tables(cursor, dbtype).values()
    if table_name in existing_tables or \
        table_name.lower() in existing_tables:
        if overwrite:
            sql.drop_table(cursor, table_name)
        else:
            raise ExistingTableException()

    # Create table
    columns = [(name, self.columns[name].dtype.type) \
                                        for name in self.names]
    sql.create_table(cursor, dbtype, table_name, columns, primary_key=self._primary_key)


    # Insert row
    float_column = [self.columns[name].dtype.type in [np.float32, np.float64] for name in self.names]

    for i in range(self.__len__()):
        row = self.row(i, python_types=True)

        sql.insert_row(cursor, dbtype, table_name, row, fixnan=not self._masked)

    # Close connection
    connection.commit()
    cursor.close()

write.__doc__ = read.__doc__


def read_set(self, dbtype, *args, **kwargs):

    self.reset()

    connection, cursor = sql.connect_database(dbtype, *args, **kwargs)
    table_names = sql.list_tables(cursor, dbtype)
    cursor.close()

    from .basetable import Table
    for table in table_names:
        kwargs['table'] = table
        table = Table()
        read(table, dbtype, *args, **kwargs)
        self.append(table)

read_set.__doc__ = read.__doc__


def write_set(self, dbtype, *args, **kwargs):

    for table_key in self.tables:
        write(self.tables[table_key], dbtype, *args, **kwargs)

write_set.__doc__ = write.__doc__

########NEW FILE########
__FILENAME__ = structhelper
from __future__ import print_function, division

import numpy as np
import numpy.ma as ma


def append_field(sta, data, dtype=None, position=None, masked=False):

    newdtype = sta.dtype.descr
    if np.equal(position, None):
        newdtype.append(dtype)
    else:
        newdtype.insert(position, dtype)
    newdtype = np.dtype(newdtype)

    if masked:
        newsta = ma.empty(sta.shape, dtype=newdtype)
    else:
        newsta = np.empty(sta.shape, dtype=newdtype)

    for field in sta.dtype.fields:
        newsta[field] = sta[field]
        if masked:
            newsta[field].set_fill_value(sta[field].fill_value)

    newsta[dtype[0]] = data
    if masked:
        newsta[dtype[0]].set_fill_value(data.fill_value)

    return newsta


def drop_fields(sta, names, masked=False):

    names = set(names)

    newdtype = np.dtype([(name, sta.dtype[name]) for name in sta.dtype.names
                       if name not in names])

    if newdtype:
        if masked:
            newsta = ma.empty(sta.shape, dtype=newdtype)
        else:
            newsta = np.empty(sta.shape, dtype=newdtype)
    else:
        return None

    for field in newdtype.fields:
        newsta[field] = sta[field]
        if masked:
            newsta[field].set_fill_value(sta[field].fill_value)

    return newsta

########NEW FILE########
__FILENAME__ = test_io
from __future__ import division

import unittest
import string
import random
import sys
import tempfile

import numpy as np
np.seterr(all='ignore')

import pytest
from astropy.tests.helper import pytest
from astropy.utils.misc import NumpyRNGContext

from .. import Table

# Size of the test table
shape = (100, )
shape_vector = (100, 10)


def random_int_array(dtype, shape):
    random.seed('integer')
    n = np.product(shape)
    n = n * np.iinfo(dtype).bits // 8
    if sys.version_info[0] > 2:
        s = bytes([random.randrange(0, 256) for i in range(n)])
    else:
        s = "".join(chr(random.randrange(0, 256)) for i in range(n))
    return np.fromstring(s, dtype=dtype).reshape(shape)


def random_float_array(dtype, shape):
    random.seed('float')
    n = np.product(shape)
    if dtype == np.float32:
        n = n * 4
    else:
        n = n * 8
    if sys.version_info[0] > 2:
        s = bytes([random.randrange(0, 256) for i in range(n)])
    else:
        s = "".join(chr(random.randrange(0, 256)) for i in range(n))
    array = np.fromstring(s, dtype=dtype)
    if np.sum(np.isnan(array)):
        array[np.isnan(array)] = random_float_array(dtype, array[np.isnan(array)].shape)
    return array.reshape(shape)


numpy_types = [np.bool, np.int8, np.int16, np.int32, np.int64, np.uint8,
               np.uint16, np.uint32, np.uint64, np.float32, np.float64,
               np.dtype('|S100')]


def random_generic(dtype, name, shape):

    random.seed('generic')

    if 'int' in name:
        values = random_int_array(dtype, shape)
    elif 'float' in name:
        values = random_float_array(dtype, shape)
    elif 'bool' in name:
        with NumpyRNGContext(12345):
            values = np.random.random(shape) > 0.5
    else:
        values = np.zeros(shape, dtype=dtype)
        for i in range(shape[0]):
            s = ""
            for k in range(dtype.itemsize):
                s += random.choice(string.ascii_letters + string.digits)
            values[i] = s

    return values


def generate_simple_table(dtype, shape):

    table = Table(name='atpy_test')

    try:
        name = dtype.__name__
    except:
        name = dtype.type.__name__

    if name == 'bytes_':
        name = 'string_'

    values = random_generic(dtype, name, shape)

    table.add_column('col_' + name, values, dtype=dtype)

    return table


class ColumnsDefaultTestCase():

    def test_bool(self):
        self.generic_test(np.bool_)

    def test_uint8(self):
        self.generic_test(np.uint8)

    def test_uint16(self):
        self.generic_test(np.uint16)

    def test_uint32(self):
        self.generic_test(np.uint32)

    def test_uint64(self):
        self.generic_test(np.uint64)

    def test_int8(self):
        self.generic_test(np.int8)

    def test_int16(self):
        self.generic_test(np.int16)

    def test_int32(self):
        self.generic_test(np.int32)

    def test_int64(self):
        self.generic_test(np.int64)

    def test_float32(self):
        self.generic_test(np.float32)

    def test_float64(self):
        self.generic_test(np.float64)

    def test_string(self):
        self.generic_test(np.dtype('|S100'))


class EmptyColumnsTestCase(unittest.TestCase, ColumnsDefaultTestCase):

    def generic_test(self, dtype):
        try:
            t = Table()
            t.add_empty_column('a', dtype, shape=shape)
            t.add_empty_column('b', dtype)
            t.add_empty_column('c', dtype)
        except:
            self.fail(sys.exc_info()[1])


class EmptyVectorColumnsTestCase(unittest.TestCase, ColumnsDefaultTestCase):

    def generic_test(self, dtype):
        try:
            t = Table()
            t.add_empty_column('a', dtype, shape=shape_vector)
            t.add_empty_column('b', dtype)
            t.add_empty_column('c', dtype, shape=shape_vector)
        except:
            self.fail(sys.exc_info()[1])


class DefaultTestCase():

    def assertAlmostEqualSig(test, first, second, significant=7, msg=None):
        ratio = first / second
        if np.abs(ratio - 1.) > 10. ** (-significant + 1):
            raise unittest.TestCase.failureException(msg or '%r != %r within %r significant digits' % (first, second, significant))

    def integer_test(self, dtype):
        colname = 'col_%s' % dtype.__name__
        self.writeread(dtype)
        before, after = self.table_orig.data[colname], self.table_new.data[colname]
        self.assertEqual(before.shape, after.shape)
        if before.ndim == 1:
            for i in range(before.shape[0]):
                self.assertEqual(before[i], after[i])
        else:
            for i in range(before.shape[0]):
                for j in range(before.shape[1]):
                    self.assertEqual(before[i, j], after[i, j])

    def test_bool(self):
        self.integer_test(np.bool_)

    def test_uint8(self):
        self.integer_test(np.uint8)

    def test_uint16(self):
        self.integer_test(np.uint16)

    def test_uint32(self):
        self.integer_test(np.uint32)

    def test_uint64(self):
        self.integer_test(np.uint64)

    def test_int8(self):
        self.integer_test(np.int8)

    def test_int16(self):
        self.integer_test(np.int16)

    def test_int32(self):
        self.integer_test(np.int32)

    def test_int64(self):
        self.integer_test(np.int64)

    def float_test(self, dtype, significant=None):
        colname = 'col_%s' % dtype.__name__
        self.writeread(dtype)
        before, after = self.table_orig.data[colname], self.table_new.data[colname]
        self.assertEqual(before.shape, after.shape)
        self.assertEqual(before.dtype.type, after.dtype.type)
        if before.ndim == 1:
            for i in range(before.shape[0]):
                if(np.isnan(before[i])):
                    self.failUnless(np.isnan(after[i]))
                elif(np.isinf(before[i])):
                    self.failUnless(np.isinf(after[i]))
                else:
                    if significant:
                        self.assertAlmostEqualSig(before[i], after[i], significant=significant)
                    else:
                        self.assertEqual(before[i], after[i])
        else:
            for i in range(before.shape[0]):
                for j in range(before.shape[1]):
                    if(np.isnan(before[i, j])):
                        self.failUnless(np.isnan(after[i, j]))
                    elif(np.isinf(before[i, j])):
                        self.failUnless(np.isinf(after[i, j]))
                    else:
                        if significant:
                            self.assertAlmostEqualSig(before[i, j], after[i, j], significant=significant)
                        else:
                            self.assertEqual(before[i, j], after[i, j])

    def test_float32(self):
        if self.format == 'mysql':
            self.float_test(np.float32, significant=6)
        elif self.format == 'postgres':
            self.float_test(np.float32, significant=6)
        else:
            self.float_test(np.float32)

    def test_float64(self):
        if self.format == 'mysql':
            self.float_test(np.float64, significant=15)
        elif self.format == 'postgres':
            self.float_test(np.float64, significant=12)
        else:
            self.float_test(np.float64)

    def test_string(self):
        self.writeread(np.dtype('|S100'))
        before, after = self.table_orig.data['col_string_'], self.table_new.data['col_string_']
        self.assertEqual(before.shape, after.shape)
        for i in range(len(self.table_orig)):
            if type(before[i]) == type(after[i]):
                self.assertEqual(before[i], after[i])
            elif type(before[i]) == np.bytes_:
                self.assertEqual(before[i], after[i].encode('utf-8'))
            else:
                self.assertEqual(before[i].encode('utf-8'), after[i])


class TestFITS(unittest.TestCase, DefaultTestCase):

    format = 'fits'

    test_uint64 = None  # unsupported

    def writeread(self, dtype):

        filename = tempfile.mktemp(suffix='.fits')

        self.table_orig = generate_simple_table(dtype, shape)
        self.table_orig.write(filename, verbose=False, overwrite=True)
        self.table_new = Table(filename, verbose=False)


class TestFITSVector(unittest.TestCase, DefaultTestCase):

    format = 'fits'

    test_string = None  # unsupported
    test_uint64 = None  # unsupported

    def writeread(self, dtype):

        filename = tempfile.mktemp(suffix='.fits')

        self.table_orig = generate_simple_table(dtype, shape_vector)
        self.table_orig.write(filename, verbose=False, overwrite=True)
        self.table_new = Table(filename, verbose=False)


class TestHDF5(unittest.TestCase, DefaultTestCase):

    format = 'hdf5'

    def writeread(self, dtype):

        try:
            import h5py
        except ImportError:
            pytest.skip()

        filename = tempfile.mktemp(suffix='.hdf5')

        self.table_orig = generate_simple_table(dtype, shape)
        self.table_orig.write(filename, verbose=False, overwrite=True)
        self.table_new = Table(filename, verbose=False)


class TestHDF5Vector(unittest.TestCase, DefaultTestCase):

    format = 'hdf5'

    test_string = None  # unsupported

    def writeread(self, dtype):

        try:
            import h5py
        except ImportError:
            pytest.skip()

        filename = tempfile.mktemp(suffix='.hdf5')

        self.table_orig = generate_simple_table(dtype, shape_vector)
        self.table_orig.write(filename, verbose=False, overwrite=True)
        self.table_new = Table(filename, verbose=False)


class TestVO(unittest.TestCase, DefaultTestCase):

    format = 'vo'

    test_uint64 = None  # unsupported

    def writeread(self, dtype):

        filename = tempfile.mktemp(suffix='.xml')

        self.table_orig = generate_simple_table(dtype, shape)
        self.table_orig.write(filename, verbose=False, overwrite=True)
        self.table_new = Table(filename, verbose=False)


class TestVOVector(unittest.TestCase, DefaultTestCase):

    format = 'vo'

    test_string = None  # unsupported
    test_uint64 = None  # unsupported

    def writeread(self, dtype):

        filename = tempfile.mktemp(suffix='.xml')

        self.table_orig = generate_simple_table(dtype, shape_vector)
        self.table_orig.write(filename, verbose=False, overwrite=True)
        self.table_new = Table(filename, verbose=False)


class TestIPAC(unittest.TestCase, DefaultTestCase):

    format = 'ipac'

    def writeread(self, dtype):

        filename = tempfile.mktemp(suffix='.tbl')

        self.table_orig = generate_simple_table(dtype, shape)
        self.table_orig.write(filename, verbose=False, overwrite=True)
        self.table_new = Table(filename, verbose=False)


class TestSQLite(unittest.TestCase, DefaultTestCase):

    format = 'sqlite'

    test_uint64 = None  # unsupported

    def writeread(self, dtype):

        filename = tempfile.mktemp(suffix='.db')

        self.table_orig = generate_simple_table(dtype, shape)
        self.table_orig.write('sqlite', filename, verbose=False, overwrite=True)
        self.table_new = Table('sqlite', filename, verbose=False)


class TestSQLiteQuery(unittest.TestCase, DefaultTestCase):

    format = 'sqlite'

    test_uint64 = None  # unsupported

    def writeread(self, dtype):

        filename = tempfile.mktemp(suffix='.db')

        self.table_orig = generate_simple_table(dtype, shape)
        self.table_orig.write('sqlite', filename, verbose=False, overwrite=True)
        self.table_new = Table('sqlite', filename, verbose=False, query='select * from atpy_test')


# SQL connection parameters
USERNAME = "testuser"
PASSWORD = "testpassword"


class MySQLTestCase(unittest.TestCase, DefaultTestCase):

    format = 'mysql'

    test_uint64 = None # unsupported

    def writeread(self, dtype):

        try:
            import MySQLdb
        except ImportError:
            pytest.skip()

        self.table_orig = generate_simple_table(dtype, shape)
        self.table_orig.write('mysql', db='python', overwrite=True, verbose=False, user=USERNAME, passwd=PASSWORD)
        self.table_new = Table('mysql', db='python', verbose=False, user=USERNAME, passwd=PASSWORD, table='atpy_test')


class MySQLTestCaseQuery(unittest.TestCase, DefaultTestCase):

    format = 'mysql'

    test_uint8 = None # unsupported
    test_uint16 = None # unsupported
    test_uint32 = None # unsupported
    test_uint64 = None # unsupported

    def writeread(self, dtype):

        try:
            import MySQLdb
        except ImportError:
            pytest.skip()

        self.table_orig = generate_simple_table(dtype, shape)
        self.table_orig.write('mysql', db='python', overwrite=True, verbose=False, user=USERNAME, passwd=PASSWORD)
        self.table_new = Table('mysql', db='python', verbose=False, user=USERNAME, passwd=PASSWORD, query='select * from atpy_test')


class PostGreSQLTestCase(unittest.TestCase, DefaultTestCase):

    format = 'postgres'

    test_uint64 = None # unsupported

    def writeread(self, dtype):

        try:
            import pgdb
        except ImportError:
            pytest.skip()

        self.table_orig = generate_simple_table(dtype, shape)
        self.table_orig.write('postgres', database='python', overwrite=True, verbose=False, user=USERNAME, password=PASSWORD)
        self.table_new = Table('postgres', database='python', verbose=False, user=USERNAME, password=PASSWORD, table='atpy_test')


class PostGreSQLTestCaseQuery(unittest.TestCase, DefaultTestCase):

    format = 'postgres'

    test_uint64 = None # unsupported

    def writeread(self, dtype):

        try:
            import pgdb
        except ImportError:
            pytest.skip()

        self.table_orig = generate_simple_table(dtype, shape)
        self.table_orig.write('postgres', database='python', overwrite=True, verbose=False, user=USERNAME, password=PASSWORD)
        self.table_new = Table('postgres', database='python', verbose=False, user=USERNAME, password=PASSWORD, query='select * from atpy_test')

########NEW FILE########
__FILENAME__ = version
__version__ = '0.9.7'

########NEW FILE########
__FILENAME__ = votable
from __future__ import print_function, division

import os
import numpy as np
import warnings

from astropy.io.votable import parse
from astropy.io.votable.tree import VOTableFile, Resource, Field, Param
from astropy.io.votable.tree import Table as VOTable

from .exceptions import TableException
from .helpers import smart_dtype
from .decorators import auto_download_to_file, auto_decompress_to_fileobj, auto_fileobj_to_file

# Define type conversion dictionary
type_dict = {}
type_dict[np.bool_] = "boolean"

type_dict[np.uint8] = "unsignedByte"
type_dict[np.int16] = "short"
type_dict[np.int32] = "int"
type_dict[np.int64] = "long"

type_dict[np.float32] = "float"
type_dict[np.float64] = "double"
type_dict[np.str] = "char"
type_dict[np.string_] = "char"
type_dict[str] = "char"


def _list_tables(filename, pedantic=False):
    votable = parse(filename, pedantic=pedantic)
    tables = {}
    for i, table in enumerate(votable.iter_tables()):
        tables[i] = table.name
    return tables


# VO can handle file objects, but because we need to read it twice we don't
# use that capability
@auto_download_to_file
@auto_decompress_to_fileobj
@auto_fileobj_to_file
def read(self, filename, pedantic=False, tid=-1, verbose=True):
    '''
    Read a table from a VOT file

    Required Arguments:

        *filename*: [ string ]
            The VOT file to read the table from

    Optional Keyword Arguments:

        *tid*: [ integer ]
            The ID of the table to read from the VO file (this is
            only required if there are more than one table in the VO file)

        *pedantic*: [ True | False ]
            When *pedantic* is True, raise an error when the file violates
            the VO Table specification, otherwise issue a warning.
    '''

    self.reset()

    # If no table is requested, check that there is only one table
    if tid==-1:
        tables = _list_tables(filename, pedantic=pedantic)
        if len(tables) == 1:
            tid = 0
        elif len(tables) == 0:
            raise Exception("There are no tables present in this file")
        else:
            raise TableException(tables, 'tid')

    votable = parse(filename, pedantic=pedantic)
    for id, table in enumerate(votable.iter_tables()):
        if id==tid:
            break

    if table.ID:
        self.table_name = str(table.ID)
    elif table.name:
        self.table_name = str(table.name)

    for field in table.fields:

        colname = field.ID

        if table.array.size:
            data = table.array[colname]
        else:
            data = np.array([], dtype=field.converter.format)

        if len(data) > 0 and data.ndim == 1 and not np.all([np.isscalar(x) for x in data]):
            warnings.warn("VO Variable length vector column detected (%s) - converting to string" % colname)
            data = np.array([str(x) for x in data])

        if self._masked:
            self.add_column(str(colname), np.array(data), \
                unit=field.unit, mask=data.mask[colname], \
                description=field.description)
        else:
            self.add_column(str(colname), np.array(data),
                unit=field.unit, description=field.description)

    for param in table.params:
        self.add_keyword(param.ID, param.value)


def _to_table(self, vo_table):
    '''
    Return the current table as a VOT object
    '''

    table = VOTable(vo_table)

    # Add keywords
    for key in self.keywords:
        if isinstance(self.keywords[key], basestring):
            arraysize = '*'
        else:
            arraysize = None
        param = Param(table, name=key, ID=key, value=self.keywords[key], arraysize=arraysize)
        table.params.append(param)

    # Define some fields

    n_rows = len(self)

    fields = []
    for i, name in enumerate(self.names):

        data = self.data[name]
        unit = self.columns[name].unit
        description = self.columns[name].description
        dtype = self.columns[name].dtype
        column_type = smart_dtype(dtype)

        if data.ndim > 1:
            arraysize = str(data.shape[1])
        else:
            arraysize = None

        if column_type in type_dict:
            datatype = type_dict[column_type]
        elif column_type == np.int8:
            warnings.warn("int8 unsupported - converting to int16")
            datatype = type_dict[np.int16]
        elif column_type == np.uint16:
            warnings.warn("uint16 unsupported - converting to int32")
            datatype = type_dict[np.int32]
        elif column_type == np.uint32:
            warnings.warn("uint32 unsupported - converting to int64")
            datatype = type_dict[np.int64]
        elif column_type == np.uint64:
            raise Exception("uint64 unsupported")
        else:
            raise Exception("cannot use numpy type " + str(column_type))

        if column_type == np.float32:
            precision = 'E9'
        elif column_type == np.float64:
            precision = 'E17'
        else:
            precision = None

        if datatype == 'char':
            if arraysize is None:
                arraysize = '*'
            else:
                raise ValueError("Cannot write vector string columns to VO files")

        field = Field(vo_table, ID=name, name=name, \
                datatype=datatype, unit=unit, arraysize=arraysize, \
                precision=precision)

        field.description = description

        fields.append(field)

    table.fields.extend(fields)

    table.create_arrays(n_rows)

    # Character columns are stored as object columns in the vo_table
    # instance. Leaving the type as string should work, but causes
    # a segmentation fault on MacOS X with Python 2.6 64-bit so
    # we force the conversion to object type columns.

    for name in self.names:

        dtype = self.columns[name].dtype
        column_type = smart_dtype(dtype)

        # Add data to the table
        # At the moment, null values in VO table are dealt with via a
        # 'mask' record array

        if column_type == np.string_:
            table.array[name] = self.data[name].astype(np.object_)
            if self._masked:
                table.array.mask[name] = self.data[name].mask.astype(np.object_)
            else:
                if self.data[name].dtype.type == np.bytes_ and type(self.columns[name].null) != bytes:
                    table.array.mask[name] = (self.data[name] == \
                                self.columns[name].null.encode('utf-8')).astype(np.object_)
                else:
                    table.array.mask[name] = (self.data[name] == \
                                self.columns[name].null).astype(np.object_)
        else:
            table.array[name] = self.data[name]
            if self._masked:
                table.array.mask[name] = self.data[name].mask
            else:
                table.array.mask[name] = self.data[name] == \
                                        self.columns[name].null

    table.name = self.table_name

    return table


def write(self, filename, votype='ascii', overwrite=False):
    '''
    Write the table to a VOT file

    Required Arguments:

        *filename*: [ string ]
            The VOT file to write the table to

    Optional Keyword Arguments:

        *votype*: [ 'ascii' | 'binary' ]
            Whether to write the table as ASCII or binary
    '''

    if os.path.exists(filename):
        if overwrite:
            os.remove(filename)
        else:
            raise Exception("File exists: %s" % filename)

    vo_table = VOTableFile()
    resource = Resource()
    vo_table.resources.append(resource)

    resource.tables.append(_to_table(self, vo_table))

    if votype is 'binary':
        vo_table.get_first_table().format = 'binary'
        vo_table.set_all_tables_format('binary')

    vo_table.to_xml(filename)


# VO can handle file objects, but because we need to read it twice we don't
# use that capability
@auto_download_to_file
@auto_decompress_to_fileobj
@auto_fileobj_to_file
def read_set(self, filename, pedantic=False, verbose=True):
    '''
    Read all tables from a VOT file

    Required Arguments:

        *filename*: [ string ]
            The VOT file to read the tables from

    Optional Keyword Arguments:

        *pedantic*: [ True | False ]
            When *pedantic* is True, raise an error when the file violates
            the VO Table specification, otherwise issue a warning.
    '''

    self.reset()

    from .basetable import Table
    for tid in _list_tables(filename, pedantic=pedantic):
        t = Table()
        read(t, filename, tid=tid, verbose=verbose, pedantic=pedantic)
        self.append(t)


def write_set(self, filename, votype='ascii', overwrite=False):
    '''
    Write all tables to a VOT file

    Required Arguments:

        *filename*: [ string ]
            The VOT file to write the tables to

    Optional Keyword Arguments:

        *votype*: [ 'ascii' | 'binary' ]
            Whether to write the tables as ASCII or binary tables
    '''

    if os.path.exists(filename):
        if overwrite:
            os.remove(filename)
        else:
            raise Exception("File exists: %s" % filename)

    vo_table = VOTableFile()
    resource = Resource()
    vo_table.resources.append(resource)

    for table_key in self.tables:
        resource.tables.append(_to_table(self.tables[table_key], vo_table))

    if votype is 'binary':
        vo_table.get_first_table().format = 'binary'
        vo_table.set_all_tables_format('binary')

    vo_table.to_xml(filename)

########NEW FILE########
__FILENAME__ = vo_conesearch
from __future__ import print_function, division

from distutils import version
import warnings
import tempfile

vo_minimum_version = version.LooseVersion('0.3')

try:
    import vo.conesearch as vcone
    vo_installed = True
except:
    vo_installed = False

def _check_vo_installed():
    if not vo_installed:
        raise Exception("Cannot query the VO - vo " +  \
            vo_minimum_version.vstring + " or later required")


def read(self, catalog=None, ra=None, dec=None, radius=None, verb=1,
         pedantic=False, **kwargs):
    '''

    Query a VO catalog using the STScI vo module

    This docstring has been adapted from the STScI vo conesearch module:

        *catalog* [ None | string | VOSCatalog | list ]

            May be one of the following, in order from easiest to use to most
            control:

            - None: A database of conesearch catalogs is downloaded from
              STScI. The first catalog in the database to successfully return
              a result is used.

            - catalog name: A name in the database of conesearch catalogs at
              STScI is used. For a list of acceptable names, see
              vo_conesearch.list_catalogs().

            - url: The prefix of a url to a IVOA Cone Search Service. Must end
              in either ? or &.

            - A VOSCatalog instance: A specific catalog manually downloaded
              and selected from the database using the APIs in the
              STScI vo.vos_catalog module.

            - Any of the above 3 options combined in a list, in which case
              they are tried in order.

        *pedantic* [ bool ]
            When pedantic is True, raise an error when the returned VOTable
            file violates the spec, otherwise issue a warning.

        *ra* [ float ]
            A right-ascension in the ICRS coordinate system for the position
            of the center of the cone to search, given in decimal degrees.

        *dec* [ float ]
            A declination in the ICRS coordinate system for the position of
            the center of the cone to search, given in decimal degrees.

        *radius* [ float]
            The radius of the cone to search, given in decimal degrees.

        *verb* [ int ]
            Verbosity, 1, 2, or 3, indicating how many columns are to be
            returned in the resulting table. Support for this parameter by a
            Cone Search service implementation is optional. If the service
            supports the parameter, then when the value is 1, the response
            should include the bare minimum of columns that the provider
            considers useful in describing the returned objects. When the
            value is 3, the service should return all of the columns that are
            available for describing the objects. A value of 2 is intended for
            requesting a medium number of columns between the minimum and
            maximum (inclusive) that are considered by the provider to most
            typically useful to the user. When the verb parameter is not
            provided, the server should respond as if verb = 2. If the verb
            parameter is not supported by the service, the service should
            ignore the parameter and should always return the same columns for
            every request.

        Additional keyword arguments may be provided to pass along to the
        server. These arguments are specific to the particular catalog being
        queried.
    '''

    _check_vo_installed()

    self.reset()

    # Perform the cone search
    VOTable = vcone.conesearch(catalog_db=catalog, pedantic=pedantic,
                               ra=ra, dec=dec, sr=radius, verb=verb, **kwargs)

    # Write table to temporary file
    output = tempfile.NamedTemporaryFile()
    VOTable._votable.to_xml(output)
    output.flush()

    # Read it in using ATpy VO reader
    self.read(output.name, type='vo', verbose=False)

    # Check if table is empty
    if len(self) == 0:
        warnings.warn("Query returned no results, so the table will be empty")

    # Remove temporary file
    output.close()


def list_catalogs():

    _check_vo_installed()

    for catalog in vcone.list_catalogs():
        if "BROKEN" in catalog:
            continue
        print("%30s" % catalog)

########NEW FILE########
__FILENAME__ = conf
# -*- coding: utf-8 -*-
#
# ATpy documentation build configuration file, created by
# sphinx-quickstart on Sat May 16 15:55:54 2009.
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
#sys.path.append(os.path.abspath('.'))

# -- General configuration -----------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be extensions
# coming with Sphinx (named 'sphinx.ext.*') or your custom ones.
extensions = ['sphinx.ext.autodoc']

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# The suffix of source filenames.
source_suffix = '.rst'

# The encoding of source files.
#source_encoding = 'utf-8'

# The master toctree document.
master_doc = 'index'

# General information about the project.
project = u'ATpy'
copyright = u'2009-2013, Eli Bressert and Thomas Robitaille'

# The version info for the project you're documenting, acts as replacement for
# |version| and |release|, also used in various other places throughout the
# built documents.
#
# The short X.Y version.
version = '0.9'
# The full version, including alpha/beta/rc tags.
import atpy
release = atpy.__version__

# The language for content autogenerated by Sphinx. Refer to documentation
# for a list of supported languages.
#language = None

# There are two options for replacing |today|: either, you set today to some
# non-false value, then it is used:
#today = ''
# Else, today_fmt is used as the format for a strftime call.
#today_fmt = '%B %d, %Y'

# List of documents that shouldn't be included in the build.
#unused_docs = []

# List of directories, relative to source directory, that shouldn't be searched
# for source files.
exclude_trees = []

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

# The theme to use for HTML and HTML Help pages.  Major themes that come with
# Sphinx are currently 'default' and 'sphinxdoc'.
html_theme = 'sphinxdoc'

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
html_logo = "atpy_logo.png"

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
#html_use_modindex = True

# If false, no index is generated.
#html_use_index = True

# If true, the index is split into individual pages for each letter.
#html_split_index = False

# If true, links to the reST sources are added to the pages.
#html_show_sourcelink = True

# If true, an OpenSearch description file will be output, and all pages will
# contain a <link> tag referring to it.  The value of this option must be the
# base URL from which the finished HTML is served.
#html_use_opensearch = ''

# If nonempty, this is the file name suffix for HTML files (e.g. ".xhtml").
#html_file_suffix = ''

# Output file base name for HTML help builder.
htmlhelp_basename = 'ATpydoc'


# -- Options for LaTeX output --------------------------------------------------

# The paper size ('letter' or 'a4').
#latex_paper_size = 'letter'

# The font size ('10pt', '11pt' or '12pt').
#latex_font_size = '10pt'

# Grouping the document tree into LaTeX files. List of tuples
# (source start file, target name, title, author, documentclass [howto/manual]).
latex_documents = [
  ('contents', 'ATpy.tex', u'ATpy',
   u'Eli Bressert and Thomas Robitaille', 'manual'),
]

# The name of an image file (relative to this directory) to place at the top of
# the title page.
#latex_logo = None

# For "manual" documents, if this is true, then toplevel headings are parts,
# not chapters.
#latex_use_parts = False

# Additional stuff for the LaTeX preamble.
#latex_preamble = ''

# Documents to append as an appendix to all manuals.
#latex_appendices = []

# If false, no module index is generated.
#latex_use_modindex = True

########NEW FILE########
__FILENAME__ = runtests
#! /usr/bin/env python

sources = """
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
"""

import sys
import base64
import zlib
import imp

class DictImporter(object):
    def __init__(self, sources):
        self.sources = sources

    def find_module(self, fullname, path=None):
        if fullname in self.sources:
            return self
        if fullname + '.__init__' in self.sources:
            return self
        return None

    def load_module(self, fullname):
        # print "load_module:",  fullname
        from types import ModuleType
        try:
            s = self.sources[fullname]
            is_pkg = False
        except KeyError:
            s = self.sources[fullname + '.__init__']
            is_pkg = True

        co = compile(s, fullname, 'exec')
        module = sys.modules.setdefault(fullname, ModuleType(fullname))
        module.__file__ = "%s/%s" % (__file__, fullname)
        module.__loader__ = self
        if is_pkg:
            module.__path__ = [fullname]

        do_exec(co, module.__dict__)
        return sys.modules[fullname]

    def get_source(self, name):
        res = self.sources.get(name)
        if res is None:
            res = self.sources.get(name + '.__init__')
        return res

if __name__ == "__main__":
    if sys.version_info >= (3, 0):
        exec("def do_exec(co, loc): exec(co, loc)\n")
        import pickle
        sources = sources.encode("ascii") # ensure bytes
        sources = pickle.loads(zlib.decompress(base64.decodebytes(sources)))
    else:
        import cPickle as pickle
        exec("def do_exec(co, loc): exec co in loc\n")
        sources = pickle.loads(zlib.decompress(base64.decodestring(sources)))

    importer = DictImporter(sources)
    sys.meta_path.append(importer)

    entry = "import py; raise SystemExit(py.test.cmdline.main())"
    do_exec(entry, locals())

########NEW FILE########