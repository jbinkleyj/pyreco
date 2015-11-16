__FILENAME__ = runtests
#!/usr/bin/env python
from django.conf import settings
settings.configure(
    INSTALLED_APPS=('typedmodels',),
    DATABASES={
        'default': {'ENGINE': 'django.db.backends.sqlite3'}
    })

from django.test.utils import setup_test_environment
setup_test_environment()

import django
if django.VERSION > (1, 7):
    django.setup()

from django.core.management import call_command
call_command('test', 'typedmodels')

########NEW FILE########
__FILENAME__ = models
# encoding: utf-8

import django
import types

from django.core.serializers.python import Serializer as _PythonSerializer
from django.core.serializers.xml_serializer import Serializer as _XmlSerializer
from django.db import models
from django.db.models.base import ModelBase
from django.db.models.fields import Field
from django.db.models.query_utils import DeferredAttribute, deferred_class_factory
from django.utils.datastructures import SortedDict
from django.utils.encoding import smart_text

from django.utils.six import with_metaclass



class TypedModelManager(models.Manager):
    def get_queryset(self):
        super_ = super(TypedModelManager, self)
        if django.VERSION < (1, 7):
            qs = super_.get_query_set()
        else:
            qs = super_.get_queryset()
        if hasattr(self.model, '_typedmodels_type'):
            if len(self.model._typedmodels_subtypes) > 1:
                qs = qs.filter(type__in=self.model._typedmodels_subtypes)
            else:
                qs = qs.filter(type=self.model._typedmodels_type)
        return qs
    # rant: why oh why would you rename something so widely used?
    if django.VERSION < (1, 7):
        # in 1.7+, get_query_set gets defined by the base manager and complains if it's called.
        # otherwise, we have to define it ourselves.
        get_query_set = get_queryset


