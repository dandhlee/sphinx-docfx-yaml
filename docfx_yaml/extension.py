# -*- coding: utf-8 -*-
"""
Sphinx DocFX YAML Top-level Extension.

This extension allows you to automagically generate DocFX YAML from your Python Domains.
"""
import os
import inspect
import subprocess

from yaml import safe_dump as dump

from sphinx.util.console import darkgreen, bold
from sphinx.util import ensuredir
from sphinx.errors import ExtensionError

from .settings import API_ROOT


# We need to map the Python type names to what DocFX is expecting
TYPE_MAPPING = {
    'method': 'Method',
    'function': 'Method',
    'module': 'Namespace',
    'class': 'Class',
    'exception': 'Class',  # Hack this for now
    'attribute': 'Property',  # Ditto
}


def build_init(app):
    """
    Set up environment data
    """
    if not app.config.docfx_yaml_output:
        raise ExtensionError('You must configure an docfx_yaml_output setting')

    app.env.docfx_yaml_modules = {}

    remote = subprocess.check_output('git remote -v'.split(' '))
    app.env.remote = remote.split('\t')[1].split(' ')[0]
    app.env.branch = subprocess.check_output('git rev-parse --abbrev-ref HEAD'.split(' ')).strip()


def _get_cls_module(_type, name):
    """
    Get the class and module name for an object
    """
    cls = None
    if _type in ['function', 'exception']:
        module = '.'.join(name.split('.')[:-1])
    elif _type in ['method', 'attribute']:
        cls = '.'.join(name.split('.')[:-1])
        module = '.'.join(name.split('.')[:-2])
    elif _type in ['class']:
        module = '.'.join(name.split('.')[:-1])
    elif _type in ['module']:
        module = name
    else:
        return (None, None)
    return (cls, module)


def _create_datam(app, cls, module, name, _type, obj, lines=[]):
    """
    Build the data structure for a autodoc class
    """
    try:
        mapped_type = TYPE_MAPPING[_type]
    except TypeError:
        print('Invalid Type Mapping: %s' % _type)
        mapped_type = _type

    short_name = name.split('.')[-1]
    full_path = inspect.getsourcefile(obj)
    path = full_path.replace(os.path.dirname(app.builder.srcdir), '').replace('/', '', 1)
    start_line = inspect.getsourcelines(obj)[1]
    datam = {
        'module': module,
        'uid': name,
        'type': mapped_type,
        '_type': _type,
        'name': short_name,
        'fullName': name,
        'summary': '\n'.join(lines),
        'source': {
            'remote': {
                'path': path,
                'branch': app.env.branch,
                'repo': app.env.remote,
            },
            'id': short_name,
            'path': path,
            'startLine': start_line,
        },
    }

    if cls:
        datam['class'] = cls
    if _type in ['class', 'module']:
        datam['children'] = []

    return datam


def _fullname(obj):
    """
    Get the fullname from a Python object
    """
    return obj.__module__ + "." + obj.__name__


def process_docstring(app, _type, name, obj, options, lines):
    """
    This function takes the docstring and indexes it into memory.
    """
    cls, module = _get_cls_module(_type, name)
    if not module:
        print('Unknown Type: %s' % _type)
        return None

    datam = _create_datam(app, cls, module, name, _type, obj, lines)

    if module not in app.env.docfx_yaml_modules:
        app.env.docfx_yaml_modules[module] = [datam]
    else:
        app.env.docfx_yaml_modules[module].append(datam)

    # Insert `Global` class to hold functions
    if _type == 'module':
        app.env.docfx_yaml_modules[module].append({
            'module': module,
            'uid': module + '.Global',
            'type': 'Class',
            '_type': 'class',
            'name': module.split('.')[-1] + '.Global',
            'fullName': name,
            'summary': 'Proxy object to hold module level functions',
            'langs': ['python'],
            'children': [],
        })

    insert_children(app, _type, datam)
    insert_inheritance(app, _type, obj, datam)


def insert_inheritance(app, _type, obj, datam):
    if hasattr(obj, '__bases__'):
        if 'inheritance' not in datam:
            datam['inheritance'] = []
        for base in obj.__bases__:
            datam['inheritance'].append(_fullname(base))
            # recurse into bases
            insert_inheritance(app, _type, base, datam)


def insert_children(app, _type, datam):
    """
    Insert children of a specific module
    """

    insert_module = app.env.docfx_yaml_modules[datam['module']]
    for obj in insert_module:
        # Add methods & attributes to class
        if _type in ['method', 'attribute'] and \
                obj['_type'] == 'class' and \
                obj['uid'] == datam['class']:
            obj['children'].append(datam['uid'])
            break
        # Add standardlone function to Global class
        elif _type in ['function'] and \
                obj['_type'] == 'class' and \
                obj['name'] == datam['module'] + '.Global':
            obj['children'].append(datam['uid'])
            # print('Inserting proxy object')
            break
        # Add classes & exceptions to module
        elif _type in ['class', 'exception'] and \
                obj['_type'] == 'module' and \
                obj['module'] == datam['module']:
            obj['children'].append(datam['uid'])
            break


def build_finished(app, exception):
    """
    Output YAML on the file system.
    """

    normalized_output = os.path.normpath(os.path.join(
        app.builder.outdir,  # Output Directory for Builder
        app.config.docfx_yaml_output
    ))
    ensuredir(normalized_output)

    # Get correct data set
    # if app.config.docfx_yaml_mode == 'rst':
    #     iter_data = app.env.docfx_yaml_data
    if app.config.docfx_yaml_mode == 'module':
        iter_data = app.env.docfx_yaml_modules

    toc_yaml = []

    for filename, yaml_data in iter_data.items():
        if not filename:
            # Skip objects without a module
            continue
        out_file = os.path.join(normalized_output, '%s.yml' % filename)
        ensuredir(os.path.dirname(out_file))
        if app.verbosity > 1:
            app.info(bold('[docfx_yaml] ') + darkgreen('Outputting %s' % filename))
        dump(
            {
                'items': yaml_data,
                'api_name': [],  # Hack around docfx YAML
            },
            open(out_file, 'w+'),
            default_flow_style=False
        )
        toc_yaml.append({'name': filename, 'href': '%s.yml' % filename})

    toc_file = os.path.join(normalized_output, 'toc.yml')
    with open(toc_file, 'w+') as writable:
        writable.write(dump(toc_yaml))


def setup(app):
    """
    Plugin init for our Sphinx extension.

    Args:
        app (Application): The Sphinx application
           instance is destructed

    """
    app.connect('autodoc-process-docstring', process_docstring)
    app.connect('builder-inited', build_init)
    app.connect('build-finished', build_finished)
    app.add_config_value('docfx_yaml_output', API_ROOT, 'html')
    app.add_config_value('docfx_yaml_ignore', [], 'html')
    app.add_config_value('docfx_yaml_mode', 'module', 'html')
