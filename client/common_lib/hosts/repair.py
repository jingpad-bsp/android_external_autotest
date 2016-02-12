# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""
Framework for host verification in Autotest.

The framework provides implementation code in support of
`Host.verify()` used in Verify special tasks.

The framework consists of these classes:
  * `Verifier`: A class representing a single verification check.
  * `RepairStrategy`:  A class for organizing a collection of
    `Verifier` instances, and invoking them in order.

Individual operations during verification are handled by instances of
`Verifier`.  `Verifier` objects are meant to test for specific
conditions that may cause tests to fail.
"""

import logging

import common
from autotest_lib.client.common_lib import error


class AutotestHostVerifyError(error.AutotestError):
    """
    Generic Exception for failures from `Verifier` objects.

    Instances of this exception can be raised when a `verify()`
    method fails, if no more specific exception is available.
    """
    pass


class AutotestVerifyDependencyError(error.AutotestError):
    """
    Exception raised for failures in dependencies.

    This exception is used to distinguish an original failure from a
    failure being passed back from a verification dependency.  That is,
    if 'B' depends on 'A', and 'A' fails, 'B' will raise this exception
    to signal that the original failure is further down the dependency
    chain.

    Each argument to the constructor for this class should be the string
    description of one failed dependency.

    `Verifier._verify_host()` recognizes and handles this exception
    specially.
    """
    pass


class Verifier(object):
    """
    Abstract class embodying one verification check.

    A concrete subclass of `Verifier` provides a simple check that can
    determine a host's fitness for testing.  Failure indicates that the
    check found a problem that can cause at least one test to fail.

    `Verifier` objects are organized in a DAG identifying dependencies
    among operations.  The DAG controls ordering and prevents wasted
    effort:  If verification operation V2 requires that verification
    operation V1 pass, then a) V1 will run before V2, and b) if V1
    fails, V2 won't run at all.  The `_verify_host()` method ensures
    that all dependencies run and pass before invoking the `verify()`
    method.

    A `Verifier` object caches its result the first time it calls
    `verify()`.  Subsequent calls return the cached result, without
    re-running the check code.  The `_reverify()` method clears the
    cached result in the current node, and in all dependencies.

    Subclasses must supply these properties and methods:
      * `verify()`: This is the method to perform the actual
        verification check.
      * `tag`:  This property is a short string to uniquely identify
        this verifier in `status.log` records.
      * `description`:  This is a property with a one-line summary of
        the verification check to be performed.  This string is used to
        identify the verifier in debug logs.
    Subclasses must override all of the above attributes; subclasses
    should not override or extend any other attributes of this class.

    The base class manages the following private data:
      * `_result`:  The cached result of verification.
      * `_dependency_list`:  The list of dependencies.
    Subclasses should not use these attributes.

    @property tag               Short identifier to be used in logging.
    @property description       Text summary of the verification check.
    @property _result           Cached result of verification.
    @property _dependency_list  Dependency pre-requisites.
    """

    def __init__(self, dependencies):
        self._result = None
        self._dependency_list = dependencies
        self._verify_tag = 'verify.' + self.tag


    def _verify_list(self, host, verifiers):
        """
        Test a list of verifiers against a given host.

        This invokes `_verify_host()` on every verifier in the given
        list.  If any verifier in the transitive closure of dependencies
        in the list fails, an `AutotestVerifyDependencyError` is raised
        containing the description of each failed verifier.  Only
        original failures are reported; verifiers that don't run due
        to a failed dependency are omitted.

        By design, original failures are logged once in `_verify_host()`
        when `verify()` originally fails.  The additional data gathered
        here is for the debug logs to indicate why a subsequent
        operation never ran.

        @param host       The host to be tested against the verifiers.
        @param verifiers  List of verifiers to be checked.

        @raises AutotestVerifyDependencyError   Raised when at least
                        one verifier in the list has failed.
        """
        failures = []
        for v in verifiers:
            try:
                v._verify_host(host)
            except AutotestVerifyDependencyError as e:
                failures.extend(e.args)
            except Exception as e:
                failures.append(v.description)
        if failures:
            raise AutotestVerifyDependencyError(*failures)


    def _reverify(self):
        """
        Discard cached verification results.

        Reset the cached verification result for this node, and for the
        transitive closure of all dependencies.
        """
        if self._result is not None:
            self._result = None
            for v in self._dependency_list:
                v._reverify()


    def _verify_host(self, host):
        """
        Determine the result of verification, and log results.

        If this verifier does not have a cached verification result,
        check dependencies, and if they pass, run `verify()`.  Log
        informational messages regarding failed dependencies.  If we
        call `verify()`, log the result in `status.log`.

        If we already have a cached result, return that result without
        logging any message.

        @param host   The host to be tested for a problem.
        """
        if self._result is not None:
            if isinstance(self._result, Exception):
                raise self._result  # cached failure
            elif self._result:
                return              # cached success
        self._result = False
        try:
            self._verify_list(host, self._dependency_list)
        except AutotestVerifyDependencyError as e:
            logging.info('Dependencies failed; skipping this '
                         'operation:  %s', self.description)
            for description in e.args:
                logging.debug('    %s', description)
            raise
        # TODO(jrbarnette): this message also logged for
        # RepairAction; do we want to customize that message?
        logging.info('Verifying this condition: %s', self.description)
        try:
            self.verify(host)
            host.record("GOOD", None, self._verify_tag)
        except Exception as e:
            logging.exception('Failed: %s', self.description)
            self._result = e
            host.record("FAIL", None, self._verify_tag, str(e))
            raise
        self._result = True


    def verify(self, host):
        """
        Unconditionally perform a verification check.

        This method is responsible for testing for a single problem on a
        host.  Implementations should follow these guidelines:
          * The check should find a problem that will cause testing to
            fail.
          * Verification checks on a working system should run quickly
            and should be optimized for success; a check that passes
            should finish within seconds.
          * Verification checks are not expected have side effects, but
            may apply trivial fixes if they will finish within the time
            constraints above.

        A verification check should normally trigger a single set of
        repair actions.  If two different failures can require two
        different repairs, ideally they should use two different
        subclasses of `Verifier`.

        Implementations indicate failure by raising an exception.  The
        exception text should be a short, 1-line summary of the error.
        The text should be concise and diagnostic, as it will appear in
        `status.log` files.

        If this method finds no problems, it returns without raising any
        exception.

        Implementations should avoid most logging actions, but can log
        DEBUG level messages if they provide significant information for
        diagnosing failures.

        @param host   The host to be tested for a problem.
        """
        raise NotImplementedError('Class %s does not implement '
                                  'verify()' % type(self).__name__)


    @property
    def tag(self):
        """
        Tag for use in logging status records.

        This is a property with a short string used to identify the
        verification check in the 'status.log' file.  The tag should
        contain only lower case letters, digits, and '_' characters.
        This tag is not used alone, but is combined with other
        identifiers, based on the operation being logged.

        N.B. Subclasses are required to override this method, but
        we _don't_ raise NotImplementedError here.  `_verify_host()`
        fails in inscrutable ways if this method raises any
        exception, so for debug purposes, it's better to return a
        default value.

        @return A short identifier-like string.
        """
        return 'bogus__%s' % type(self).__name__


    @property
    def description(self):
        """
        Text description of this verifier for log messages.

        This string will be logged with failures, and should
        describe the condition required for success.

        N.B. Subclasses are required to override this method, but
        we _don't_ raise NotImplementedError here.  `_verify_host()`
        fails in inscrutable ways if this method raises any
        exception, so for debug purposes, it's better to return a
        default value.

        @return A descriptive string.
        """
        return ('Class %s fails to implement description().' %
                type(self).__name__)


class _RootVerifier(Verifier):
    """
    Utility class used by `RepairStrategy`.

    A node of this class by itself does nothing; it always passes (if it
    can run).  This class exists merely to be the root of a DAG of
    dependencies in an instance of `RepairStrategy`.
    """

    def __init__(self, dependencies, tag):
        # N.B. must initialize _tag before calling superclass,
        # because the superclass constructor uses `self.tag`.
        self._tag = tag
        super(_RootVerifier, self).__init__(dependencies)


    def verify(self, host):
        pass


    @property
    def tag(self):
        return self._tag


    @property
    def description(self):
        return 'All host verification checks pass'



class RepairStrategy(object):
    """
    A class for organizing `Verifier` objects.

    An instance of `RepairStrategy` is organized as a set of `Verifier`
    objects.  The class provides methods for invoking those objects in
    order, when needed: the `verify()` method walks the verifier DAG in
    dependency order.
    """

    def __init__(self, verifier_data):
        """
        Construct a `RepairStrategy` from simplified DAG data.

        The input `verifier_data` object describes how to construct
        verify nodes and the dependencies that relate them, as detailed
        below.

        The `verifier_data` parameter is an iterable object (e.g. a list
        or tuple) of entries.  Each entry is a two-element iterable of
        the form `(constructor, deps)`:
          * The `constructor` value is a callable that creates a
            `Verifier` as for the interface of the default constructor.
            For classes that inherit the default constructor from
            `Verifier`, this can be the class itself.
          * The `deps` value is an iterable (e.g. list or tuple) of
            strings.  Each string corresponds to the `tag` member of a
            `Verifier` dependency.

        Note that `verifier_data` *must* be listed in dependency order.
        That is, if `B` depends on `A`, then the constructor for `A`
        must precede the constructor for `B` in the list.  Put another
        way, the following is valid `verifier_data`:

        ```
            ((AlphaVerifier, ()), (BetaVerifier, ('alpha',)))
        ```

        The following will fail at construction time:

        ```
            ((BetaVerifier, ('alpha',)), (AlphaVerifier, ()))
        ```

        @param verifier_data  Iterable value with constructors for the
                              elements of the verification DAG and their
                              dependencies.
        """
        verifier_map = {}
        roots = set()
        for construct, deps in verifier_data:
            v = construct([verifier_map[d] for d in deps])
            verifier_map[v.tag] = v
            roots.add(v)
            roots.difference_update(deps)
        self._verify_root = _RootVerifier(list(roots), 'all')


    def verify(self, host):
        """
        Run the verifier DAG on the given host.

        @param host   The target to be verified.
        """
        self._verify_root._reverify()
        self._verify_root._verify_host(host)
