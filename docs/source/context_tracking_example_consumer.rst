================
Example consumer
================

This page shows a minimal consumer for :doc:`context tracking <context_tracking>` events.


What it does
============

* Declares a durable topic exchange ``rez.context`` and a durable queue bound to
  ``REZ.CONTEXT.*``, so events wait in the queue while the script isn't running.
* Inserts and commits each message, then acks it. If the script dies in between, the message
  is delivered again: you may get a rare duplicate, but you don't lose events.
* Uses the time of arrival as ``received_at``. rez doesn't send an event time;
  ``context.timestamp`` is when the context was resolved, which for ``sourced`` events can be
  days earlier.
* Turns the resolved variant handles into ``name-version`` strings (``resolved_packages``), so
  "who used maya-2025.3" is an indexed array lookup. The full context is kept in a ``jsonb``
  column, and the :data:`context_tracking_extra_fields` go to ``extra``.
* Reads ``NaN`` and ``Infinity`` (which Python's ``json`` writes, but ``jsonb`` rejects) as null.
* Logs and drops messages it can't store: invalid JSON, no ``action`` or ``context``, or text
  PostgreSQL can't store (a NUL character). Requeueing them would only fail again.
* If the database or broker goes away, it reconnects every 5 seconds. The message being handled
  stays in the queue.

What it leaves out
==================

* batched inserts, for much higher throughput;
* a rejects table that keeps undecodable messages instead of dropping them;
* cleaning of NUL characters and invalid surrogates, and checks on field types (a wrong type
  becomes NULL instead of failing the insert);
* monthly partitions, so old data can be dropped cheaply;
* configuration for rez's default exchange, extra fields mapped to their own columns, health
  checks, Prometheus metrics, and a Docker image.

Tested with Python 3.10 and pika 1.5. pika 1.5 warns that ``BlockingConnection`` is deprecated in
favour of its new thread-based ``Connection``; it still works and remains available until pika 2.0.

Running it
==========

The script needs two Python packages:

.. code-block:: text
   :caption: requirements.txt

   pika>=1.2,<2
   psycopg2-binary>=2.9

It also needs a RabbitMQ broker and a PostgreSQL database, both with a user ``rez`` whose
password is ``rez``. For a local test, you can start both with Docker:

.. code-block:: sh

   docker run -d --name rez-rabbitmq -p 5672:5672 -e RABBITMQ_DEFAULT_USER=rez -e RABBITMQ_DEFAULT_PASS=rez rabbitmq:4
   docker run -d --name rez-postgres -p 5432:5432 -e POSTGRES_USER=rez -e POSTGRES_PASSWORD=rez postgres:17

Install the packages, point the script at your broker and database, and start it:

.. code-block:: sh

   pip install -r requirements.txt
   export AMQP_URL=amqp://rez:rez@localhost:5672/
   export PG_DSN=postgresql://rez:rez@localhost:5432/rez
   python consumer.py

Configure rez to match:

.. code-block:: python
   :caption: rezconfig.py

   context_tracking_host = "localhost:5672"
   context_tracking_amqp = {
       "userid": "rez",
       "password": "rez",
       "exchange_name": "rez.context",
       "exchange_routing_key": "REZ.CONTEXT",
       "message_delivery_mode": 2,  # persistent
   }

Start the script once before rez sends anything: it creates the exchange and the queue, and until
a queue exists RabbitMQ drops the messages. This also takes care of the exchange requirement
described in :doc:`context_tracking`.

It writes each event to a ``rez_context_event`` table, which it creates if missing.


.. _context-tracking-example-consumer-code:

Code
====

.. code-block:: python
   :caption: consumer.py

   """A minimal rez context tracking consumer: RabbitMQ -> Postgres.

   One message, one row, one commit. No batching, metrics or partitions.

       pip install pika psycopg2-binary
       AMQP_URL=amqp://rez:rez@localhost:5672/ PG_DSN=postgresql://rez:rez@localhost/rez \
           python consumer.py

   rez config (rezconfig.py) to match:

       context_tracking_host = "localhost:5672"
       context_tracking_amqp = {
           "userid": "rez",
           "password": "rez",
           "exchange_name": "rez.context",
           "exchange_routing_key": "REZ.CONTEXT",
           "message_delivery_mode": 2,  # persistent
       }
   """

   import json
   import logging
   import os
   import time
   from datetime import datetime, timezone

   import pika
   import psycopg2
   from psycopg2.extras import Json

   AMQP_URL = os.environ.get("AMQP_URL", "amqp://rez:rez@localhost:5672/")
   PG_DSN = os.environ.get("PG_DSN", "postgresql://rez:rez@localhost:5432/rez")
   EXCHANGE = "rez.context"  # context_tracking_amqp["exchange_name"]
   QUEUE = "rez.context.tracking"
   BINDING_KEY = "REZ.CONTEXT.*"  # rez sends REZ.CONTEXT.CREATED / REZ.CONTEXT.SOURCED

   SCHEMA = """
   CREATE TABLE IF NOT EXISTS rez_context_event (
       id                 bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
       received_at        timestamptz NOT NULL,
       routing_key        text NOT NULL,
       action             text NOT NULL,
       host               text,
       username           text,
       rez_version        text,
       status             text,
       context_timestamp  timestamptz,
       solve_time         double precision,
       load_time          double precision,
       from_cache         boolean,
       package_requests   text[],
       implicit_packages  text[],
       resolved_packages  text[],
       context            jsonb NOT NULL,
       extra              jsonb NOT NULL
   );
   CREATE INDEX IF NOT EXISTS rez_context_event_received_at_idx
       ON rez_context_event (received_at);
   CREATE INDEX IF NOT EXISTS rez_context_event_resolved_packages_idx
       ON rez_context_event USING gin (resolved_packages);
   """

   INSERT = """
   INSERT INTO rez_context_event (
       received_at, routing_key, action, host, username, rez_version, status,
       context_timestamp, solve_time, load_time, from_cache, package_requests,
       implicit_packages, resolved_packages, context, extra
   ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
   """

   log = logging.getLogger("rez-consumer")


   def to_row(routing_key, body):
       # Postgres jsonb rejects NaN/Infinity (Python's json writes them), so read them as null.
       data = json.loads(body, parse_constant=lambda name: None)
       action = data.pop("action")
       context = data.pop("context")
       timestamp = context.get("timestamp")  # when the context was resolved, epoch seconds
       # Variant handles -> "name-version", which makes "who used maya-2025.3" an
       # indexed array lookup. The full handles stay in the context column.
       resolved = [
           "-".join(filter(None, (p["variables"]["name"], p["variables"].get("version"))))
           for p in context.get("resolved_packages") or []
       ]
       return (
           # rez sends no event time; the time of arrival is the best there is.
           # (context.timestamp is the resolve time: for "sourced" events that is
           # when the saved context was originally resolved.)
           datetime.now(timezone.utc),
           routing_key,
           action,
           data.pop("host", None),
           data.pop("user", None),
           data.pop("rez_version", None),
           context.get("status"),
           datetime.fromtimestamp(timestamp, timezone.utc) if timestamp else None,
           context.get("solve_time"),
           context.get("load_time"),
           context.get("from_cache"),
           context.get("package_requests"),
           context.get("implicit_packages"),
           resolved,
           Json(context),
           Json(data),  # whatever is left: context_tracking_extra_fields, e.g. {"show": ...}
       )


   def consume(db, connection):
       channel = connection.channel()
       # Durable exchange and queue: rez's messages wait in the queue while this
       # script is not running. Start it once before rez sends anything, though:
       # an exchange without a bound queue drops messages.
       channel.exchange_declare(EXCHANGE, exchange_type="topic", durable=True)
       channel.queue_declare(QUEUE, durable=True)
       channel.queue_bind(QUEUE, EXCHANGE, routing_key=BINDING_KEY)
       channel.basic_qos(prefetch_count=100)

       def on_message(ch, method, properties, body):
           try:
               row = to_row(method.routing_key, body)
               with db.cursor() as cur:
                   cur.execute(INSERT, row)
               db.commit()
           except Exception:
               if db.closed:
                   raise  # lost the database: stop without ack, the message stays queued
               # Roll back only on a live connection; on a closed one that would raise
               # and hide the original error.
               db.rollback()
               # Not JSON, no "action"/"context", a NUL character in a string, ...
               # Acked anyway: requeueing would just fail again, forever.
               log.exception("dropping message: %r", body[:500])
           # Ack only after the commit: a crash before this means the message is
           # delivered again (at least once; a rare duplicate rather than a loss).
           ch.basic_ack(method.delivery_tag)

       channel.basic_consume(QUEUE, on_message)
       log.info("consuming from %s", QUEUE)
       channel.start_consuming()


   def main():
       logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
       logging.getLogger("pika").setLevel(logging.WARNING)  # pika logs every connect step at INFO
       while True:
           db = connection = None
           try:
               db = psycopg2.connect(PG_DSN)
               with db, db.cursor() as cur:
                   cur.execute(SCHEMA)
               connection = pika.BlockingConnection(pika.URLParameters(AMQP_URL))
               consume(db, connection)
           except (pika.exceptions.AMQPError, psycopg2.Error) as exc:
               log.warning("connection lost (%r), retrying in 5 s", exc)
               time.sleep(5)
           except KeyboardInterrupt:
               break
           finally:
               for conn in (connection, db):
                   try:
                       if conn is not None:
                           conn.close()
                   except Exception:
                       pass  # already closed or broken


   if __name__ == "__main__":
       main()
