========
Billfred
========

A jabber bot written with python 3. Uses `SleekXMPP`_.

Install
=======

Installation with virtualenv and setup.py::

  python -m venv env
  ./env/bin/python /path/to/billfred/code/setup.py develop

Libxml is required to compile *lxml* dependency.

Then copy ``billfred/billfred.cfg_`` sowewhere and edit it.

Usage
=====

When installed through ``python setup.py develop``, python puts script
``billfred`` into path (or into virtualenv bin/ directory). Run it
like this::

  billfred --config /path/to/config.cfg

If ``--config`` isn't specified, ``billfred.cfg`` in current directory
will be used.

.. _SleekXMPP: http://sleekxmpp.com/