class TypedModelMetaclass(ModelBase):
    """
    This metaclass enables a model for auto-downcasting using a ``type`` attribute.
    """
    def __new__(meta, classname, bases, classdict):
        # artifact created by with_metaclass, needed for py2/py3 compatibility
        if classname == 'NewBase':
            return super(TypedModelMetaclass, meta).__new__(
                meta, classname, bases, classdict)
        try:
            TypedModel
        except NameError:
            # don't do anything for TypedModel class itself
            #
            # ...except updating Meta class to instantiate fields_from_subclasses attribute
            typed_model = super(TypedModelMetaclass, meta).__new__(meta, classname, bases, classdict)
            # We have to set this attribute after _meta has been created, otherwise an
            # exception would be thrown by Options class constructor.
            typed_model._meta.fields_from_subclasses = {}
            return typed_model

        # look for a non-proxy base class that is a subclass of TypedModel
        mro = list(bases)
        while mro:
            base_class = mro.pop(-1)
            if issubclass(base_class, TypedModel) and base_class is not TypedModel:
                if base_class._meta.proxy:
                    # continue up the mro looking for non-proxy base classes
                    mro.extend(base_class.__bases__)
                else:
                    break
        else:
            base_class = None

        if base_class:
            if not hasattr(base_class._meta, 'original'):
                class original_meta:
                    proxy = True
                Original = super(TypedModelMetaclass, meta).__new__(meta, base_class.__name__+'Original', (base_class,), {'Meta': original_meta, '__module__': base_class.__module__})
                base_class._meta.original = Original
                # Fill m2m cache for original class now, so it doesn't contain fields from child classes.
                base_class._meta.original._meta.many_to_many

            # Enforce that subclasses are proxy models.
            # Update an existing metaclass, or define an empty one
            # then set proxy=True
            class Meta:
                pass
            Meta = classdict.get('Meta', Meta)
            if getattr(Meta, 'proxy', False):
                # If user has specified proxy=True explicitly, we assume that he wants it to be treated like ordinary
                # proxy class, without TypedModel logic.
                return super(TypedModelMetaclass, meta).__new__(meta, classname, bases, classdict)
            Meta.proxy = True

            declared_fields = dict((name, element) for name, element in classdict.items() if isinstance(element, Field))

            for field_name, field in declared_fields.items():
                field.null = True
                if isinstance(field, models.fields.related.RelatedField):
                    # Monkey patching field instance to make do_related_class use created class instead of base_class.
                    # Actually that class doesn't exist yet, so we just monkey patch base_class for a while,
                    # changing _meta.[object_name,module_name,model_name], so accessor names are generated properly.
                    # We'll do more stuff when the class is created.
                    old_do_related_class = field.do_related_class
                    def do_related_class(self, other, cls):
                        base_class_name = base_class.__name__
                        # model_name was introduced in commit ec469ad in Django.
                        if hasattr(cls._meta, 'model_name'):
                            cls._meta.model_name = classname.lower()
                        else:
                            cls._meta.object_name = classname
                        old_do_related_class(other, cls)
                        if hasattr(cls._meta, 'model_name'):
                            cls._meta.model_name = base_class_name.lower()
                        else:
                            cls._meta.object_name = base_class_name
                    field.do_related_class = types.MethodType(do_related_class, field)
                if isinstance(field, models.fields.related.RelatedField) and isinstance(field.rel.to, TypedModel) and field.rel.to.base_class:
                    field.rel.limit_choices_to['type__in'] = field.rel.to._typedmodels_subtypes
                    field.rel.to = field.rel.to.base_class
                field.contribute_to_class(base_class, field_name)
                classdict.pop(field_name)
            base_class._meta.fields_from_subclasses.update(declared_fields)

            # set app_label to the same as the base class, unless explicitly defined otherwise
            if not hasattr(Meta, 'app_label'):
                if hasattr(getattr(base_class, '_meta', None), 'app_label'):
                    Meta.app_label = base_class._meta.app_label

            classdict.update({
                'Meta': Meta,
            })

        classdict['base_class'] = base_class

        cls = super(TypedModelMetaclass, meta).__new__(meta, classname, bases, classdict)

        cls._meta.fields_from_subclasses = {}

        if base_class:
            opts = cls._meta

            # Dr Hacky "the hack" McHackerson, Sr.
            # Django's deserialization code doesn't trigger sequence resets for proxy models.
            # That's cool usually, but our deserialized models are always going to be recasted
            # to proxies, so the sequences will always have the wrong value after fixture loading.
            # Turns out Django triggers sequence resets based on whether there's PK fields in
            # opts.local_fields (which is normally empty for proxies.) So we hack it!
            opts.local_fields[:] = base_class._meta.local_fields[:]

            # model_name was introduced in commit ec469ad in Django.
            if hasattr(opts, 'model_name'):
                model_name = opts.model_name
            else:
                model_name = opts.module_name
            typ = "%s.%s" % (opts.app_label, model_name)
            cls._typedmodels_type = typ
            cls._typedmodels_subtypes = [typ]
            if typ in base_class._typedmodels_registry:
                raise ValueError("Can't register %s type %r to %r (already registered to %r )" % (typ, classname, base_class._typedmodels_registry))
            base_class._typedmodels_registry[typ] = cls
            type_name = getattr(cls._meta, 'verbose_name', cls.__name__)
            type_field = base_class._meta.get_field('type')
            type_field._choices = tuple(list(type_field.choices) + [(typ, type_name)])

            cls._meta.declared_fields = declared_fields

            # Update related fields in base_class so they refer to cls.
            for field_name, related_field in declared_fields.items():
                if isinstance(related_field, models.fields.related.RelatedField):
                    # Unfortunately RelatedObject is recreated in ./manage.py validate, so false positives for name clashes
                    # may be reported until #19399 is fixed - see https://code.djangoproject.com/ticket/19399
                    related_field.related.opts = cls._meta

            # look for any other proxy superclasses, they'll need to know
            # about this subclass
            for superclass in cls.mro():
                if (issubclass(superclass, base_class)
                        and superclass not in (cls, base_class)
                        and hasattr(superclass, '_typedmodels_type')):
                    superclass._typedmodels_subtypes.append(typ)

            # Overriding _fill_fields_cache and _fill_m2m_cache functions in Meta.
            # This is done by overriding method for specific instance of
            # django.db.models.options.Options class, which generally should
            # be avoided, but in this case it may be better than monkey patching
            # Options or copy-pasting large parts of Django code.

            def _fill_fields_cache(self):
                cache = []
                for parent in self.parents:
                    for field, model in parent._meta.get_fields_with_model():
                        if field in base_class._meta.original._meta.fields or any(field in ancestor._meta.declared_fields.values() for ancestor in cls.mro() if issubclass(ancestor, base_class) and not ancestor==base_class):
                            if model:
                                cache.append((field, model))
                            else:
                                cache.append((field, parent))
                self._field_cache = tuple(cache)
                self._field_name_cache = [x for x, _ in cache]
            cls._meta._fill_fields_cache = types.MethodType(_fill_fields_cache, cls._meta)
            if hasattr(cls._meta, '_field_name_cache'):
                del cls._meta._field_name_cache
            if hasattr(cls._meta, '_field_cache'):
                del cls._meta._field_cache
            cls._meta._fill_fields_cache()
            # Flush “fields” property cache created using cached_property, introduced in commit 9777442 in Django.
            if 'fields' in cls._meta.__dict__:
                del cls._meta.__dict__['fields']

            def _fill_m2m_cache(self):
                cache = SortedDict()
                for parent in self.parents:
                    for field, model in parent._meta.get_m2m_with_model():
                        if field in base_class._meta.original._meta.many_to_many or any(field in ancestor._meta.declared_fields.values() for ancestor in cls.mro() if issubclass(ancestor, base_class) and not ancestor==base_class):
                            if model:
                                cache[field] = model
                            else:
                                cache[field] = parent
                for field in self.local_many_to_many:
                    cache[field] = None
                self._m2m_cache = cache
            cls._meta._fill_m2m_cache = types.MethodType(_fill_m2m_cache, cls._meta)
            if hasattr(cls._meta, '_m2m_cache'):
                del cls._meta._m2m_cache
            cls._meta._fill_m2m_cache()
        else:
            # this is the base class
            cls._typedmodels_registry = {}

            # Since fields may be added by subclasses, save original fields.
            cls._meta.original_fields = cls._meta.fields

            # set default manager. this will be inherited by subclasses, since they are proxy models
            manager = None
            if not cls._default_manager:
                manager = TypedModelManager()
            elif not isinstance(cls._default_manager, TypedModelManager):
                class Manager(TypedModelManager, cls._default_manager.__class__):
                    pass
                cls._default_manager.__class__ = Manager
                manager = cls._default_manager
            if manager is not None:
                cls.add_to_class('objects', manager)
                cls._default_manager = cls.objects

            # add a get_type_classes classmethod to allow fetching of all the subclasses (useful for admin)

            def get_type_classes(subcls):
                if subcls is cls:
                    return list(cls._typedmodels_registry.values())
                else:
                    return [cls._typedmodels_registry[k] for k in subcls._typedmodels_subtypes]
            cls.get_type_classes = classmethod(get_type_classes)

            def get_types(subcls):
                if subcls is cls:
                    return cls._typedmodels_registry.keys()
                else:
                    return subcls._typedmodels_subtypes[:]
            cls.get_types = classmethod(get_types)

        return cls


