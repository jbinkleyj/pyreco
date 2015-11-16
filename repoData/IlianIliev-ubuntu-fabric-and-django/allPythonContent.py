__FILENAME__ = mysql
""" Fabric task for MySQL. Have in note that this is Debian specific."""
from fabric.api import local, run, sudo, env, prompt
from fabric.context_managers import settings
from fabric.utils import warn

from db import DBTypeBase
from utils import generate_password, add_os_package


MYSQL_EXECUTABLE_PATH = '/usr/bin/mysql'

# On Debian based systems this file contains system user and password for mysql
MYSQL_DEFAULTS_CONF = '/etc/mysql/debian.cnf'
MYSQL_RUN_COMMAND = '%s --defaults-file=%s' % (MYSQL_EXECUTABLE_PATH,
                                               MYSQL_DEFAULTS_CONF)

CREATE_DB_QUERY = """echo 'create database %s default character set utf8 collate utf8_general_ci'"""
CREATE_USER_QUERY = """echo 'CREATE USER "%s"@"localhost" identified by "%s"'"""
GRANT_PRIVILEGES_QUERY = """echo 'grant all privileges on %s.* to "%s"@"localhost"'"""


class DBType(DBTypeBase):
    def __init__(self, *args, **kwargs):
        self.engine = 'mysql'
        self.required_system_packages = ['libmysqlclient-dev']
        self.required_packages = ['MySQL-python']
        self.executable_path = MYSQL_EXECUTABLE_PATH

    def create_db(self, name):
        """ Creates database with given name """
        res_ex = None
        with settings(warn_only=True):
            result = sudo('%s | %s' % (CREATE_DB_QUERY, MYSQL_RUN_COMMAND) %
                          name)
        return not result.failed

    def create_user(self, dbname, username, password=None):
        if not password:
            password = generate_password()
        with settings(warn_only=True):
            result = sudo('%s | %s' % (CREATE_USER_QUERY, MYSQL_RUN_COMMAND) %
                          (username, password))
        return False if result.failed else password

    def grant_privileges(self, dbname, username):
        with settings(warn_only=True):
            result = sudo('%s | %s' % (GRANT_PRIVILEGES_QUERY,
                                       MYSQL_RUN_COMMAND) %
                          (dbname, username))
        return not result.failed

    def create_db_and_user(self, name):
        """ Creates database and user with the same name """
        if self.create_db(name):
            password = self.create_user(name, name)
            return password
        else:
            return False

    def install(self):
        if self.is_db_installed():
            print 'Database already installed'
            return
        password = generate_password()
        sudo('debconf-set-selections <<< "mysql-server-5.5 mysql-server/root_password password %s"' % password)
        sudo('debconf-set-selections <<< "mysql-server-5.5 mysql-server/root_password_again password %s"' % password)
        add_os_package(' '.join(['mysql-server'] + self.required_system_packages))
        local('touch passwords')
        return password
########NEW FILE########
__FILENAME__ = postgresql
from fabric.api import sudo, local, env
from fabric.context_managers import settings

from db import DBTypeBase
from utils import generate_password, add_os_package

PGSQL_USER = 'postgres'
POSTGRESQL_EXECUTABLE_PATH = '/usr/bin/psql'


class DBType(DBTypeBase):
    def __init__(self, *args, **kwargs):
        self.engine = 'postgresql_psycopg2'
        self.required_system_packages = ['libpq-dev']
        self.required_packages = ['psycopg2']
        self.executable_path = POSTGRESQL_EXECUTABLE_PATH

    def create_user(self, username):
        """ Creates user with given name and grans them full permission on specified base """
        password = generate_password()
        with settings(warn_only=True):
            result = sudo('psql -c "create user %s with password \'%s\'"' %
                          (username, password),
                          user=PGSQL_USER)
        return False if result.failed else password

    def create_db(self, name):
        """ Creates database with given name """
        with settings(warn_only=True):
            result = sudo('psql -c "CREATE DATABASE %s"' % name,
                          user=PGSQL_USER)
        return not result.failed

    def create_db_and_user(self, name):
        """ Creates database and user with the same name """
        password = self.create_user(name)
        if password:
            self.create_db(name)
        return password

    def grant_privileges(self, dbname, username):
        with settings(warn_only=True):
            result = sudo('psql -c "GRANT ALL PRIVILEGES on DATABASE %s TO %s"'
                          % (dbname, username),
                          user=PGSQL_USER)
        return not result.failed

    def install(self):
        if self.is_db_installed():
            print 'Database already installed'
            return
        add_os_package('postgresql')
