"""
********************************************************************************
* Name: utilities.py
* Author: Scott Christensen
* Created On: 2015
* Copyright: (c) Brigham Young University 2015
* License: BSD 2-Clause
********************************************************************************
"""
# code for DictionaryField was taken from https://djangosnippets.org/snippets/1979/

import json
from django import forms
from django.core import exceptions
from django.db import models
from django.utils.translation import ugettext_lazy as _

class DictionaryField(models.Field):
    description = _("Dictionary object")

    __metaclass__ = models.SubfieldBase

    def get_internal_type(self):
        return "TextField"

    def to_python(self, value):
        if value is None:
            return None
        elif value == "":
            return {}
        elif isinstance(value, basestring):
            try:
                return dict(json.loads(value))
            except (ValueError, TypeError):
                raise exceptions.ValidationError(self.error_messages['invalid value for json: %s' % value])

        if isinstance(value, dict):
            return value
        else:
            return {}

    def get_prep_value(self, value):
        if not value:
            return ""
        elif isinstance(value, basestring):
            return value
        else:
            return json.dumps(value)

    def value_to_string(self, obj):
        value = self._get_val_from_obj(obj)
        return self.get_prep_value(value)

    def clean(self, value, model_instance):
        value = super(DictionaryField, self).clean(value, model_instance)
        return self.get_prep_value(value)

    def formfield(self, **kwargs):
        defaults = {'widget': forms.Textarea}
        defaults.update(kwargs)
        return super(DictionaryField, self).formfield(**defaults)

class ListField(models.Field):
    description = _("List object")

    __metaclass__ = models.SubfieldBase

    def get_internal_type(self):
        return "TextField"

    def to_python(self, value):
        if value is None:
            return None
        elif value == "":
            return []
        elif isinstance(value, basestring):
            try:
                return json.loads(value)
            except (ValueError, TypeError), e:
                raise e
                #raise exceptions.ValidationError(self.error_messages['invalid value for json: %s' % value])

        if isinstance(value, list):
            return value
        else:
            return []

    def get_prep_value(self, value):
        if not value:
            return ""
        elif isinstance(value, basestring):
            return value
        else:
            return json.dumps(value)

    def value_to_string(self, obj):
        value = self._get_val_from_obj(obj)
        return self.get_prep_value(value)

    def clean(self, value, model_instance):
        value = super(ListField, self).clean(value, model_instance)
        return self.get_prep_value(value)

    def formfield(self, **kwargs):
        defaults = {'widget': forms.Textarea}
        defaults.update(kwargs)
        return super(ListField, self).formfield(**defaults)