def get_deferred_class_for_instance(instance, desired_class):
    """
    Returns a deferred class (as used by instances in a .defer() queryset).
    """
    original_cls = instance.__class__
    attrs = [k for (k, v) in original_cls.__dict__.items() if isinstance(v, DeferredAttribute)]
    return deferred_class_factory(desired_class, attrs)


class TypedModel(with_metaclass(TypedModelMetaclass, models.Model)):
    '''
    This class contains the functionality required to auto-downcast a model based
    on its ``type`` attribute.

    To use, simply subclass TypedModel for your base type, and then subclass
    that for your concrete types.

    Example usage::

        from django.db import models
        from typedmodels import TypedModel

        class Animal(TypedModel):
            """
            Abstract model
            """
            name = models.CharField(max_length=255)

            def say_something(self):
                raise NotImplemented

            def __repr__(self):
                return u'<%s: %s>' % (self.__class__.__name__, self.name)

        class Canine(Animal):
            def say_something(self):
                return "woof"

        class Feline(Animal):
            def say_something(self):
                return "meoww"
    '''

    type = models.CharField(choices=(), max_length=255, null=False, blank=False, db_index=True)

    # Class variable indicating if model should be automatically recasted after initialization
    _auto_recast = True

    class Meta:
        abstract = True

    def __init__(self, *args, **kwargs):
        # Calling __init__ on base class because some functions (e.g. save()) need access to field values from base
        # class.

        # Move args to kwargs since base_class may have more fields defined with different ordering
        args = list(args)
        if len(args) > len(self._meta.fields):
            # Daft, but matches old exception sans the err msg.
            raise IndexError("Number of args exceeds number of fields")
        for field_value, field in zip(args, self._meta.fields):
            kwargs[field.attname] = field_value
        args = []  # args were all converted to kwargs

        if self.base_class:
            before_class = self.__class__
            self.__class__ = self.base_class
        else:
            before_class = None
        super(TypedModel, self).__init__(*args, **kwargs)
        if before_class:
            self.__class__ = before_class
        if self._auto_recast:
            self.recast()

    def recast(self, typ=None):
        if not self.type:
            if not hasattr(self, '_typedmodels_type'):
                # Ideally we'd raise an error here, but the django admin likes to call
                # model() and doesn't expect an error.
                # Instead, we raise an error when the object is saved.
                return
            self.type = self._typedmodels_type

        for base in self.__class__.mro():
            if issubclass(base, TypedModel) and hasattr(base, '_typedmodels_registry'):
                break
        else:
            raise ValueError("No suitable base class found to recast!")

        if typ is None:
            typ = self.type
        else:
            if isinstance(typ, type) and issubclass(typ, base):
                if django.VERSION < (1, 7):
                    model_name = typ._meta.module_name
                else:
                    model_name = typ._meta.model_name
                typ = '%s.%s' % (typ._meta.app_label, model_name)

        try:
            correct_cls = base._typedmodels_registry[typ]
        except KeyError:
            raise ValueError("Invalid %s identifier: %r" % (base.__name__, typ))

        self.type = typ

        current_cls = self.__class__

        if current_cls != correct_cls:
            if self._deferred:
                # create a new deferred class based on correct_cls instead of current_cls
                correct_cls = get_deferred_class_for_instance(self, correct_cls)
            self.__class__ = correct_cls

    def save(self, *args, **kwargs):
        if not getattr(self, '_typedmodels_type', None):
            raise RuntimeError("Untyped %s cannot be saved." % self.__class__.__name__)
        return super(TypedModel, self).save(*args, **kwargs)

    @classmethod
    def _check_field_name_clashes(cls):
        if cls.base_class:
            # Because we hack self._meta.local_fields, django's normal
            # implementation of this method throws a bunch of errors.
            # So we hack it to not throw those errors.
            return []
        return super(TypedModel, cls)._check_field_name_clashes()