########NEW FILE########
__FILENAME__ = manage
#!/usr/bin/env python
import os
import sys

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "{{ project_name }}.settings.development")

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)

########NEW FILE########
__FILENAME__ = development
from {{ project_name }}.settings import *


# DEVELOPMENT SPECIFIC SETTINGS GOES HERE
DEBUG = TEMPLATE_DEBUG = True



########NEW FILE########
__FILENAME__ = local

########NEW FILE########
__FILENAME__ = production
from {{ project_name }}.settings import *


# PRODUCTION SPECIFIC SETTINGS GOES HERE
DEBUG = TEMPLATE_DEBUG = False

########NEW FILE########
__FILENAME__ = urls
from django.conf.urls import patterns, include, url

from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('',
    # Examples:
    # url(r'^{{ project_name }}/', include('{{ project_name }}.foo.urls')),

    # Uncomment the admin/doc line below to enable admin documentation:
    # url(r'^admin/doc/', include('django.contrib.admindocs.urls')),

    # Uncomment the next line to enable the admin:
    url(r'^admin/', include(admin.site.urls)),
    url(r'^$', '{{ project_name }}.views.home', name='home'),
)

########NEW FILE########
__FILENAME__ = views
from django.shortcuts import render_to_response


def home(request):
    return render_to_response('home.html')
########NEW FILE########
__FILENAME__ = wsgi
"""
WSGI config for {{ project_name }} project.

This module contains the WSGI application used by Django's development server
and any production WSGI deployments. It should expose a module-level variable
named ``application``. Django's ``runserver`` and ``runfcgi`` commands discover
this application via the ``WSGI_APPLICATION`` setting.

Usually you will have the standard Django WSGI application here, but it also
might make sense to replace the whole Django WSGI application with a custom one
that later delegates to the Django one. For example, you could introduce WSGI
middleware here, or combine a Django application with an application of another
framework.

"""
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "{{ project_name }}.settings")

# This application object is used by any WSGI server configured to use this
# file. This includes Django's development server, if the WSGI_APPLICATION
# setting points here.
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()

# Apply WSGI middleware here.
# from helloworld.wsgi import HelloWorldApplication
# application = HelloWorldApplication(application)

########NEW FILE########
__FILENAME__ = fabfile
import re, os, inspect

from fabric.api import env, local, run, sudo
from fabric.context_managers import cd, lcd, prefix, settings
from fabric.contrib.console import confirm
from fabric.contrib.files import exists

from db import select_db_type
#from db.mysql import setup_db_server, create_db_and_user

from utils import add_os_package, create_virtual_env, replace_in_template


VERSION = '0.1'


FABFILE_LOCATION = os.path.dirname(inspect.getfile(inspect.currentframe()))


# The name of the directory where the version controlled source will reside
SOURCE_DIRECTORY_NAME = 'src'

PRODUCTION_USER = 'ubuntu'
PRODUCTION_WORKSPACE_PATH = os.path.join(os.sep, 'home', PRODUCTION_USER)

SETTINGS_TYPES = ['development', 'production']


# System packages required for basic server setup
REQUIRED_SYSTEM_PACKAGES = [
    'python-pip',
    'gcc',
    'python-dev',
    'libjpeg-dev',
    'libfreetype6-dev',
    'git',
    'nginx',
    'python-virtualenv',
    'libxml2-dev',
    #'ia32-libs', # this packages fixes the following uwsgi error -> ibgcc_s.so.1 must be installed for pthread_cancel to work 
]


