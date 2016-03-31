"""
********************************************************************************
* Name: handoff.py
* Author: Nathan Swain and Scott Christensen
* Created On: August 11, 2015
* Copyright: (c) Brigham Young University 2015
* License: BSD 2-Clause
********************************************************************************
"""
import inspect
import json

from django.core.urlresolvers import reverse
from django.shortcuts import redirect
from django.http import HttpResponseBadRequest

import tethys_apps
from tethys_apps.base.persistent_store import TethysFunctionExtractor


NEXT_HANDOFF_KEY = 'next_handoff'
NEXT_HANDOFF_LIST_KEY = 'next_handoff_list'

class HandoffManager(object):
    """
    An object that is used to interact with HandoffHandlers.

    Attributes:
      app (str): Instance of a TethysAppBase object.
      handlers (list[HandoffHandler]): A list of HandoffHandlers registered in the app.
      valid_handlers (list[HandoffHandler]): A filtered list of only the valid HandoffHandlers.
    """

    def __init__(self, app):
        """
        Constructor
        """

        self.app = app
        self.handlers = app.handoff_handlers() or []
        self.valid_handlers = self._get_valid_handlers()

    def __repr__(self):
        """
        String representation
        """
        return '<Handoff Manager: app={0}, handlers={1}>'.format(self.app, [handler.name for handler in self.handlers])

    def get_capabilities(self, app_name=None, external_only=False, jsonify=False):
        """
        Gets a list of the valid handoff handlers.

        Args:
            app_name (str, optional): The name of another app whose capabilities should be listed. Defaults to None in which case the capabilities of the current app will be listed.
            external_only (bool, optional): If True only return handlers where the internal attribute is False. Default is False.
            jsonify (bool, optional): If True return the JSON representation of the handlers is used. Default is False.

        Returns:
            A list of valid HandoffHandler objects (or a JSON string if jsonify=True) representing the capabilities of app_name, or None if no app with app_name is found.
        """
        manager = self._get_handoff_manager_for_app(app_name)

        if manager:
            handlers = manager.valid_handlers

            if external_only:
                handlers = [handler for handler in handlers if not handler.internal]

            if jsonify:
                handlers = json.dumps([handler.__json__() for handler in handlers])

            return handlers

    def get_handler(self, handler_name, app_name=None):
        """
        Returns the HandoffHandler with name == handler_name.

        Args:
            handler_name (str): the name of a HandoffHandler object.
            app_name (str, optional): the name of the app with handler_name. Defaults to None in which case the current app will be used.

        Returns:
            A HandoffHandler object where the name attribute is equal to handler_name or None if no HandoffHandler with that name is found or no app with app_name is found.
        """
        manager = self._get_handoff_manager_for_app(app_name)

        if manager:
            for handler in manager.valid_handlers:
                if handler.name == handler_name:
                    return handler

    def handoff(self, request, handler_name, app_name=None, next_handoff_list=None, external_only=True, **kwargs):
        """
        Calls handler if it is not internal and if it exists for the app.

        Args:
            request (HttpRequest): The request object passed by the http call.
            handler_name (str): The name of the HandoffHandler object to handle the handoff. Must not be internal.
            app_name (str, optional): The name of another app where the handler should exist. Defaults to None in which case the current app will attempt to handle the handoff.
            next_handoff_list (list, optional): A list of urls or namespaced urlnames (e.g. 'my_app:url'), or namespaced handoff handler names (e.g. 'my_app:handler') that form a sequense of handoffs.
            **kwargs: Key-value pairs to be passed on to the handler.

        Returns:
            HttpResponse object.
        """

        error = {"message": "",
                 "code": 400,
                 "status": "error",
                 "app_name": app_name or self.app.name,
                 "handler_name": handler_name}

        manager = self._get_handoff_manager_for_app(app_name)

        if manager:
            handler = manager.get_handler(handler_name)
            if not handler.internal:
                try:
                    request.session[NEXT_HANDOFF_LIST_KEY] = next_handoff_list
                    urlish = handler(request, **kwargs)
                    return redirect(urlish)
                except TypeError as e:
                    error['message'] = "HTTP 400 Bad Request: {0}. ".format(e.message)
                    return HttpResponseBadRequest(json.dumps(error), content_type='application/javascript')

        error['message'] = "HTTP 400 Bad Request: No handoff handler '{0}' for app '{1}' found.".format(handler_name, manager.app.package)
        return HttpResponseBadRequest(json.dumps(error), content_type='application/javascript')

    def _get_handoff_manager_for_app(self, app_name):
        """
        Returns the app manager for app with package == app_name if that app is installed.

        Args:
            app_name (str): The name of another Tethys app whose HandoffManager should be returned. If None then self is returned.

        Returns:
            A HandoffManager object for the app with the name app_name or None if no app with that name is found.
        """

        if not app_name:
            return self

        # Get the app
        harvester = tethys_apps.app_harvester.SingletonAppHarvester()
        apps = harvester.apps

        for app in apps:
            if app.package == app_name:
                manager = app.get_handoff_manager()
                return manager

    def _get_valid_handlers(self):
        """
        Returns a list of valid HandoffHandler objects.
        """
        valid_handlers = [handler for handler in self.handlers if handler.valid]

        # Code for backwards compatibility TODO: delete this code block when deprecated
        valid_handlers = []
        for handler in self.handlers:
            if handler.valid:
                valid_handlers.append(handler)
            else:
                handler_str = handler.handler
                if ':' in handler_str:
                    print('DEPRECATION WARNING: The handler attribute of a HandoffHandler should now be in the form: "my_first_app.controllers.my_handler". The form "%s" is now deprecated.' % (handler_str,))

                    # Split into module name and function name
                    module_path, function_name  = handler_str.split(':')

                    # Pre-process handler path
                    full_module_path = '.'.join(('tethys_apps.tethysapp', self.app.package, module_path))

                    try:
                        # Import module
                        module = __import__(full_module_path, fromlist=[function_name])
                    except ImportError:
                        pass
                    else:
                        handler._function = getattr(module, function_name)
                        handler._valid = True
                        valid_handlers.append(handler)

        return valid_handlers


class HandoffHandler(TethysFunctionExtractor):
    """
    An object that is used to register a Handoff handler functions.

    Attributes:
      name(str): Name of the handoff handler.
      handler(str): Path to the handler function for the handoff interaction. Use dot-notation (e.g.: "foo.bar.function").
      internal(bool, optional): Specifies that the handler is only for internal (i.e. within the same Tethys server) purposes.
    """

    def __init__(self, name, handler, internal=False):
        """
        Constructor
        """
        self.name = name
        self.handler = handler
        self.internal = internal
        super(HandoffHandler, self).__init__(self.handler)

        # ensure that the function and valid attributes are initialized
        self.function

        # make each instance callable
        self.__class__ = type(self.__class__.__name__, (self.__class__,), {})
        self.__class__.__call__ = lambda this, *args, **kwargs: this.function(*args, **kwargs)

    def __repr__(self):
        """
        String representation
        """
        return '<Handoff Handler: name={0}, handler={1}>'.format(self.name, self.handler)

    def __json__(self):
        """
        JSON representation
        """
        return {'name': self.name,
                'arguments': self.json_arguments,
                }

    @property
    def arguments(self):
        """
        Returns a list of arguments for the HandoffHandler function.
        """
        return inspect.getargspec(self.function).args

    @property
    def json_arguments(self):
        """
        Returns self.arguments with the 'request' argument removed.
        """
        args = self.arguments
        if 'request' in args:
            index = args.index('request')
            args.pop(index)
        return args