# Monkey patching Python and XML serializers in Django to use model name from base class.
# This should be preferably done by changing __unicode__ method for ._meta attribute in each model,
# but it doesn’t work.
_python_serializer_get_dump_object = _PythonSerializer.get_dump_object
def _get_dump_object(self, obj):
    if isinstance(obj, TypedModel):
        return {
            "pk": smart_text(obj._get_pk_val(), strings_only=True),
            "model": smart_text(getattr(obj, 'base_class', obj)._meta),
            "fields": self._current
        }
    else:
        return _python_serializer_get_dump_object(self, obj)
_PythonSerializer.get_dump_object = _get_dump_object

_xml_serializer_start_object = _XmlSerializer.start_object
def _start_object(self, obj):
    if isinstance(obj, TypedModel):
        self.indent(1)
        obj_pk = obj._get_pk_val()
        modelname = smart_text(getattr(obj, 'base_class', obj)._meta)
        if obj_pk is None:
            attrs = {"model": modelname,}
        else:
            attrs = {
                "pk": smart_text(obj._get_pk_val()),
                "model": modelname,
            }

        self.xml.startElement("object", attrs)
    else:
        return _xml_serializer_start_object(self, obj)
_XmlSerializer.start_object = _start_object

########NEW FILE########
__FILENAME__ = tests
from django.utils import unittest
try:
    import yaml
    PYYAML_AVAILABLE = True
except ImportError:
    PYYAML_AVAILABLE = False

from django.core import serializers
from django.test import TestCase
from django.db.models.query_utils import DeferredAttribute

from .test_models import AngryBigCat, Animal, BigCat, Canine, Feline, Parrot, AbstractVegetable, Vegetable, Fruit


class SetupStuff(TestCase):
    def setUp(self):
        Feline.objects.create(name="kitteh")
        Feline.objects.create(name="cheetah")
        Canine.objects.create(name="fido")
        BigCat.objects.create(name="simba")
        AngryBigCat.objects.create(name="mufasa")
        Parrot.objects.create(name="Kajtek")