# Django database configuration template
DJANGO_DB_CONF = """
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.%s', # Add 'postgresql_psycopg2', 'mysql', 'sqlite3' or 'oracle'.
        'NAME': '%s',                      # Or path to database file if using sqlite3.
        'USER': '%s',                      # Not used with sqlite3.
        'PASSWORD': '%s',                  # Not used with sqlite3.
        'HOST': '%s',                      # Set to empty string for localhost. Not used with sqlite3.
        'PORT': '%s',                      # Set to empty string for default. Not used with sqlite3.
    }
}
"""


def check_project_name(name):
    """ Check whether the project name corresponds to the Django project name
    restrictions. The check is copied from the Dajngo core code. As we are
    running it before the creation of the virtual environment the check whether
    the project name matches those of existing module check is skipped """
    if not re.search(r'^[_a-zA-Z]\w*$', name):
        # Provide a smart error message, depending on the error.
        if not re.search(r'^[_a-zA-Z]', name):
            message = ('make sure the name begins '
                       'with a letter or underscore')
        else:
            message = 'use only numbers, letters and underscores'
        return False, ("%r is not a valid project name. Please %s." %
                           (name, message))
    if os.path.exists(name):
        message = ('Project with such name already exists.')
        return False, message
    return True, ''


def ve_activate_prefix(name):
    """ Returns the path to the virtual environment activate script """
    return os.path.join(os.getcwd(), name, 'bin', 'activate')


def create_django_project(name, dest_path=''):
    """ Creates new Django project using a pre made template """
    local('python ./bin/django-admin.py startproject --template "%s" %s %s' % (
            os.path.join(FABFILE_LOCATION, 'django_template/'),
            name,
            dest_path))
    local('mkdir %s' % os.path.join(dest_path, os.pardir, 'media'))


def generate_django_db_config(engine='', name='', user='', password='',
                              host='', port=''):
    """ Returns database configuration template with filled values """
    return DJANGO_DB_CONF % (engine, name, user, password, host, port)


def create_uwsgi_files(project_name, project_path=None):
    """ Creates the uwsgi and nginx configuration files for development and
    production environment. The uwsgi script file is ment to be run using
    upstart """
    if not project_path:
        project_path = os.path.join(project_name)
    project_path = os.path.abspath(project_path)
    source_path = os.path.join(project_path, SOURCE_DIRECTORY_NAME)

    uwsgi_templates_dir = os.path.join(FABFILE_LOCATION, 'project_settings')
    # the last template in the line is only for local development purposes
    uwsgi_templates = [os.path.join(uwsgi_templates_dir, 'nginx.uwsgi.conf'),
                       os.path.join(uwsgi_templates_dir,
                                    'uwsgi.conf'),
                       os.path.join(uwsgi_templates_dir,
                                    'nginx.local.conf')]

    def _generate_files(input_files, output_path, data):
        for file_path in input_files:
            file_name = os.path.basename(file_path)
            with open(file_path) as template:
                output = replace_in_template(template.read(), data)
            output_file_name = '%s.%s.%s' % (data['project_name'],
                                             data['env_type'],
                                             file_name)
            output_file_path = os.path.join(output_path, output_file_name)
            if exists(output_file_path):
                if not confirm('File %s already exists, proceeding with this '
                               'task will overwrite it' % output_file_path):
                    continue
            with open(output_file_path, 'w+') as output_file:
                output_file.write(output)

    development_data = {'project_path': os.path.abspath(project_path),
                        'source_path': source_path,
                        'project_home': os.path.join(source_path,
                                                     project_name),
                        'env_type': 'development',
                        'project_name': project_name}
    _generate_files(uwsgi_templates, source_path, development_data)

    production_project_path = os.path.abspath(os.path.join(
                                        PRODUCTION_WORKSPACE_PATH,project_name))
    production_data = {'project_path': os.path.abspath(production_project_path),
                       'source_path': os.path.join(production_project_path,
                                                   SOURCE_DIRECTORY_NAME),
                       'project_home': os.path.join(production_project_path,
                                                    SOURCE_DIRECTORY_NAME,
                                                    project_name),
                       'env_type': 'production',
                       'project_name': project_name}
    _generate_files(uwsgi_templates[:-1], source_path, production_data)


