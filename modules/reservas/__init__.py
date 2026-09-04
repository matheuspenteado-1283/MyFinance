from flask import Blueprint

bp = Blueprint('reservas', __name__)

from . import routes  # noqa
