#!/usr/bin/python

# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import logging

import common

try:
  from apiclient.discovery import build
  from apiclient.http import HttpError
except ImportError as e:
  build = None
  logging.info("API client for bug filing disabled. %s", e)


class ProjectHostingApiException(Exception):
    """
    Raised when an api call fails, since the actual
    HTTP error can be cryptic.
    """


class ProjectHostingApiClient():
    """
    Client class for interaction with the project hosting api.
    """

    def __init__(self, api_key, project_name):
        if build is None:
            logging.error('Cannot get apiclient library.')
            return None

        self._service = build('projecthosting', 'v2', developerKey=api_key)
        self._project_name = project_name


    def _execute_request(self, request):
        """
        Executes an api request checking for a reason upon failure.

        @param request: request to be executed.
        @raises: ProjectHostingApiException if we
                 fail to execute the request.
        @return: results from the executed request.
        """
        try:
            return request.execute()
        except HttpError, e:
            msg = 'Unable to execute your request. '
            if hasattr(e, 'content') and 'keyInvalid' in e.content:
                msg += 'Your credentials have been revoked.'
            raise ProjectHostingApiException(msg)


    def _get_field(self, field):
        """
        Gets a field from the project.

        This method directly queries the project hosting API using bugdroids1's,
        api key.

        @param field: A selector, which corresponds loosely to a field in the
                      new bug description of the crosbug frontend.

        @return: A json formatted python dict of the specified field's options,
                 or None if we can't find the api library. This dictionary
                 represents the javascript literal used by the front end tracker
                 and can hold multiple filds.

                The returned dictionary follows a template, but it's structure
                is only loosely defined as it needs to match whatever the front
                end describes via javascript.
                For a new issue interface which looks like:

                field 1: text box
                              drop down: predefined value 1 = description
                                         predefined value 2 = description
                field 2: text box
                              similar structure as field 1

                you will get a dictionary like:
                {
                    'field name 1': {
                        'project realted config': 'config value'
                        'property': [
                            {predefined value for property 1, description},
                            {predefined value for property 2, description}
                        ]
                    },

                    'field name 2': {
                        similar structure
                    }
                    ...
                }
        """
        project = self._service.projects()
        request = project.get(projectId=self._project_name,
                              fields=field)
        return self._execute_request(request)


    def get_property_values(self, prop_dict):
        """
        Searches a dictionary as returned by _get_field for property lists,
        then returns each value in the list. Effectively this gives us
        all the accepted values for a property. For example, in crosbug
        crosbug, 'properties' map to things like Status, Labels, Owner
        etc, each of these will have a list within the issuesConfig dict. Each
        list will contain a listing of all predefined values, this function
        retrieves each of these lists.

        @param prop_dict: dictionary which contains a list of properties.

        @yield: each value in a property list. This can be a dict or any other
                type of datastructure, the caller is responsible for handling
                it correctly.
        """
        for name, property in prop_dict.iteritems():
            if isinstance(property, list):
                for values in property:
                    yield values


    def get_cros_labels(self, prop_dict):
        """
        Helper function to isolate labels from the labels dictionary. This
        dictionary is of the form:
            {
                "label": "Cr-OS-foo",
                "description": "description"
            },
        And maps to the frontend like so:
            Labels: Cr-???
                    Cr-OS-foo = description
        where Cr-OS-foo is a conveniently predefined value for Label Cr-OS-???.

        @param prop_dict: a dictionary we expect the Cros label to be in.
        @return: A lower case product area, eg: video, factory, ui.
        """
        label = prop_dict.get('label')
        if label and 'Cr-OS-' in label:
            return label.split('Cr-OS-')[1]


    def get_areas(self):
        """
        Parse issue options and return a list of 'Cr-OS' labels.

        @return: a list of Cr-OS labels from crosbug, eg: ['kernel', 'systems']
        """
        try:
            issue_options_dict = self._get_field('issuesConfig')
        except ProjectHostingApiException as e:
            logging.error('Unable to determine area labels: %s', str(e))
            return []

        # Since we can request multiple fields at once we need to
        # retrieve each one from the field options dictionary, even if we're
        # really only asking for one field.
        issue_options = issue_options_dict.get('issuesConfig')
        return filter(None, [self.get_cros_labels(each)
                      for each in self.get_property_values(issue_options)
                      if isinstance(each, dict)])