class TestTypedModels(SetupStuff):
    def test_cant_instantiate_base_model(self):
        # direct instantiation shouldn't work
        self.assertRaises(RuntimeError, Animal.objects.create, name="uhoh")

        # ... unless a type is specified
        Animal.objects.create(name="dingo", type="typedmodels.canine")

        # ... unless that type is stupid
        try:
            Animal.objects.create(name="dingo", type="macaroni.buffaloes")
        except ValueError:
            pass

    def test_get_types(self):
        self.assertEqual(set(Animal.get_types()), set(['typedmodels.canine', 'typedmodels.bigcat', 'typedmodels.parrot', 'typedmodels.angrybigcat', 'typedmodels.feline']))
        self.assertEqual(set(Canine.get_types()), set(['typedmodels.canine']))
        self.assertEqual(set(Feline.get_types()), set(['typedmodels.bigcat', 'typedmodels.angrybigcat', 'typedmodels.feline']))

    def test_get_type_classes(self):
        self.assertEqual(set(Animal.get_type_classes()), set([Canine, BigCat, Parrot, AngryBigCat, Feline]))
        self.assertEqual(set(Canine.get_type_classes()), set([Canine]))
        self.assertEqual(set(Feline.get_type_classes()), set([BigCat, AngryBigCat, Feline]))

    def test_base_model_queryset(self):
        # all objects returned
        qs = Animal.objects.all().order_by('type')
        self.assertEqual(len(qs), 6)
        self.assertEqual([obj.type for obj in qs], ['typedmodels.angrybigcat', 'typedmodels.bigcat', 'typedmodels.canine', 'typedmodels.feline', 'typedmodels.feline', 'typedmodels.parrot'])
        self.assertEqual([type(obj) for obj in qs], [AngryBigCat, BigCat, Canine, Feline, Feline, Parrot])

    def test_proxy_model_queryset(self):
        qs = Canine.objects.all().order_by('type')
        self.assertEqual(qs.count(), 1)
        self.assertEqual(len(qs), 1)
        self.assertEqual([obj.type for obj in qs], ['typedmodels.canine'])
        self.assertEqual([type(obj) for obj in qs], [Canine])

        qs = Feline.objects.all().order_by('type')
        self.assertEqual(qs.count(), 4)
        self.assertEqual(len(qs), 4)
        self.assertEqual([obj.type for obj in qs], ['typedmodels.angrybigcat', 'typedmodels.bigcat', 'typedmodels.feline', 'typedmodels.feline'])
        self.assertEqual([type(obj) for obj in qs], [AngryBigCat, BigCat, Feline, Feline])

    def test_doubly_proxied_model_queryset(self):
        qs = BigCat.objects.all().order_by('type')
        self.assertEqual(qs.count(), 2)
        self.assertEqual(len(qs), 2)
        self.assertEqual([obj.type for obj in qs], ['typedmodels.angrybigcat', 'typedmodels.bigcat'])
        self.assertEqual([type(obj) for obj in qs], [AngryBigCat, BigCat])

    def test_triply_proxied_model_queryset(self):
        qs = AngryBigCat.objects.all().order_by('type')
        self.assertEqual(qs.count(), 1)
        self.assertEqual(len(qs), 1)
        self.assertEqual([obj.type for obj in qs], ['typedmodels.angrybigcat'])
        self.assertEqual([type(obj) for obj in qs], [AngryBigCat])

    def test_recast_auto(self):
        cat = Feline.objects.get(name='kitteh')
        cat.type = 'typedmodels.bigcat'
        cat.recast()
        self.assertEqual(cat.type, 'typedmodels.bigcat')
        self.assertEqual(type(cat), BigCat)

    def test_recast_string(self):
        cat = Feline.objects.get(name='kitteh')
        cat.recast('typedmodels.bigcat')
        self.assertEqual(cat.type, 'typedmodels.bigcat')
        self.assertEqual(type(cat), BigCat)

    def test_recast_modelclass(self):
        cat = Feline.objects.get(name='kitteh')
        cat.recast(BigCat)
        self.assertEqual(cat.type, 'typedmodels.bigcat')
        self.assertEqual(type(cat), BigCat)

    def test_recast_fail(self):
        cat = Feline.objects.get(name='kitteh')
        self.assertRaises(ValueError, cat.recast, AbstractVegetable)
        self.assertRaises(ValueError, cat.recast, 'typedmodels.abstractvegetable')
        self.assertRaises(ValueError, cat.recast, Vegetable)
        self.assertRaises(ValueError, cat.recast, 'typedmodels.vegetable')

    def test_fields_in_subclasses(self):
        canine = Canine.objects.all()[0]
        angry = AngryBigCat.objects.all()[0]

        angry.mice_eaten = 5
        angry.save()
        self.assertEqual(AngryBigCat.objects.get(pk=angry.pk).mice_eaten, 5)

        angry.canines_eaten.add(canine)
        self.assertEqual(list(angry.canines_eaten.all()), [canine])

        # Feline class was created before Parrot and has mice_eaten field which is non-m2m, so it may break accessing
        # known_words field in Parrot instances (since Django 1.5).
        parrot = Parrot.objects.all()[0]
        parrot.known_words = 500
        parrot.save()
        self.assertEqual(Parrot.objects.get(pk=parrot.pk).known_words, 500)

    def test_fields_cache(self):
        mice_eaten = Feline._meta.get_field('mice_eaten')
        known_words = Parrot._meta.get_field('known_words')
        self.assertIn(mice_eaten, AngryBigCat._meta.fields)
        self.assertIn(mice_eaten, Feline._meta.fields)
        self.assertNotIn(mice_eaten, Parrot._meta.fields)
        self.assertIn(known_words, Parrot._meta.fields)
        self.assertNotIn(known_words, AngryBigCat._meta.fields)
        self.assertNotIn(known_words, Feline._meta.fields)

    def test_m2m_cache(self):
        canines_eaten = AngryBigCat._meta.get_field_by_name('canines_eaten')[0]
        self.assertIn(canines_eaten, AngryBigCat._meta.many_to_many)
        self.assertNotIn(canines_eaten, Feline._meta.many_to_many)
        self.assertNotIn(canines_eaten, Parrot._meta.many_to_many)

    def test_related_names(self):
        '''Ensure that accessor names for reverse relations are generated properly.'''

        canine = Canine.objects.all()[0]
        self.assertTrue(hasattr(canine, 'angrybigcat_set'))

    def test_queryset_defer(self):
        """
        Ensure that qs.defer() works correctly
        """
        Vegetable.objects.create(name='cauliflower', color='white', yumness=1)
        Vegetable.objects.create(name='spinach', color='green', yumness=5)
        Vegetable.objects.create(name='sweetcorn', color='yellow', yumness=10)
        Fruit.objects.create(name='Apple', color='red', yumness=7)

        qs = AbstractVegetable.objects.defer('yumness')

        objs = set(qs)
        for o in objs:
            print(o)
            self.assertIsInstance(o, AbstractVegetable)
            self.assertTrue(o._deferred)
            self.assertIsInstance(o.__class__.__dict__['yumness'], DeferredAttribute)
            # does a query, since this field was deferred
            self.assertIsInstance(o.yumness, float)

    def _check_serialization(self, serialization_format):
        """Helper function used to check serialization and deserialization for concrete format."""
        animals = Animal.objects.order_by('pk')
        serialized_animals = serializers.serialize(serialization_format, animals)
        deserialized_animals = [wrapper.object for wrapper in serializers.deserialize(serialization_format, serialized_animals)]
        self.assertEqual(set(deserialized_animals), set(animals))

    def test_xml_serialization(self):
        self._check_serialization('xml')

    def test_json_serialization(self):
        self._check_serialization('json')

    @unittest.skipUnless(PYYAML_AVAILABLE, 'PyYAML is not available.')
    def test_yaml_serialization(self):
        self._check_serialization('yaml')

