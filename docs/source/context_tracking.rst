================
Context Tracking
================

Context tracking makes rez send a message to an `AMQP <https://www.amqp.org/>`_ message broker
whenever a :doc:`context <context>` is created or sourced. This gives you a record of which
packages are actually used across your studio, by whom, on which machines and how often.
You can use that to answer questions such as "Is anybody still using ``maya-2022``?" or
"Which shows depend on this version of ``openexr``?", and to see how long resolves take in production.

Tracking is disabled by default.

Events
======

Rez emits two kinds of events, which are called *actions*:

``created``
   A new context was constructed. This either caused a resolve or fetched one from the
   :doc:`resolve cache <caching>`. For example, every ``rez-env`` invocation emits it.

``sourced``
   An existing context was recreated, for example by loading an ``.rxt`` file.

Each event is published as a JSON message that looks like this:

.. code-block:: python

   {
       "action": "created",
       "host": "some_fqdn",
       "user": "jdoe",
       "rez_version": "3.5.0",
       "context": {
           ...
       }
   }

The ``context`` field contains the context itself (the same data you find in an ``.rxt``
file), filtered by the fields listed in :data:`context_tracking_context_fields`. By default,
these fields are included:

* ``status``
* ``timestamp``
* ``solve_time``
* ``load_time``
* ``from_cache``
* ``package_requests``
* ``implicit_packages``
* ``resolved_packages``

Each message's routing key is ``{exchange_routing_key}.{ACTION}``, for example
``REZ.CONTEXT.CREATED`` or ``REZ.CONTEXT.SOURCED``. The prefix comes from the ``exchange_routing_key``
entry in :data:`context_tracking_amqp`.

Extra fields
------------

You can add your own fields to every message with :data:`context_tracking_extra_fields`.
Environment variables in the values are expanded, which makes this a convenient way to
attach studio-specific information such as the current show or shot:

.. code-block:: python

   context_tracking_extra_fields = {
       "show": "${SHOW}",
       "shot": "${SHOT}",
   }

If a field references an unknown environment variable, or is an empty string (possibly as
a result of variable expansion), rez removes it from the message.

Requirements
============

Message broker
--------------

Rez publishes events over AMQP 0.9.1 (via the vendored `pika <https://pika.readthedocs.io/>`_
library), so you need a running message broker that speaks that protocol. Examples are:

* `RabbitMQ <https://www.rabbitmq.com/>`_, the most common choice
* `LavinMQ <https://lavinmq.com/>`_
* Hosted services such as `Amazon MQ for RabbitMQ <https://aws.amazon.com/amazon-mq/>`_
  or `CloudAMQP <https://www.cloudamqp.com/>`_

.. note::
   AMQP 1.0 is **not** supported. Despite the similar name and version number, AMQP 1.0 is
   not a newer iteration of AMQP 0.9.1. It is a complete re-imagining of the protocol with a
   fundamentally different approach, and the two are not compatible with each other.

   AMQP 0.9.1 defines both a wire protocol and a broker model: exchanges, queues and the
   bindings between them are part of the specification, and clients publish messages to an
   exchange with a routing key. AMQP 1.0 drops the broker model entirely. It only defines how
   two peers transfer messages between each other, and leaves it to each implementation to
   decide what exists on the other end. Concepts that rez relies on, such as exchanges and
   routing keys, simply do not exist in AMQP 1.0.

   Be careful when a product advertises "AMQP support", and check which version it means.
   Brokers and services that only implement AMQP 1.0, such as ActiveMQ Classic, ActiveMQ Artemis
   or Azure Service Bus, will not work with rez. Brokers that support both versions, such as
   RabbitMQ, work fine, because rez uses their AMQP 0.9.1 interface.

Exchange
--------

.. warning::
   Rez does **not** create the target exchange. It only publishes to the exchange named
   in :data:`context_tracking_amqp`, so you must declare that exchange on the broker before
   you enable tracking. If the exchange does not exist, the broker rejects the publish and
   the event is lost.

A durable ``topic`` exchange works well because it lets consumers bind with patterns such as
``REZ.CONTEXT.*`` or ``REZ.CONTEXT.CREATED``. With RabbitMQ, you can create it in the
management UI, with ``rabbitmqadmin``, or as part of your broker's definitions file.

Keep in mind that the broker discards any message that no queue is bound to receive.
To keep events, bind at least one queue to the exchange (see :ref:`context-tracking-persisting-events`).

Configuration
=============

Tracking is enabled as soon as :data:`context_tracking_host` is set to a non-empty value. It takes
the broker address in the form ``{host}[:{port}]``. Connection settings go in
:data:`context_tracking_amqp`:

.. code-block:: python

   context_tracking_host = "amqp.example.com:5672"

   context_tracking_amqp = {
       "userid": "rez",
       "password": "secret",
       "connect_timeout": 10,
       "exchange_name": "rez",
       "exchange_routing_key": "REZ.CONTEXT",
       "message_delivery_mode": 1,
   }

``message_delivery_mode`` is the AMQP delivery mode. ``1`` is non-persistent and ``2`` is
persistent, meaning the broker writes the message to disk so that it survives a broker restart
(as long as the queue is durable too).

Rez publishes messages in a background thread, so tracking does not slow down resolves.
When the process exits, rez waits up to five seconds for pending messages to be sent.
If publishing fails, rez prints an error but the context itself is unaffected.

Please refer to the :ref:`context tracking <config-context-tracking>` configuration section
for a complete list of settings.

Testing your setup
------------------

Set :data:`context_tracking_host` to ``stdout`` to print messages instead of sending them.
This lets you check what the payload looks like without a broker:

.. code-block:: console

   $ export REZ_CONTEXT_TRACKING_HOST=stdout
   $ rez-env python -- echo
   Published to REZ.CONTEXT.CREATED: {'action': 'created', 'context': {...}, ...}

Once you point rez at a real broker, enable :data:`debug_context_tracking` (or set
``REZ_DEBUG_CONTEXT_TRACKING=1``) to print debugging information about the AMQP connection.

.. _context-tracking-persisting-events:

Persisting events
=================

On its own, emitting events is of limited use. A message broker is a transport, not a database:
messages that nobody consumes are discarded, and messages that are consumed are gone once they have
been acknowledged. To get real value out of context tracking, run a listener service that consumes
the events from a queue bound to your exchange and writes them into a permanent store, such as
`PostgreSQL <https://www.postgresql.org/>`_. Once the events are stored, you can run analytics on
them: which packages and versions are in use, who uses them and where, how usage changes over
time, which versions are safe to retire, and how solve and load times develop. Because the
listener is decoupled from rez through the broker, it can be taken down for maintenance without
affecting users, as long as the queue is durable and messages are published as persistent.

See :doc:`context_tracking_example_consumer` for a minimal listener that writes events
from RabbitMQ to PostgreSQL.

.. toctree::
   :hidden:

   context_tracking_example_consumer
