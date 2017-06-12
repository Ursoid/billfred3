========
Billfred
========

A jabber bot written with python 3. Uses `SleekXMPP`_.

Install
=======

Libxml is required to compile *lxml* dependency.

Installation with virtualenv and pip::

  python -m venv env
  # optional: run "source ./env/bin/activate" to use env python
  # and pip without providing full path
  cd /path/to/billfred/code 
  /path/to/env/bin/pip install -e .

Billfred also can be installed with setup.py::

  /path/to/env/bin/python setup.py develop

Then copy ``billfred/billfred.cfg_`` somewhere and edit it.

Usage
=====

When installed through pip or setup.py, python puts script
``billfred`` into path (or into virtualenv bin/ directory). Run it
like this::

  billfred --config /path/to/config.cfg

If ``--config`` isn't specified, ``billfred.cfg`` in current directory
will be used.

.. _SleekXMPP: http://sleekxmpp.com/