########NEW FILE########
__FILENAME__ = test_models

from django.db import models
from django.utils.encoding import python_2_unicode_compatible
from typedmodels import TypedModel

from django.utils.six import text_type


@python_2_unicode_compatible
class Animal(TypedModel):
    """
    Abstract model
    """
    name = models.CharField(max_length=255)

    def say_something(self):
        raise NotImplemented

    # def __repr__(self):
    #     return u'<%s: %s>' % (self.__class__.__name__, self.name)

    def __str__(self):
        return text_type(self.name)


class Canine(Animal):
    def say_something(self):
        return "woof"


class Feline(Animal):
    def say_something(self):
        return "meoww"

    mice_eaten = models.IntegerField(default=0)


class BigCat(Feline):
    """
    This model tests doubly-proxied models.
    """

    def say_something(self):
        return "roar"


class AngryBigCat(BigCat):
    """
    This model tests triple-proxied models. Because we can
    """
    canines_eaten = models.ManyToManyField(
        Canine
        )

    def say_something(self):
        return "raawr"


class Parrot(Animal):
    known_words = models.IntegerField()

    def say_something(self):
        return "hello"


class AbstractVegetable(TypedModel):
    """
    This is an entirely different typed model.
    """
    name = models.CharField(max_length=255)
    color = models.CharField(max_length=255)
    yumness = models.FloatField(null=False)


class Fruit(AbstractVegetable):
    pass


class Vegetable(AbstractVegetable):
    pass

########NEW FILE########