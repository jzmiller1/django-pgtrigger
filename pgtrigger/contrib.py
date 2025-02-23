"""Additional goodies"""
from pgtrigger import core
from pgtrigger import utils


# A sentinel value to determine if a kwarg is unset
_unset = object()


class Protect(core.Trigger):
    """A trigger that raises an exception."""

    when = core.Before

    def get_func(self, model):
        return f'''
            RAISE EXCEPTION
                'pgtrigger: Cannot {str(self.operation).lower()} rows from % table',
                TG_TABLE_NAME;
        '''


class FSM(core.Trigger):
    """Enforces a finite state machine on a field.

    Supply the trigger with the "field" that transitions and then
    a list of tuples of valid transitions to the "transitions" argument.

    .. note::

        Only non-null ``CharField`` fields are currently supported.
    """

    when = core.Before
    operation = core.Update
    field = None
    transitions = None

    def __init__(self, *, name=None, condition=None, field=None, transitions=None):
        self.field = field or self.field
        self.transitions = transitions or self.transitions

        if not self.field:  # pragma: no cover
            raise ValueError('Must provide "field" for FSM')

        if not self.transitions:  # pragma: no cover
            raise ValueError('Must provide "transitions" for FSM')

        super().__init__(name=name, condition=condition)

    def get_declare(self, model):
        return [('_is_valid_transition', 'BOOLEAN')]

    def get_func(self, model):
        col = model._meta.get_field(self.field).column
        transition_uris = '{' + ','.join([f'{old}:{new}' for old, new in self.transitions]) + '}'

        return f'''
            SELECT CONCAT(OLD.{utils.quote(col)}, ':', NEW.{utils.quote(col)}) = ANY('{transition_uris}'::text[])
                INTO _is_valid_transition;

            IF (_is_valid_transition IS FALSE AND OLD.{utils.quote(col)} IS DISTINCT FROM NEW.{utils.quote(col)}) THEN
                RAISE EXCEPTION
                    'pgtrigger: Invalid transition of field "{self.field}" from "%" to "%" on table %',
                    OLD.{utils.quote(col)},
                    NEW.{utils.quote(col)},
                    TG_TABLE_NAME;
            ELSE
                RETURN NEW;
            END IF;
        '''  # noqa


class SoftDelete(core.Trigger):
    """Sets a field to a value when a delete happens.

    Supply the trigger with the "field" that will be set
    upon deletion and the "value" to which it should be set.
    The "value" defaults to ``False``.

    .. note::

        This trigger currently only supports nullable ``BooleanField``,
        ``CharField``, and ``IntField`` fields.
    """

    when = core.Before
    operation = core.Delete
    field = None
    value = False

    def __init__(self, *, name=None, condition=None, field=None, value=_unset):
        self.field = field or self.field
        self.value = value if value is not _unset else self.value

        if not self.field:  # pragma: no cover
            raise ValueError('Must provide "field" for soft delete')

        super().__init__(name=name, condition=condition)

    def get_func(self, model):
        soft_field = model._meta.get_field(self.field).column
        pk_col = model._meta.pk.column

        def _render_value():
            if self.value is None:
                return 'NULL'
            elif isinstance(self.value, str):
                return f"'{self.value}'"
            else:
                return str(self.value)

        return f'''
            UPDATE {utils.quote(model._meta.db_table)}
            SET {soft_field} = {_render_value()}
            WHERE {utils.quote(pk_col)} = OLD.{utils.quote(pk_col)};
            RETURN NULL;
        '''


class UpdateSearchVector(core.Trigger):
    """Updates a ``django.contrib.postgres.search.SearchVectorField`` from document fields.

    Supply the trigger with the ``vector_field`` that will be updated with
    changes to the ``document_fields``. Optionally provide a ``config_name``, which
    defaults to ``pg_catalog.english``.

    This trigger uses ``tsvector_update_trigger`` to update the vector field.
    See `the Postgres docs <https://www.postgresql.org/docs/current/textsearch-features.html#TEXTSEARCH-UPDATE-TRIGGERS>`__
    for more information.

    .. note::

        ``UpdateSearchVector`` triggers are not compatible with `pgtrigger.ignore` since
        it references a built-in trigger. Trying to ignore this trigger results in a
        `RuntimeError`.
    """  # noqa

    when = core.Before
    vector_field = None
    document_fields = None
    config_name = 'pg_catalog.english'

    def __init__(self, *, name=None, vector_field=None, document_fields=None, config_name=None):
        self.vector_field = vector_field or self.vector_field
        self.document_fields = document_fields or self.document_fields
        self.config_name = config_name or self.config_name

        if not self.vector_field:
            raise ValueError('Must provide "vector_field" to update search vector')

        if not self.document_fields:
            raise ValueError('Must provide "document_fields" to update search vector')

        if not self.config_name:  # pragma: no cover
            raise ValueError('Must provide "config_name" to update search vector')

        super().__init__(name=name, operation=core.Insert | core.UpdateOf(*document_fields))

    def ignore(self, model):
        raise RuntimeError(f"Cannot ignore {self.__class__.__name__} triggers")

    def render_func(self, model):
        return ''

    def render_trigger(self, model, function=None):
        document_cols = [model._meta.get_field(field).column for field in self.document_fields]
        rendered_document_cols = ', '.join(utils.quote(col) for col in document_cols)
        vector_col = model._meta.get_field(self.vector_field).column
        function = (
            f'tsvector_update_trigger({utils.quote(vector_col)},'
            f' {utils.quote(self.config_name)}, {rendered_document_cols})'
        )
        return super().render_trigger(model, function=function)