def init_git_repository(source_path):
    """ Goes to the source path and initiales GIT repository there """
    with lcd(os.path.abspath(source_path)):
        local('git init')
        local('cp %s %s' % (os.path.join(FABFILE_LOCATION,
                                             'project_settings',
                                             'gitignore_base'),
                            os.path.join(source_path, '.gitignore')))


def startproject(name):
    """Creates new virtual environment, installs Django and creates new project
    with the specified name. Prompts the user to choose DB engine and tries
    to setup database/user with the project name and random password and
    updates local settings according to the choosen database. Also creates
    nginx conf file for local usage"""
    if env['host'] not in ['127.0.0.1', 'localhost']:
        print 'This task can be executed only on localhost'
        return
    check, message = check_project_name(name)
    if not check:
        print message
        exit(1)
    create_virtual_env(name, True)
    ve_path = os.path.abspath(name)
    source_path = os.path.join(ve_path, SOURCE_DIRECTORY_NAME)
    local('mkdir %s' % source_path)
    with lcd(name):
        with prefix('. %s' % ve_activate_prefix(name)):
            packages_file = os.path.join(source_path,
                                         'required_packages.txt')
            local('cp %s %s' % (os.path.join(FABFILE_LOCATION,
                                             'project_settings',
                                             'required_packages.txt'),
                                packages_file))
            local('pip install -r %s' % packages_file)
            project_root = os.path.join(source_path, name)
            local('mkdir %s' % project_root)
            create_django_project(name, project_root)
            create_uwsgi_files(name, ve_path)
            init_git_repository(source_path)
            manage_py_path = os.path.join(source_path, name, 'manage.py')
            local_settings_path = os.path.join(source_path, name, name,
                                               'settings', 'local.py')
            db_type_class = select_db_type()
            if db_type_class:
                db_type = db_type_class()
                if not os.path.exists(db_type.executable_path):
                    print 'Database executable not found. Skipping DB creation part.'
                    django_db_config = generate_django_db_config(db_type.engine)
                    local('echo "%s" >> %s' % (django_db_config,
                                               local_settings_path))
                else:
                    installed_packages = file(packages_file).read()
                    package_list_updated = False
                    for package in db_type.required_packages:
                        if package not in installed_packages:
                            local('echo "%s" >> %s' % (package, packages_file))
                            package_list_updated = True
                    if package_list_updated:
                        local('pip install -r %s' % packages_file)
                    password = db_type.create_db_and_user(name)
                    if password:
                        django_db_config = generate_django_db_config(db_type.engine,
                                                                name, name,
                                                                password)
                        local('echo "%s" >> %s' % (django_db_config,
                                                   local_settings_path))
                        grant = db_type.grant_privileges(name, name)
                        if grant:
                            local('python %s syncdb' % manage_py_path)
                        else:
                            print 'Unable to grant DB privileges'
                            exit(1)
                    else:
                        print ('Unable to complete DB/User creation.'
                               'Skipping DB settings update.')
                        local('echo "%s" >> %s' % (generate_django_db_config(db_type.engine),
                                                   local_settings_path))
            else:
                local('echo "%s" >> %s' % (generate_django_db_config(),
                                               local_settings_path))
            local('python %s collectstatic --noinput' % manage_py_path)


def setup_server(local=False):
    """ WARNING: under development """
    with settings(warn_only=True):
        sudo('apt-get update')
    add_os_package(' '.join(REQUIRED_SYSTEM_PACKAGES))
    server_setup_info = ['-'*80, 'Server setup for %s' % env.host]
    #if not local:
    #    password = add_user(PRODUCTION_USER, True)
    #    if password:
    #        server_setup_info.append('www user password: %s' % password)
    db_type_class = select_db_type()
    if db_type_class:
        db = db_type_class()
        db_password = db.install()
        if db_password:
            server_setup_info.append('Database Root Password: %s' % db_password)
    sudo('reboot') # FIX ME: add check for is reboot required
    print '\n'.join(server_setup_info)


def generate_local_config(name, local_settings_path):
    db_type_class = select_db_type()
    if db_type_class:
        db_type = db_type_class()
        if not os.path.exists(db_type.executable_path):
            print 'Database executable not found. Skipping DB creation part.'
            return False
        else:
            password = db_type.create_db_and_user(name)
            if password:
                django_db_config = generate_django_db_config(db_type.engine,
                                                        name, name,
                                                        password)
                run('echo "%s" >> %s' % (django_db_config,
                                           local_settings_path))
                grant = db_type.grant_privileges(name, name)
                if grant:
                    return True
                else:
                    print 'Unable to grant DB privileges'
                    return False
            else:
                print ('Unable to complete DB/User creation.'
                       'Skipping DB settings update.')
                return False
    else:
        print 'No database selected, skipping DB settings update'
        return True


def update_project(project_name, env_type):
    """ Updates the source files, and then consecutively runs syncdb, migrate
    and collectstatic. The env_type argument shows the environment type
    development/production/etc."""
    user_home_path = run('echo $HOME')
    project_path = os.path.join(user_home_path, project_name)
    activate_prefix = '. %s' % os.path.join(project_path, 'bin', 'activate')
    source_path = os.path.join(project_path, SOURCE_DIRECTORY_NAME) 
    with cd(source_path):
        run('git pull origin master')
        with prefix(activate_prefix):
            run('pip install -r required_packages.txt')
            with cd(project_name):
                run('python manage.py syncdb')
                run('python manage.py migrate')
                run('python manage.py collectstatic --noinput')
    uwsgi_conf_name = '%s.%s.uwsgi' % (project_name, env_type)
    sudo('initctl reload-configuration')
    with settings(warn_only=True):
        result = sudo('initctl restart %s' % uwsgi_conf_name)
        if result.failed:
            result = sudo('initctl start %s' % uwsgi_conf_name)
            if result.failed:
                print 'Failed to restart/start job %s' % uwsgi_conf_name
    sudo('/etc/init.d/nginx restart')


def deploy_project(project_name, env_type, repo):
    """ Deploys project to remote server, requires project name, environment
    type(development/production) and the repository of the project """
    create_virtual_env(project_name)
    with cd(project_name):
        run('mkdir %s' % SOURCE_DIRECTORY_NAME)
        with cd(SOURCE_DIRECTORY_NAME):
            run('git clone %s .' % repo)
            source_path = run('pwd')
            nginx_uwsgi_conf_name = '%s.production.nginx.uwsgi' % project_name
            uwsgi_conf_name = '%s.production.uwsgi' % project_name
            with settings(warn_only=True):
                sudo('ln -s %s.conf /etc/nginx/sites-enabled/' % os.path.join(source_path,
                                                                         nginx_uwsgi_conf_name))
                sudo('ln -s %s.conf /etc/init/' % os.path.join(source_path,
                                                           uwsgi_conf_name))
            local_settings_path = os.path.join(source_path, project_name,
                                               project_name, 'settings',
                                               'local.py')
            if generate_local_config(project_name, local_settings_path):
                update_project(project_name, env_type)
########NEW FILE########
__FILENAME__ = utils
import string
import random

from fabric.api import local, run, sudo
from fabric.context_managers import settings


def add_os_package(name):
    sudo('sudo apt-get -y install %s' % name)


def add_user(user, make_sudoer = False):
    with settings(warn_only=True):
        result = sudo('useradd -m %s' % (user))
    if not result.failed:
        if make_sudoer:
            sudo('echo "%s ALL=(ALL) ALL" >> /etc/sudoers' % user)
        password = generate_password()
        sudo('echo "%s:%s" | chpasswd' % (user, password))
        return password
    return False


def generate_password(length=10):
    """ Generates password using ASCII letters and punctuations chars """
    chars = string.ascii_letters + string.digits
    password = ''.join(random.choice(chars) for x in range(length))
    return password


def create_virtual_env(name='.', run_locally=False):
    """ Creates virtual environment with given name """
    runner = local if run_locally else run
    runner('virtualenv --no-site-packages %s' % name)


def replace_in_template(input, data={}):
    for var in data:
        input = input.replace('%%%%%%%s%%%%%%' % var, data[var])
    return input
########NEW FILE########